import secrets

import redis as redis_lib
from fastapi import APIRouter, Depends, Request
from pydantic import Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.deps import client_ip, get_db, get_redis
from app.core.errors import AppError
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)
from app.dealer.models.admin import DealerAdmin
from app.dealer.models.dealer import SIGNED_IN_STATUSES, Dealer, DealerStaff
from app.dealer.schemas.common import Base, PhoneMixin
from app.dealer.services import otp, ratelimit
from app.dealer.services import signup as signup_svc
from app.dealer.services.audit import record_audit

router = APIRouter(prefix="/auth", tags=["dealer-auth"])

# Something for /admin/login to verify against when the email is unknown, so that
# answer costs the same as a real one. Argon2 is ~50-100ms by design; a row that is
# not there costs a database round trip and nothing else, so
# `admin is None or not verify_password(...)` short-circuits and replies in ~1ms.
# That gap is an order of magnitude wider than network jitter, which turns the
# endpoint into a directory of the client's back-office staff: type an address,
# time the 401, learn whether the person works here. The 10-per-5-minutes IP limit
# below slows a sweep down; it does not stop one, and it does nothing about a
# single targeted "does my counterpart at the distributor have an account?".
#
# Hashed ONCE, at import. Generating a throwaway hash per miss would pay argon2 on
# the miss path too, but hashing is slower than verifying — the gap would reopen
# pointing the other way, and unknown emails would become the slow ones.
_DUMMY_PASSWORD_HASH = hash_password(secrets.token_urlsafe(32))


class OtpRequestIn(PhoneMixin, Base):
    phone: str = Field(min_length=6, max_length=20)


class OtpRequestOut(Base):
    resend_in: int
    # Tells the app which screen comes after the code: a returning staff member
    # goes to the dealer app, a new shop finishes creating its account.
    is_new_account: bool = False
    # False when no account exists for this number, so the app can offer signup
    # instead of waiting for a code that was never sent. See the note on
    # otp_request for why this is safe to disclose.
    account_exists: bool = True


class SignupIn(PhoneMixin, Base):
    phone: str = Field(min_length=6, max_length=20)
    name: str = Field(min_length=1, max_length=200, description="The person signing up")
    shop_name: str = Field(min_length=1, max_length=200)
    city: str | None = Field(default=None, max_length=100)
    address: str | None = Field(default=None, max_length=400)
    pincode: str | None = Field(default=None, max_length=10)
    gst_number: str | None = Field(default=None, max_length=20)


class OtpVerifyIn(PhoneMixin, Base):
    phone: str = Field(min_length=6, max_length=20)
    code: str = Field(min_length=4, max_length=8)


class DealerBrief(Base):
    id: str
    code: str
    name: str


class StaffOut(Base):
    id: str
    name: str
    phone: str
    role: str


class TokenPair(Base):
    access_token: str
    refresh_token: str
    expires_in: int
    staff: StaffOut | None = None
    dealer: DealerBrief | None = None


class RefreshIn(Base):
    refresh_token: str


class AdminLoginIn(Base):
    email: str
    password: str


def _revoked_key(jti: str) -> str:
    return f"jwt:revoked:{jti}"


@router.post("/otp/request", response_model=OtpRequestOut)
def otp_request(
    body: OtpRequestIn,
    request: Request,
    db: Session = Depends(get_db),
    redis: redis_lib.Redis = Depends(get_redis),
) -> OtpRequestOut:
    """Send a login code, or say plainly that there is no account.

    This used to answer identically whether or not the number belonged to a
    dealer, so the endpoint could not be used to discover which numbers are
    dealers. That protection is now worthless: shops sign themselves up, so
    anyone can learn the same fact by attempting a signup and reading
    `already_registered`.

    What it still cost was real — a dealer tapping "sign in" with a number that
    has no account got a cheerful "code sent" and then waited forever for a code
    that was never generated. That is exactly how this endpoint was first
    reported as broken.

    Nothing about the account is created or modified here — see services/otp.py.
    """
    ratelimit.enforce(redis, f"otp:ip:{client_ip(request)}", limit=20, window_s=3600)

    staff = db.execute(
        select(DealerStaff).where(DealerStaff.phone == body.phone)
    ).scalar_one_or_none()

    if staff is None or not staff.is_active:
        return OtpRequestOut(resend_in=settings.otp_resend_cooldown_seconds, account_exists=False)

    otp.issue(db, redis, body.phone)
    return OtpRequestOut(resend_in=settings.otp_resend_cooldown_seconds)


