"""Dealer-side models.

Shared with the worker side and imported from app.models: Admin, Product,
ProductUnit. Everything here is dealer-only. Tables that would have collided
with the worker schema carry a `dealer_` prefix (see the 0008 migration).
"""

from app.dealer.models.allocation import Allocation, AllocationBatch
from app.dealer.models.claim import Claim
from app.dealer.models.customer import Customer
from app.dealer.models.dealer import Dealer, DealerStaff
from app.dealer.models.idempotency import IdempotencyKey
from app.dealer.models.ledger_entry import LedgerEntry
from app.dealer.models.point_rate import PointRate
from app.dealer.models.reward import Redemption, Reward
from app.dealer.models.sms_message import SmsMessage
from app.dealer.models.warranty import Warranty, WarrantyEvent

__all__ = [
    "Allocation",
    "AllocationBatch",
    "Claim",
    "Customer",
    "Dealer",
    "DealerStaff",
    "IdempotencyKey",
    "LedgerEntry",
    "PointRate",
    "Redemption",
    "Reward",
    "SmsMessage",
    "Warranty",
    "WarrantyEvent",
]
