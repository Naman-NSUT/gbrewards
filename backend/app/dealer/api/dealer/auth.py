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
)
from app.dealer.models.dealer import Dealer, DealerStaff
from app.dealer.schemas.common import Base, PhoneMixin
from app.dealer.services import otp, ratelimit

router = APIRouter(prefix="/auth", tags=["dealer-auth"])


class OtpRequestIn(PhoneMixin, Base):
    phone: str = Field(min_length=6, max_length=20)


class OtpRequestOut(Base):
    resend_in: int


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
    """Send a login code to a KNOWN dealer staff number.

    Nothing about the account is created or modified here — see services/otp.py
    for why that matters.
    """
    ratelimit.enforce(redis, f"otp:ip:{client_ip(request)}", limit=20, window_s=3600)

    staff = db.execute(
        select(DealerStaff).where(DealerStaff.phone == body.phone)
    ).scalar_one_or_none()

    # Same response either way: this endpoint must not reveal which numbers
    # belong to dealers.
    if staff is not None and staff.is_active:
        otp.issue(db, redis, body.phone)

    return OtpRequestOut(resend_in=settings.otp_resend_cooldown_seconds)


@router.post("/otp/verify", response_model=TokenPair)
def otp_verify(
    body: OtpVerifyIn,
    db: Session = Depends(get_db),
    redis: redis_lib.Redis = Depends(get_redis),
) -> TokenPair:
    otp.verify(redis, body.phone, body.code)

    staff = db.execute(
        select(DealerStaff).where(DealerStaff.phone == body.phone)
    ).scalar_one_or_none()
    if staff is None or not staff.is_active:
        raise AppError("account_not_found", 403, "No active dealer account for this number")

    dealer = db.get(Dealer, staff.dealer_id)
    if dealer is None or dealer.status != "active":
        raise AppError("dealer_inactive", 403, "This dealership is not active")

    return _issue_pair(staff, dealer)


def _issue_pair(staff: DealerStaff, dealer: Dealer) -> TokenPair:
    access = create_access_token(str(staff.id), "dealer", {"dealer_id": str(dealer.id)})
    refresh, _ = create_refresh_token(str(staff.id), "dealer")
    return TokenPair(
        access_token=access,
        refresh_token=refresh,
        expires_in=settings.jwt_access_ttl_minutes * 60,
        staff=StaffOut(
            id=str(staff.id), name=staff.name, phone=staff.phone, role=staff.role
        ),
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
    if dealer is None or dealer.status != "active":
        raise AppError("dealer_inactive", 403, "This dealership is not active")

    # Rotate: the presented refresh token is burned as it is exchanged.
    redis.set(
        _revoked_key(payload["jti"]), "1", ex=settings.jwt_refresh_ttl_days * 86400
    )
    return _issue_pair(staff, dealer)


@router.post("/logout", status_code=204)
def logout(body: RefreshIn, redis: redis_lib.Redis = Depends(get_redis)) -> None:
    payload = decode_token(body.refresh_token, expected_aud="dealer", expected_type="refresh")
    redis.set(_revoked_key(payload["jti"]), "1", ex=settings.jwt_refresh_ttl_days * 86400)


# NOTE: admin login is NOT redefined here. The worker back office already serves
# POST /api/v1/auth/admin/login against the same `admins` table, so the dealer
# panel signs in through that. Two endpoints minting tokens for one identity is
# how they drift apart.