@router.post("/signup", response_model=OtpRequestOut)
def signup(
    body: SignupIn,
    request: Request,
    db: Session = Depends(get_db),
    redis: redis_lib.Redis = Depends(get_redis),
) -> OtpRequestOut:
    """Start creating a dealership. Writes NOTHING until the code is verified.

    The typed details are staged in Redis against the OTP; the dealer and staff
    rows are created by /otp/verify once the phone is proven. Staging rather than
    inserting is deliberate — see services/signup.py.
    """
    ratelimit.enforce(redis, f"signup:ip:{client_ip(request)}", limit=10, window_s=3600)

    existing = db.execute(
        select(DealerStaff).where(DealerStaff.phone == body.phone)
    ).scalar_one_or_none()
    if existing is not None:
        raise AppError(
            "already_registered",
            409,
            "This number already has an account. Sign in instead.",
        )

    signup_svc.stage(
        redis,
        signup_svc.PendingSignup(
            phone=body.phone,
            name=body.name,
            shop_name=body.shop_name,
            city=body.city,
            address=body.address,
            pincode=body.pincode,
            gst_number=body.gst_number,
        ),
    )
    otp.issue(db, redis, body.phone)
    return OtpRequestOut(resend_in=settings.otp_resend_cooldown_seconds, is_new_account=True)


@router.post("/otp/verify", response_model=TokenPair)
def otp_verify(
    body: OtpVerifyIn,
    request: Request,
    db: Session = Depends(get_db),
    redis: redis_lib.Redis = Depends(get_redis),
) -> TokenPair:
    otp.verify(redis, body.phone, body.code)

    staff = db.execute(
        select(DealerStaff).where(DealerStaff.phone == body.phone)
    ).scalar_one_or_none()

    if staff is None:
        # No account yet — this is the second half of a signup. The rows are
        # created HERE, now that the phone is proven, and not a moment earlier.
        pending = signup_svc.take(redis, body.phone)
        if pending is None:
            raise AppError(
                "account_not_found",
                403,
                "No account for this number. Create one to get started.",
            )
        dealer, staff = signup_svc.create_from_signup(
            db, pending, auto_approve=settings.dealer_signup_auto_approve
        )
        record_audit(
            db,
            action="dealer_self_signup",
            entity_type="dealer",
            entity_id=dealer.id,
            actor_type="dealer_staff",
            actor_id=staff.id,
            metadata={"code": dealer.code, "shop": dealer.name, "status": dealer.status},
            ip=client_ip(request),
        )
        db.commit()
        return _issue_pair(staff, dealer)

    if not staff.is_active:
        raise AppError("account_not_found", 403, "No active dealer account for this number")

    existing_dealer = db.get(Dealer, staff.dealer_id)
    # A pending shop signs in fine; what it cannot do is redeem.
    if existing_dealer is None or existing_dealer.status not in SIGNED_IN_STATUSES:
        raise AppError("dealer_inactive", 403, "This dealership is not active")

    return _issue_pair(staff, existing_dealer)


def _issue_pair(staff: DealerStaff, dealer: Dealer) -> TokenPair:
    access = create_access_token(str(staff.id), "dealer", {"dealer_id": str(dealer.id)})
    refresh, _ = create_refresh_token(str(staff.id), "dealer")
    return TokenPair(
        access_token=access,
        refresh_token=refresh,
        expires_in=settings.jwt_access_ttl_minutes * 60,
        staff=StaffOut(id=str(staff.id), name=staff.name, phone=staff.phone, role=staff.role),
        dealer=DealerBrief(id=str(dealer.id), code=dealer.code, name=dealer.name),
    )


