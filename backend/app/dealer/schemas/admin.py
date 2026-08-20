"""Request and response models for the admin API.

Two conventions hold across every screen:

  * One pagination envelope — {items, total, limit, offset}. The admin panel has
    a dozen list screens and a second shape would mean a second table component.
  * Warranty status is reported TWICE: `status` is what a human should be told
    (expiry folded in by warranty.display_status) and `stored_status` is the raw
    column. Filters key off the stored value; humans read the display value. One
    field carrying both meanings is how an expired warranty ends up displayed as
    'active' on one screen and 'expired' on another.
"""

import uuid
from datetime import date, datetime
from typing import Any

from pydantic import Field

from app.dealer.schemas.common import Base, PhoneMixin


class Paginated[T](Base):
    items: list[T]
    total: int
    limit: int
    offset: int


class ReasonIn(Base):
    # Three characters is not a real explanation, but it is enough to stop "x"
    # while staying out of the way of "returned" or "duplicate scan".
    reason: str = Field(min_length=3, max_length=1000)


# --- Shared briefs ---------------------------------------------------------


class DealerBrief(Base):
    id: uuid.UUID
    code: str
    name: str
    status: str
    city: str | None = None


class StaffBrief(Base):
    id: uuid.UUID
    name: str
    phone: str
    role: str


class CustomerBrief(Base):
    id: uuid.UUID
    name: str
    phone: str


class AdminBrief(Base):
    id: uuid.UUID
    name: str
    email: str
    role: str


# --- Dealers ---------------------------------------------------------------


class DealerIn(Base):
    code: str = Field(min_length=1, max_length=32)
    name: str = Field(min_length=1, max_length=200)
    # Deliberately NOT run through normalise_phone: a dealership's contact
    # number is often a landline, and rejecting one would block creating a real
    # dealer. Staff phones are logins and are normalised — see StaffIn.
    phone: str | None = Field(default=None, max_length=20)
    email: str | None = Field(default=None, max_length=200)
    address: str | None = Field(default=None, max_length=400)
    city: str | None = Field(default=None, max_length=100)
    state: str | None = Field(default=None, max_length=100)
    pincode: str | None = Field(default=None, max_length=10)
    gst_number: str | None = Field(default=None, max_length=20)


class DealerUpdateIn(Base):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    phone: str | None = Field(default=None, max_length=20)
    email: str | None = Field(default=None, max_length=200)
    address: str | None = Field(default=None, max_length=400)
    city: str | None = Field(default=None, max_length=100)
    state: str | None = Field(default=None, max_length=100)
    pincode: str | None = Field(default=None, max_length=10)
    gst_number: str | None = Field(default=None, max_length=20)


class DealerOut(Base):
    id: uuid.UUID
    code: str
    name: str
    phone: str | None
    email: str | None
    address: str | None
    city: str | None
    state: str | None
    pincode: str | None
    gst_number: str | None
    status: str
    created_at: datetime


class DealerListItem(DealerOut):
    staff_count: int
    points_balance: int


class PointsSummaryOut(Base):
    balance: int
    pending: int
    available: int
    total_earned: int


class DealerStatsOut(Base):
    warranties_registered: int
    warranties_voided: int
    self_registrations: int
    last_registration_at: datetime | None


class StaffIn(PhoneMixin, Base):
    name: str = Field(min_length=1, max_length=200)
    # A login identity, so it must be a real mobile: normalised to E.164 by
    # PhoneMixin and unique across every dealership.
    phone: str = Field(min_length=6, max_length=20)
    role: str = Field(default="staff", pattern="^(owner|staff)$")


class StaffUpdateIn(Base):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    role: str | None = Field(default=None, pattern="^(owner|staff)$")
    is_active: bool | None = None


class StaffOut(Base):
    id: uuid.UUID
    dealer_id: uuid.UUID
    name: str
    phone: str
    role: str
    is_active: bool
    last_active_at: datetime | None
    created_at: datetime


class DealerDetailOut(Base):
    dealer: DealerOut
    staff: list[StaffOut]
    points: PointsSummaryOut
    stats: DealerStatsOut


