"""Dealer and staff administration.

Staff accounts are created HERE and nowhere else. There is no self-registration
anywhere in this system: dealers are contracted businesses, and every
registration a staff login makes pays points. An open sign-up on a paying
system is an open till — see services/otp.py for the same reasoning on the login
side.
"""

import uuid

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy import Select, func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.deps import client_ip, get_current_dealer_admin, get_db, require_admin_write
from app.core.errors import AppError
from app.dealer.api.admin._common import Pagination, count_of, like, pagination
from app.dealer.models.admin import DealerAdmin as Admin
from app.dealer.models.allocation import Allocation
from app.dealer.models.dealer import Dealer, DealerStaff
from app.dealer.models.ledger_entry import LedgerEntry
from app.dealer.models.warranty import Warranty
from app.dealer.schemas.admin import (
    DealerDetailOut,
    DealerIn,
    DealerListItem,
    DealerOut,
    DealerStatsOut,
    DealerUpdateIn,
    Paginated,
    PointsSummaryOut,
    ReasonIn,
    StaffIn,
    StaffOut,
    StaffUpdateIn,
)
from app.dealer.schemas.common import Ok
from app.dealer.services import ledger
from app.dealer.services.audit import record_audit

router = APIRouter(tags=["admin-dealers"])


def _dealer_list_query() -> Select[tuple[Dealer, int, int]]:
    # Correlated subqueries rather than a per-row lookup: the dealer list is the
    # first screen of the panel and it must be one round-trip whatever the size
    # of the dealer network.
    staff_count = (
        select(func.count(DealerStaff.id))
        .where(DealerStaff.dealer_id == Dealer.id, DealerStaff.is_active.is_(True))
        .correlate(Dealer)
        .scalar_subquery()
    )
    balance = (
        select(func.coalesce(func.sum(LedgerEntry.amount), 0))
        .where(LedgerEntry.dealer_id == Dealer.id)
        .correlate(Dealer)
        .scalar_subquery()
    )
    return select(
        Dealer, staff_count.label("staff_count"), balance.label("points_balance")
    )


def _get_dealer(db: Session, dealer_id: uuid.UUID) -> Dealer:
    dealer = db.get(Dealer, dealer_id)
    if dealer is None:
        raise AppError("dealer_not_found", 404, "No such dealer")
    return dealer


@router.get("/dealers", response_model=Paginated[DealerListItem])
def list_dealers(
    q: str | None = Query(default=None, max_length=120),
    status: str | None = Query(default=None, pattern="^(active|suspended|closed)$"),
    page: Pagination = Depends(pagination),
    _: Admin = Depends(get_current_dealer_admin),
    db: Session = Depends(get_db),
) -> Paginated[DealerListItem]:
    stmt = _dealer_list_query()
    if q:
        term = like(q)
        stmt = stmt.where(
            or_(
                Dealer.code.ilike(term),
                Dealer.name.ilike(term),
                func.coalesce(Dealer.city, "").ilike(term),
            )
        )
    if status:
        stmt = stmt.where(Dealer.status == status)

    total = count_of(db, stmt)
    rows = db.execute(
        stmt.order_by(Dealer.code.asc()).limit(page.limit).offset(page.offset)
    ).all()
    return Paginated[DealerListItem](
        items=[
            DealerListItem(
                **DealerOut.model_validate(dealer).model_dump(),
                staff_count=int(staff_count),
                points_balance=int(balance),
            )
            for dealer, staff_count, balance in rows
        ],
        total=total,
        limit=page.limit,
        offset=page.offset,
    )


@router.post("/dealers", response_model=DealerOut, status_code=201)
def create_dealer(
    body: DealerIn,
    request: Request,
    admin: Admin = Depends(require_admin_write),
    db: Session = Depends(get_db),
) -> Dealer:
    code = body.code.strip()
    # Case-insensitive uniqueness. The allocation upload matches dealer codes
    # case-insensitively (a despatch export writes 'd001' for 'D001'), so
    # allowing both to exist would make that match ambiguous.
    clash = db.execute(
        select(Dealer).where(func.upper(Dealer.code) == code.upper())
    ).scalar_one_or_none()
    if clash is not None:
        raise AppError(
            "dealer_code_taken", 409, f"Dealer code '{clash.code}' already exists"
        )

    dealer = Dealer(**{**body.model_dump(), "code": code})
    db.add(dealer)
    try:
        db.flush()
    except IntegrityError as exc:  # concurrent create of the same code
        db.rollback()
        raise AppError("dealer_code_taken", 409, "That dealer code already exists") from exc

    record_audit(
        db,
        action="create_dealer",
        entity_type="dealer",
        entity_id=dealer.id,
        actor_id=admin.id,
        ip=client_ip(request),
        metadata={"code": dealer.code, "name": dealer.name},
    )
    db.commit()
    return dealer


