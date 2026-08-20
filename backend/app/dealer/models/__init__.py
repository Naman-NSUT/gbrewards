"""Dealer programme models.

Nothing here is shared with the worker programme. Every table the dealer side
touches is its own — including its admins, its product catalogue, its unit
registry and its audit trail. There are no foreign keys into the worker schema.

A mattress therefore carries two QR labels: `product_units.token` for the worker
app, `dealer_units.token` for the dealer app. The two serials are unrelated.
"""

from app.dealer.models.admin import DealerAdmin
from app.dealer.models.audit_log import DealerAuditLog
from app.dealer.models.claim import Claim
from app.dealer.models.customer import Customer
from app.dealer.models.dealer import Dealer, DealerStaff
from app.dealer.models.idempotency import IdempotencyKey
from app.dealer.models.ledger_entry import LedgerEntry
from app.dealer.models.point_rate import PointRate
from app.dealer.models.product import DealerProduct
from app.dealer.models.reward import Redemption, Reward
from app.dealer.models.sms_message import SmsMessage
from app.dealer.models.unit import DealerQrBatch, DealerUnit
from app.dealer.models.warranty import Warranty, WarrantyEvent

__all__ = [
    "Claim",
    "Customer",
    "Dealer",
    "DealerAdmin",
    "DealerAuditLog",
    "DealerProduct",
    "DealerQrBatch",
    "DealerStaff",
    "DealerUnit",
    "IdempotencyKey",
    "LedgerEntry",
    "PointRate",
    "Redemption",
    "Reward",
    "SmsMessage",
    "Warranty",
    "WarrantyEvent",
]
