"""The dealer's own-account surface: rewards, redemptions, profile, ledger.

One module because these four are one screen group in the dealer app — "my
shop", everything the dealer can see about themselves — and they share the
points vocabulary (balance / pending / available) that must read identically on
every one of those screens.
"""

import uuid
from datetime import datetime

from pydantic import Field, field_validator

from app.dealer.schemas.common import Base, Page

# What a dealer should be told a ledger row means. `registration_credit` is an
# internal enum; on a shop-floor phone it is not an explanation. The label is
# derived at read time rather than stored, so renaming a label never means
# rewriting append-only history.
ENTRY_LABELS: dict[str, str] = {
    "registration_credit": "Warranty registered",
    "registration_reversal": "Registration reversed",
    "redemption_debit": "Reward redeemed",
    "redemption_release": "Redemption returned",
    "admin_credit": "Adjustment by GoodBed",
    "admin_debit": "Adjustment by GoodBed",
}


def entry_label(entry_type: str) -> str:
    return ENTRY_LABELS.get(entry_type, entry_type.replace("_", " ").capitalize())


# --- Catalogue -------------------------------------------------------------


class RewardOut(Base):
    id: uuid.UUID
    name: str
    description: str | None
    points_cost: int
    image_url: str | None
    # Stock is only decremented on approval, so this is "can still be requested",
    # not a reservation.
    in_stock: bool
    # Against AVAILABLE points, never the raw balance: points already committed
    # to a pending request cannot be spent a second time.
    affordable: bool
    # How many more points are needed. 0 when affordable — the app shows a
    # progress hint rather than a bare "you can't have this".
    short_by: int


class CatalogueOut(Base):
    balance: int
    pending: int
    available: int
    items: list[RewardOut]


# --- Redemptions -----------------------------------------------------------


class RedeemIn(Base):
    reward_id: uuid.UUID
    note: str | None = Field(default=None, max_length=500)


class RedemptionOut(Base):
    id: uuid.UUID
    reward_id: uuid.UUID | None
    # Frozen at request time — this is what was asked for, even if the catalogue
    # entry has since been renamed, repriced or retired.
    reward_name: str | None
    points: int
    status: str
    note: str | None
    created_at: datetime
    processed_at: datetime | None


class RedemptionPage(Page):
    items: list[RedemptionOut]


# --- Profile ---------------------------------------------------------------


class StaffOut(Base):
    id: uuid.UUID
    name: str
    phone: str
    role: str


class DealerBrief(Base):
    id: uuid.UUID
    code: str
    name: str
    city: str | None
    state: str | None
    status: str


class PointsOut(Base):
    balance: int
    pending: int
    available: int
    total_earned: int


class ProfileOut(Base):
    staff: StaffOut
    dealer: DealerBrief
    points: PointsOut
    # The compliance number the dealer is actually judged on, shown to them
    # rather than only to the brand.
    registrations_this_month: int


class ProfileUpdateIn(Base):
    name: str = Field(min_length=1, max_length=200)

    @field_validator("name")
    @classmethod
    def _strip(cls, v: str) -> str:
        cleaned = v.strip()
        if not cleaned:
            raise ValueError("Name cannot be blank")
        return cleaned


# --- Ledger ----------------------------------------------------------------


class LedgerEntryOut(Base):
    id: uuid.UUID
    amount: int
    type: str
    label: str
    # The sale this row came from, so "why was I paid 50 on Tuesday?" is
    # answerable without a support ticket.
    serial: str | None
    reward_name: str | None
    reason: str | None
    created_at: datetime


class LedgerPage(Page):
    balance: int
    items: list[LedgerEntryOut]