@router.get("/dealers/{dealer_id}", response_model=DealerDetailOut)
def get_dealer(
    dealer_id: uuid.UUID,
    _: Admin = Depends(get_current_dealer_admin),
    db: Session = Depends(get_db),
) -> DealerDetailOut:
    dealer = _get_dealer(db, dealer_id)
    staff = list(
        db.execute(
            select(DealerStaff)
            .where(DealerStaff.dealer_id == dealer.id)
            .order_by(DealerStaff.created_at.asc())
        ).scalars()
    )

    allocated = db.execute(
        select(func.count(Allocation.id)).where(
            Allocation.dealer_id == dealer.id, Allocation.status != "revoked"
        )
    ).scalar_one()
    unregistered = db.execute(
        select(func.count(Allocation.id)).where(
            Allocation.dealer_id == dealer.id, Allocation.status == "allocated"
        )
    ).scalar_one()
    registered, voided, last_at = db.execute(
        select(
            func.count(Warranty.id).filter(Warranty.status != "voided"),
            func.count(Warranty.id).filter(Warranty.status == "voided"),
            func.max(Warranty.registered_at),
        ).where(Warranty.dealer_id == dealer.id)
    ).one()
    # Self-registrations against stock this dealer holds — the non-compliance
    # signal, repeated here so the dealer page tells the same story as the
    # compliance screen.
    self_registered = db.execute(
        select(func.count(Warranty.id))
        .select_from(Warranty)
        .join(Allocation, Allocation.serial == Warranty.serial)
        .where(
            Allocation.dealer_id == dealer.id,
            Warranty.source == "customer_self",
            Warranty.status != "voided",
        )
    ).scalar_one()

    return DealerDetailOut(
        dealer=DealerOut.model_validate(dealer),
        staff=[StaffOut.model_validate(s) for s in staff],
        points=PointsSummaryOut(
            balance=ledger.balance(db, dealer.id),
            pending=ledger.pending(db, dealer.id),
            available=ledger.available(db, dealer.id),
            total_earned=ledger.total_earned(db, dealer.id),
        ),
        stats=DealerStatsOut(
            units_allocated=int(allocated),
            units_unregistered=int(unregistered),
            warranties_registered=int(registered),
            warranties_voided=int(voided),
            self_registrations=int(self_registered),
            last_registration_at=last_at,
        ),
    )


@router.patch("/dealers/{dealer_id}", response_model=DealerOut)
def update_dealer(
    dealer_id: uuid.UUID,
    body: DealerUpdateIn,
    request: Request,
    admin: Admin = Depends(require_admin_write),
    db: Session = Depends(get_db),
) -> Dealer:
    dealer = _get_dealer(db, dealer_id)
    changes = body.model_dump(exclude_unset=True)
    if not changes:
        raise AppError("nothing_to_update", 400, "No fields supplied")

    before = {field: getattr(dealer, field) for field in changes}
    for field, value in changes.items():
        setattr(dealer, field, value)

    record_audit(
        db,
        action="update_dealer",
        entity_type="dealer",
        entity_id=dealer.id,
        actor_id=admin.id,
        ip=client_ip(request),
        metadata={"before": before, "after": changes},
    )
    db.commit()
    return dealer


@router.post("/dealers/{dealer_id}/suspend", response_model=DealerOut)
def suspend_dealer(
    dealer_id: uuid.UUID,
    body: ReasonIn,
    request: Request,
    admin: Admin = Depends(require_admin_write),
    db: Session = Depends(get_db),
) -> Dealer:
    """Stop a dealership earning.

    No token revocation is needed: get_current_staff re-reads the dealership on
    every request and refuses a token whose dealer is not active, so a staff
    session issued before the suspension dies at its next call.
    """
    dealer = _get_dealer(db, dealer_id)
    if dealer.status == "suspended":
        return dealer

    previous = dealer.status
    dealer.status = "suspended"
    record_audit(
        db,
        action="suspend_dealer",
        entity_type="dealer",
        entity_id=dealer.id,
        actor_id=admin.id,
        reason=body.reason,
        ip=client_ip(request),
        metadata={"from": previous},
    )
    db.commit()
    return dealer


@router.post("/dealers/{dealer_id}/reactivate", response_model=DealerOut)
def reactivate_dealer(
    dealer_id: uuid.UUID,
    request: Request,
    admin: Admin = Depends(require_admin_write),
    db: Session = Depends(get_db),
) -> Dealer:
    dealer = _get_dealer(db, dealer_id)
    previous = dealer.status
    dealer.status = "active"
    record_audit(
        db,
        action="reactivate_dealer",
        entity_type="dealer",
        entity_id=dealer.id,
        actor_id=admin.id,
        ip=client_ip(request),
        metadata={"from": previous},
    )
    db.commit()
    return dealer