@router.post("/refresh", response_model=TokenPair)
def refresh_token(
    body: RefreshIn,
    db: Session = Depends(get_db),
    redis: redis_lib.Redis = Depends(get_redis),
) -> TokenPair:
    payload = decode_token(body.refresh_token, expected_aud="dealer", expected_type="refresh")
    if redis.exists(_revoked_key(payload["jti"])):
        raise AppError("invalid_token", 401, "Refresh token revoked")

    staff = db.get(DealerStaff, payload["sub"])
    if staff is None or not staff.is_active:
        raise AppError("invalid_token", 401, "Unknown or disabled account")
    dealer = db.get(Dealer, staff.dealer_id)
    # Same rule as sign-in and as get_current_staff. Demanding 'active' here
    # while both of those accept 'pending' meant a self-signed-up shop was
    # logged out every time its hour-long access token expired, and had to redo
    # the OTP to carry on selling.
    if dealer is None or dealer.status not in SIGNED_IN_STATUSES:
        raise AppError("dealer_inactive", 403, "This dealership is not active")

    # Rotate: the presented refresh token is burned as it is exchanged.
    redis.set(_revoked_key(payload["jti"]), "1", ex=settings.jwt_refresh_ttl_days * 86400)
    return _issue_pair(staff, dealer)


@router.post("/logout", status_code=204)
def logout(body: RefreshIn, redis: redis_lib.Redis = Depends(get_redis)) -> None:
    payload = decode_token(body.refresh_token, expected_aud="dealer", expected_type="refresh")
    redis.set(_revoked_key(payload["jti"]), "1", ex=settings.jwt_refresh_ttl_days * 86400)


@router.post("/admin/login", response_model=TokenPair)
def dealer_admin_login(
    body: AdminLoginIn,
    request: Request,
    db: Session = Depends(get_db),
    redis: redis_lib.Redis = Depends(get_redis),
) -> TokenPair:
    """Sign in to the DEALER back office.

    Its own table, its own token audience. The worker panel's login is a separate
    endpoint against a separate table; the two programmes share no accounts, so a
    person who works on both holds two logins.
    """
    ratelimit.enforce(redis, f"dealeradminlogin:{client_ip(request)}", limit=10, window_s=300)

    admin = db.execute(
        select(DealerAdmin).where(DealerAdmin.email == body.email.lower().strip())
    ).scalar_one_or_none()
    # Unconditional, and before the `admin is None` test: an unknown email must do
    # the same argon2 work as a known one. See _DUMMY_PASSWORD_HASH.
    password_ok = verify_password(
        body.password,
        admin.password_hash if admin is not None else _DUMMY_PASSWORD_HASH,
    )
    if admin is None or not password_ok:
        raise AppError("invalid_credentials", 401, "Incorrect email or password")
    if not admin.is_active:
        raise AppError("admin_disabled", 403, "This account has been disabled")

    return TokenPair(
        access_token=create_access_token(
            str(admin.id), "dealer_admin", {"role": admin.role, "name": admin.name}
        ),
        refresh_token=create_refresh_token(str(admin.id), "dealer_admin")[0],
        expires_in=settings.jwt_access_ttl_minutes * 60,
    )


@router.post("/admin/refresh", response_model=TokenPair)
def dealer_admin_refresh(
    body: RefreshIn,
    db: Session = Depends(get_db),
    redis: redis_lib.Redis = Depends(get_redis),
) -> TokenPair:
    payload = decode_token(body.refresh_token, expected_aud="dealer_admin", expected_type="refresh")
    if redis.exists(_revoked_key(payload["jti"])):
        raise AppError("invalid_token", 401, "Refresh token revoked")
    admin = db.get(DealerAdmin, payload["sub"])
    if admin is None or not admin.is_active:
        raise AppError("invalid_token", 401, "Unknown or disabled admin")
    redis.set(_revoked_key(payload["jti"]), "1", ex=settings.jwt_refresh_ttl_days * 86400)

    return TokenPair(
        access_token=create_access_token(
            str(admin.id), "dealer_admin", {"role": admin.role, "name": admin.name}
        ),
        refresh_token=create_refresh_token(str(admin.id), "dealer_admin")[0],
        expires_in=settings.jwt_access_ttl_minutes * 60,
    )