# --- Allocations -----------------------------------------------------------


class WarrantyListItem(Base):
    id: uuid.UUID
    serial: str
    model_name: str | None
    model_code: str | None
    status: str
    stored_status: str
    source: str
    warranty_months: int
    warranty_start_date: date
    warranty_end_date: date
    backdate_days: int
    unit_unverified: bool
    invoice_ref: str | None
    invoice_date: date | None
    registered_at: datetime
    customer: CustomerBrief | None = None
    dealer: DealerBrief | None = None


class CustomerOut(Base):
    id: uuid.UUID
    name: str
    phone: str
    email: str | None
    address: str | None
    city: str | None
    state: str | None
    pincode: str | None
    is_phone_verified: bool


class WarrantyEventOut(Base):
    id: uuid.UUID
    warranty_id: uuid.UUID
    event: str
    from_status: str | None
    to_status: str | None
    actor_type: str
    actor_id: uuid.UUID | None
    actor_name: str | None = None
    reason: str | None
    metadata: dict[str, Any] | None = None
    created_at: datetime


class LedgerEntryOut(Base):
    id: uuid.UUID
    dealer_id: uuid.UUID
    amount: int
    type: str
    warranty_id: uuid.UUID | None
    redemption_id: uuid.UUID | None
    rate_version_id: uuid.UUID | None
    admin_id: uuid.UUID | None
    staff_id: uuid.UUID | None
    reason: str | None
    metadata: dict[str, Any] | None = None
    created_at: datetime
    # Balance AFTER this entry, computed over the dealer's whole history — the
    # column an accountant looks for and cannot reconstruct from a page of rows.
    balance_after: int | None = None


class ClaimBrief(Base):
    id: uuid.UUID
    reference: str
    status: str
    issue_type: str | None
    created_at: datetime


class WarrantyDetailOut(Base):
    warranty: WarrantyListItem
    is_expired: bool
    customer: CustomerOut
    dealer: DealerBrief | None
    staff: StaffBrief | None
    events: list[WarrantyEventOut]
    ledger_entries: list[LedgerEntryOut]
    claims: list[ClaimBrief]
    void_reason: str | None = None
    voided_at: datetime | None = None
    proof_file_key: str | None = None


class VoidWarrantyIn(ReasonIn):
    # Default true: a voided registration that keeps its points is a paid-for
    # sale that did not happen. Turning it off is the exception (a data fix on a
    # genuine sale), which is why it is an explicit flag on an audited action.
    clawback: bool = True
    notify_customer: bool = False


class EditCustomerIn(PhoneMixin, ReasonIn):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    # Changing the phone REPOINTS the warranty at the customer who owns that
    # number, creating them if new. A mistyped number is the single most common
    # support ticket: the buyer cannot find their own warranty.
    phone: str | None = Field(default=None, min_length=6, max_length=20)
    email: str | None = Field(default=None, max_length=200)
    address: str | None = Field(default=None, max_length=400)
    city: str | None = Field(default=None, max_length=100)
    state: str | None = Field(default=None, max_length=100)
    pincode: str | None = Field(default=None, max_length=10)


# --- Approvals -------------------------------------------------------------


class ApprovalItem(Base):
    """A warranty waiting on a human, with the evidence to decide it."""

    id: uuid.UUID
    serial: str
    model_name: str | None
    status: str
    source: str
    warranty_months: int
    warranty_start_date: date
    warranty_end_date: date
    invoice_ref: str | None
    # What the dealer claimed, kept even when not honoured.
    requested_invoice_date: date | None
    days_back: int
    registered_at: datetime
    waiting_days: int
    unit_unverified: bool
    # Self-registrations carry a photo of the bill; a backdate request does not.
    proof_file_key: str | None
    customer: CustomerBrief
    dealer: DealerBrief | None
    # 'warranty' when the dealer registered it, 'allocation' when we inferred the
    # seller from who holds the serial (a customer self-registration names no
    # dealer — that inference IS the non-compliance report).
    dealer_source: str | None
    staff: StaffBrief | None