# --- Staff -----------------------------------------------------------------


@router.get("/dealers/{dealer_id}/staff", response_model=list[StaffOut])
def list_staff(
    dealer_id: uuid.UUID,
    include_inactive: bool = Query(default=True),
    _: Admin = Depends(get_current_dealer_admin),
    db: Session = Depends(get_db),
) -> list[DealerStaff]:
    _get_dealer(db, dealer_id)
    stmt = select(DealerStaff).where(DealerStaff.dealer_id == dealer_id)
    if not include_inactive:
        stmt = stmt.where(DealerStaff.is_active.is_(True))
    return list(db.execute(stmt.order_by(DealerStaff.created_at.asc())).scalars())


@router.post("/dealers/{dealer_id}/staff", response_model=StaffOut, status_code=201)
def create_staff(
    dealer_id: uuid.UUID,
    body: StaffIn,
    request: Request,
    admin: Admin = Depends(require_admin_write),
    db: Session = Depends(get_db),
) -> DealerStaff:
    dealer = _get_dealer(db, dealer_id)
    if dealer.status == "closed":
        raise AppError("dealer_closed", 409, "Cannot add staff to a closed dealership")

    # Phone is the login identity and is unique across every dealership, so a
    # clash is almost always "this person moved shops", not a duplicate.
    existing = db.execute(
        select(DealerStaff).where(DealerStaff.phone == body.phone)
    ).scalar_one_or_none()
    if existing is not None:
        raise AppError(
            "phone_taken",
            409,
            "That number already belongs to a staff account",
            {"dealer_id": str(existing.dealer_id), "is_active": existing.is_active},
        )

    staff = DealerStaff(
        dealer_id=dealer.id, name=body.name, phone=body.phone, role=body.role
    )
    db.add(staff)
    try:
        db.flush()
    except IntegrityError as exc:
        db.rollback()
        raise AppError("phone_taken", 409, "That number is already registered") from exc

    record_audit(
        db,
        action="create_staff",
        entity_type="dealer_staff",
        entity_id=staff.id,
        actor_id=admin.id,
        ip=client_ip(request),
        metadata={"dealer_id": str(dealer.id), "phone": staff.phone, "role": staff.role},
    )
    db.commit()
    return staff


@router.patch("/dealers/{dealer_id}/staff/{staff_id}", response_model=StaffOut)
def update_staff(
    dealer_id: uuid.UUID,
    staff_id: uuid.UUID,
    body: StaffUpdateIn,
    request: Request,
    admin: Admin = Depends(require_admin_write),
    db: Session = Depends(get_db),
) -> DealerStaff:
    staff = _get_staff(db, dealer_id, staff_id)
    changes = body.model_dump(exclude_unset=True)
    if not changes:
        raise AppError("nothing_to_update", 400, "No fields supplied")

    before = {field: getattr(staff, field) for field in changes}
    for field, value in changes.items():
        setattr(staff, field, value)

    record_audit(
        db,
        action="deactivate_staff" if changes.get("is_active") is False else "update_staff",
        entity_type="dealer_staff",
        entity_id=staff.id,
        actor_id=admin.id,
        ip=client_ip(request),
        metadata={"before": before, "after": changes},
    )
    db.commit()
    return staff


@router.delete("/dealers/{dealer_id}/staff/{staff_id}", response_model=Ok)
def deactivate_staff(
    dealer_id: uuid.UUID,
    staff_id: uuid.UUID,
    request: Request,
    admin: Admin = Depends(require_admin_write),
    db: Session = Depends(get_db),
) -> Ok:
    """Soft delete, always.

    The row is referenced by every warranty that person registered and by their
    ledger entries. Deleting it would erase the attribution that makes abuse
    investigation possible; deactivating it just stops the login.
    """
    staff = _get_staff(db, dealer_id, staff_id)
    if staff.is_active:
        staff.is_active = False
        record_audit(
            db,
            action="deactivate_staff",
            entity_type="dealer_staff",
            entity_id=staff.id,
            actor_id=admin.id,
            ip=client_ip(request),
            metadata={"dealer_id": str(dealer_id), "phone": staff.phone},
        )
        db.commit()
    return Ok()


def _get_staff(db: Session, dealer_id: uuid.UUID, staff_id: uuid.UUID) -> DealerStaff:
    staff = db.get(DealerStaff, staff_id)
    if staff is None or staff.dealer_id != dealer_id:
        raise AppError("staff_not_found", 404, "No such staff member for this dealer")
    return staff
