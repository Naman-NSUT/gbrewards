"""Dealer self-signup.

A shop registers itself: the first person to sign up creates the dealership and
becomes its owner. Nobody is provisioned by an admin.

THE ONE RULE THIS FILE EXISTS TO ENFORCE: nothing is written to the database
until the phone number is proven. The details a shop types are held in Redis
against the OTP and only become rows once the code is verified.

That is not theoretical caution. The system this one sits beside creates or
UPDATES its user row on the OTP *request*, before any verification — so anyone
who knows a registered number can overwrite that user's name and address with no
authentication at all. Staging avoids inheriting the same hole.
"""

import json
import uuid
from dataclasses import asdict, dataclass

from redis import Redis
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.dealer.models.dealer import Dealer, DealerStaff

# Long enough to survive a slow SMS and a customer at the counter, short enough
# that abandoned signups do not linger.
STAGE_TTL_SECONDS = 900


@dataclass(frozen=True)
class PendingSignup:
    phone: str
    name: str
    shop_name: str
    city: str | None = None
    address: str | None = None
    pincode: str | None = None
    gst_number: str | None = None


def _key(phone: str) -> str:
    return f"signup:pending:{phone}"


def stage(redis: Redis, signup: PendingSignup) -> None:
    """Hold the typed details until the OTP proves the phone. Writes nothing."""
    redis.set(_key(signup.phone), json.dumps(asdict(signup)), ex=STAGE_TTL_SECONDS)


def take(redis: Redis, phone: str) -> PendingSignup | None:
    """Fetch and consume a staged signup, if one is waiting for this phone."""
    raw = redis.get(_key(phone))
    if raw is None:
        return None
    redis.delete(_key(phone))
    return PendingSignup(**json.loads(raw))


def _next_code(session: Session) -> str:
    """A short, human-quotable dealer code.

    Sequential rather than random because staff read these down the phone, and
    'D0007' survives that where a random string does not. The count is a
    starting point, not an identity: the loop below settles collisions, and the
    unique constraint is what actually guarantees it.
    """
    base = int(session.execute(select(func.count()).select_from(Dealer)).scalar_one()) + 1
    for offset in range(1000):
        code = f"D{base + offset:04d}"
        exists = session.execute(
            select(Dealer.id).where(func.lower(Dealer.code) == code.lower())
        ).scalar_one_or_none()
        if exists is None:
            return code
    return f"D{uuid.uuid4().hex[:8].upper()}"


def create_from_signup(
    session: Session, signup: PendingSignup, *, auto_approve: bool
) -> tuple[Dealer, DealerStaff]:
    """Turn a verified signup into a dealership and its first staff member.

    The shop starts 'pending' unless auto-approval is configured: it can register
    sales immediately, because capturing the sale is the product and must not
    wait on anyone, but it cannot redeem until a human has looked at it once.
    """
    existing = session.execute(
        select(DealerStaff).where(DealerStaff.phone == signup.phone)
    ).scalar_one_or_none()
    if existing is not None:
        # Signup raced a signup. The phone already logs in somewhere, so this is
        # a login, not a new shop.
        raise AppError("already_registered", 409, "This number already has an account")

    dealer = Dealer(
        code=_next_code(session),
        name=signup.shop_name,
        phone=signup.phone,
        city=signup.city,
        address=signup.address,
        pincode=signup.pincode,
        gst_number=signup.gst_number,
        status="active" if auto_approve else "pending",
    )
    session.add(dealer)
    session.flush()

    staff = DealerStaff(
        dealer_id=dealer.id,
        phone=signup.phone,
        name=signup.name,
        # Whoever signs the shop up owns it and can add colleagues later.
        role="owner",
    )
    session.add(staff)
    session.flush()
    return dealer, staff