class ApproveIn(ReasonIn):
    # False means "the sale is real but the claimed date is not": the clock is
    # reset to today rather than the whole registration being thrown away.
    honour_requested_date: bool = True


# --- Compliance ------------------------------------------------------------


class ComplianceRowOut(Base):
    dealer_id: uuid.UUID
    dealer_code: str
    dealer_name: str
    city: str | None
    dealer_status: str
    warranties_registered: int
    self_registrations: int
    backdated_registrations: int
    last_registration_at: datetime | None
    days_since_last_registration: int | None
    non_compliance_score: float


class ComplianceTotalsOut(Base):
    dealers: int
    warranties_registered: int
    self_registrations: int


class ComplianceOut(Base):
    items: list[ComplianceRowOut]
    total: int
    limit: int
    offset: int
    date_from: date | None
    date_to: date | None
    sort: str
    totals: ComplianceTotalsOut


class SelfRegistrationOut(Base):
    warranty_id: uuid.UUID
    serial: str
    status: str
    registered_at: datetime
    invoice_date: date | None
    proof_file_key: str | None
    customer: CustomerBrief


class StaffActivityOut(Base):
    staff: StaffBrief
    is_active: bool
    last_active_at: datetime | None
    registrations: int


class DealerComplianceDetailOut(Base):
    dealer: DealerBrief
    summary: ComplianceRowOut
    date_from: date | None
    date_to: date | None
    self_registrations: list[SelfRegistrationOut]
    staff_activity: list[StaffActivityOut]


# --- Points ----------------------------------------------------------------


class PointRateOut(Base):
    id: uuid.UUID
    points_per_registration: int
    effective_from: datetime
    effective_to: datetime | None
    note: str | None
    created_by_admin_id: uuid.UUID | None
    is_current: bool = False


class DealerProductIn(Base):
    name: str = Field(min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=2000)
    # Printed on the physical label under the QR.
    terms: str | None = Field(default=None, max_length=2000)
    model_code: str | None = Field(default=None, max_length=64)
    warranty_months: int = Field(default=60, gt=0, le=600)
    is_active: bool = True


class DealerProductOut(Base):
    id: uuid.UUID
    name: str
    description: str | None
    terms: str | None
    model_code: str | None
    warranty_months: int
    is_active: bool
    # How many serials have been minted for this product so far.
    units_generated: int


class GenerateBatchIn(Base):
    quantity: int = Field(gt=0, le=10_000)
    label: str | None = Field(default=None, max_length=200)


class QrBatchOut(Base):
    id: uuid.UUID
    product_id: uuid.UUID
    quantity: int
    label: str | None
    created_at: datetime


class ProductRateOut(Base):
    """A product and what registering it currently pays a dealer."""

    product_id: uuid.UUID
    product_name: str
    is_active: bool
    warranty_months: int | None
    points_per_registration: int | None
    rate_id: uuid.UUID | None
    effective_from: datetime | None


class SetRateIn(Base):
    product_id: uuid.UUID
    points_per_registration: int = Field(ge=0, le=1_000_000)
    note: str | None = Field(default=None, max_length=1000)


class AdjustPointsIn(ReasonIn):
    # Signed. Positive credits the dealer, negative claws back. Zero is rejected
    # by ledger.add_entry — an entry that moves nothing only muddies the history.
    amount: int = Field(ge=-1_000_000, le=1_000_000)


class AdjustPointsOut(Base):
    entry: LedgerEntryOut
    points: PointsSummaryOut


class DealerLedgerOut(Base):
    dealer: DealerBrief
    points: PointsSummaryOut
    items: list[LedgerEntryOut]
    total: int
    limit: int
    offset: int


# --- SMS -------------------------------------------------------------------


class SmsOut(Base):
    id: uuid.UUID
    to_phone: str
    template_key: str
    provider: str
    provider_template_id: str | None
    provider_message_id: str | None
    variables: dict[str, Any] | None
    status: str
    error: str | None
    attempts: int
    warranty_id: uuid.UUID | None
    created_at: datetime
    sent_at: datetime | None
    delivered_at: datetime | None
    # The rendered text, reconstructed from the template and the stored
    # variables. Not stored twice: the body is derivable, PII is not duplicated.
    preview: str | None = None


# --- Rewards ---------------------------------------------------------------


class RewardIn(Base):
    name: str = Field(min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=2000)
    points_cost: int = Field(gt=0, le=10_000_000)
    image_url: str | None = Field(default=None, max_length=600)
    stock: int | None = Field(default=None, ge=0)
    is_active: bool = True
    sort_order: int = 0


class RewardUpdateIn(Base):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=2000)
    points_cost: int | None = Field(default=None, gt=0, le=10_000_000)
    image_url: str | None = Field(default=None, max_length=600)
    stock: int | None = Field(default=None, ge=0)
    is_active: bool | None = None
    sort_order: int | None = None


class RewardOut(Base):
    id: uuid.UUID
    name: str
    description: str | None
    points_cost: int
    image_url: str | None
    stock: int | None
    is_active: bool
    sort_order: int
    created_at: datetime
    updated_at: datetime


class RedemptionOut(Base):
    id: uuid.UUID
    dealer: DealerBrief
    requested_by: StaffBrief | None
    reward_id: uuid.UUID | None
    reward_name: str | None
    points: int
    status: str
    note: str | None
    processed_by_admin_id: uuid.UUID | None
    processed_at: datetime | None
    created_at: datetime


class RedemptionDecisionOut(Base):
    redemption: RedemptionOut
    points: PointsSummaryOut


class RedemptionNoteIn(Base):
    note: str | None = Field(default=None, max_length=1000)


# --- Audit -----------------------------------------------------------------


class AuditOut(Base):
    id: uuid.UUID
    actor_type: str
    actor_id: uuid.UUID | None
    actor_name: str | None
    actor_label: str | None
    action: str
    entity_type: str
    entity_id: uuid.UUID | None
    reason: str | None
    metadata: dict[str, Any] | None
    ip: str | None
    created_at: datetime


# --- Claims ----------------------------------------------------------------


class ClaimListItem(Base):
    id: uuid.UUID
    reference: str
    status: str
    issue_type: str | None
    description: str
    warranty_id: uuid.UUID
    serial: str
    model_name: str | None
    customer: CustomerBrief
    dealer: DealerBrief | None
    warranty_end_date: date
    # Whether the mattress was still under warranty on the day the claim was
    # raised. The first question anyone asks, and a date subtraction nobody
    # should be doing by hand on a support call.
    in_warranty: bool
    handled_by_admin_id: uuid.UUID | None
    resolved_at: datetime | None
    created_at: datetime


class ClaimDetailOut(Base):
    claim: ClaimListItem
    resolution_note: str | None
    warranty: WarrantyListItem
    customer: CustomerOut


class ClaimUpdateIn(Base):
    status: str = Field(pattern="^(open|in_review|approved|rejected|closed)$")
    resolution_note: str | None = Field(default=None, max_length=2000)


# --- Unified serial lookup -------------------------------------------------


class UnitOut(Base):
    known: bool
    serial: str
    model_name: str | None = None
    model_code: str | None = None
    warranty_months: int | None = None
    source: str | None = None
    source_status: str | None = None
    source_synced_at: datetime | None = None
    # True when the row is a local stub (an allocation upload invented it) and
    # GB Rewards has never confirmed the unit exists.
    unverified: bool = True
    # True when upstream facts are older than UNIT_MIRROR_STALENESS_HOURS.
    stale: bool = False


class SerialLookupOut(Base):
    """Everything known about one serial, in one response.

    Support staff live on this screen. Anything missing here becomes a second
    query in a second tab while a customer waits on the phone.
    """

    serial: str
    unit: UnitOut
    current_warranty: WarrantyDetailOut | None
    warranties: list[WarrantyListItem]
    claims: list[ClaimListItem]
    sms: list[SmsOut]
    events: list[WarrantyEventOut]
