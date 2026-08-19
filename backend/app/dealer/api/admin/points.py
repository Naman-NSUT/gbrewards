"""Point rate versions, manual adjustments and the dealer ledger.

Nothing here ever updates a balance, because there is no balance to update: a
balance is SUM(ledger_entries.amount). Every endpoint appends a row, and the
rate is versioned rather than edited so a ledger entry written six months ago
can still explain its own amount.
"""

import uuid

from fastapi import APIRouter, Depends, Request
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.deps import (
    client_ip,
    get_current_dealer_admin,
    get_db,
    require_admin_write,
    require_owner,
)
from app.core.errors import AppError
from app.dealer.api.admin._common import Pagination, pagination
from app.dealer.models.admin import DealerAdmin as Admin
from app.dealer.models.dealer import Dealer
from app.dealer.models.ledger_entry import LedgerEntry
from app.dealer.models.point_rate import PointRate
from app.dealer.models.product import DealerProduct as Product
from app.dealer.schemas.admin import (
    AdjustPointsIn,
    AdjustPointsOut,
    DealerBrief,
    DealerLedgerOut,
    LedgerEntryOut,
    Paginated,
    PointRateOut,
    PointsSummaryOut,
    ProductRateOut,
    SetRateIn,
)
from app.dealer.services import ledger
from app.dealer.services.audit import record_audit

router = APIRouter(tags=["admin-points"])


def _rate_out(rate: PointRate) -> PointRateOut:
    return PointRateOut.model_validate(rate).model_copy(
        update={"is_current": rate.effective_to is None}
    )


def _summary(db: Session, dealer_id: uuid.UUID) -> PointsSummaryOut:
    return PointsSummaryOut(
        balance=ledger.balance(db, dealer_id),
        pending=ledger.pending(db, dealer_id),
        available=ledger.available(db, dealer_id),
        total_earned=ledger.total_earned(db, dealer_id),
    )


def _get_dealer(db: Session, dealer_id: uuid.UUID) -> Dealer:
    dealer = db.get(Dealer, dealer_id)
    if dealer is None:
        raise AppError("dealer_not_found", 404, "No such dealer")
    return dealer


def _brief(dealer: Dealer) -> DealerBrief:
    return DealerBrief(
        id=dealer.id,
        code=dealer.code,
        name=dealer.name,
        status=dealer.status,
        city=dealer.city,
    )


@router.get("/points/rates/current", response_model=list[ProductRateOut])
def current_rates(
    _: Admin = Depends(get_current_dealer_admin),
    db: Session = Depends(get_db),
) -> list[ProductRateOut]:
    """Every product with the registration points currently in force.

    Products with no rate are returned with points=None rather than omitted —
    an unpriced product is the thing an admin most needs to see, because a
    dealer registering it earns nothing and will (rightly) complain.
    """
    rows = db.execute(
        select(Product, PointRate)
        .outerjoin(
            PointRate,
            (PointRate.product_id == Product.id) & (PointRate.effective_to.is_(None)),
        )
        .order_by(Product.name)
    ).all()
    return [
        ProductRateOut(
            product_id=product.id,
            product_name=product.name,
            is_active=product.is_active,
            warranty_months=product.warranty_months,
            worker_points_value=product.points_value,
            points_per_registration=rate.points_per_registration if rate else None,
            rate_id=rate.id if rate else None,
            effective_from=rate.effective_from if rate else None,
        )
        for product, rate in rows
    ]


@router.get("/points/rates", response_model=Paginated[PointRateOut])
def rate_history(
    product_id: uuid.UUID | None = None,
    page: Pagination = Depends(pagination),
    _: Admin = Depends(get_current_dealer_admin),
    db: Session = Depends(get_db),
) -> Paginated[PointRateOut]:
    stmt = select(PointRate)
    if product_id is not None:
        stmt = stmt.where(PointRate.product_id == product_id)
    total = int(db.execute(select(func.count()).select_from(stmt.subquery())).scalar_one())
    rates = db.execute(
        stmt.order_by(PointRate.effective_from.desc()).limit(page.limit).offset(page.offset)
    ).scalars()
    return Paginated[PointRateOut](
        items=[_rate_out(rate) for rate in rates],
        total=total,
        limit=page.limit,
        offset=page.offset,
    )


@router.post("/points/rate", response_model=PointRateOut, status_code=201)
def set_rate(
    body: SetRateIn,
    request: Request,
    admin: Admin = Depends(require_owner),
    db: Session = Depends(get_db),
) -> PointRateOut:
    """Change what a registration is worth. Owner only.

    This is the single lever that sets the programme's cost, so it sits above
    'staff': every other point movement is bounded by a rate someone else chose,
    and this one chooses it. The previous rate is closed rather than overwritten,
    so historic ledger rows keep pointing at the version that produced them.
    """
    product = db.get(Product, body.product_id)
    if product is None:
        raise AppError("product_not_found", 404, "No such product")
    previous = ledger.current_rate(db, product_id=body.product_id)
    rate = ledger.set_rate(
        db,
        product_id=body.product_id,
        points_per_registration=body.points_per_registration,
        admin_id=admin.id,
        note=body.note,
    )
    record_audit(
        db,
        action="set_point_rate",
        entity_type="point_rate",
        entity_id=rate.id,
        actor_id=admin.id,
        reason=body.note,
        ip=client_ip(request),
        metadata={
            "from": previous.points_per_registration if previous else None,
            "to": rate.points_per_registration,
            "product_id": str(body.product_id),
            "product_name": product.name,
        },
    )
    db.commit()
    return _rate_out(rate)


@router.get("/dealers/{dealer_id}/points", response_model=PointsSummaryOut)
def dealer_points(
    dealer_id: uuid.UUID,
    _: Admin = Depends(get_current_dealer_admin),
    db: Session = Depends(get_db),
) -> PointsSummaryOut:
    _get_dealer(db, dealer_id)
    return _summary(db, dealer_id)


@router.get("/dealers/{dealer_id}/ledger", response_model=DealerLedgerOut)
def dealer_ledger(
    dealer_id: uuid.UUID,
    page: Pagination = Depends(pagination),
    _: Admin = Depends(get_current_dealer_admin),
    db: Session = Depends(get_db),
) -> DealerLedgerOut:
    """The dealer's statement, newest first, with a running balance.

    The running total is a window function over the dealer's WHOLE history
    computed before paging, because a balance-after column derived from one page
    of rows would be wrong on every page but the first.
    """
    dealer = _get_dealer(db, dealer_id)

    running = func.sum(LedgerEntry.amount).over(
        order_by=(LedgerEntry.created_at.asc(), LedgerEntry.id.asc()),
        rows=(None, 0),  # UNBOUNDED PRECEDING .. CURRENT ROW
    )
    history = (
        select(
            LedgerEntry.id.label("id"),
            LedgerEntry.dealer_id.label("dealer_id"),
            LedgerEntry.amount.label("amount"),
            LedgerEntry.type.label("type"),
            LedgerEntry.warranty_id.label("warranty_id"),
            LedgerEntry.redemption_id.label("redemption_id"),
            LedgerEntry.rate_version_id.label("rate_version_id"),
            LedgerEntry.admin_id.label("admin_id"),
            LedgerEntry.staff_id.label("staff_id"),
            LedgerEntry.reason.label("reason"),
            LedgerEntry.entry_metadata.label("entry_metadata"),
            LedgerEntry.created_at.label("created_at"),
            running.label("balance_after"),
        )
        .where(LedgerEntry.dealer_id == dealer_id)
        .subquery()
    )

    total = int(
        db.execute(
            select(func.count(LedgerEntry.id)).where(LedgerEntry.dealer_id == dealer_id)
        ).scalar_one()
    )
    rows = db.execute(
        select(history)
        .order_by(history.c.created_at.desc(), history.c.id.desc())
        .limit(page.limit)
        .offset(page.offset)
    ).mappings()

    return DealerLedgerOut(
        dealer=_brief(dealer),
        points=_summary(db, dealer_id),
        items=[
            LedgerEntryOut(
                id=row["id"],
                dealer_id=row["dealer_id"],
                amount=row["amount"],
                type=row["type"],
                warranty_id=row["warranty_id"],
                redemption_id=row["redemption_id"],
                rate_version_id=row["rate_version_id"],
                admin_id=row["admin_id"],
                staff_id=row["staff_id"],
                reason=row["reason"],
                metadata=row["entry_metadata"],
                created_at=row["created_at"],
                balance_after=int(row["balance_after"]),
            )
            for row in rows
        ],
        total=total,
        limit=page.limit,
        offset=page.offset,
    )


@router.post("/dealers/{dealer_id}/points/adjust", response_model=AdjustPointsOut, status_code=201)
def adjust_points(
    dealer_id: uuid.UUID,
    body: AdjustPointsIn,
    request: Request,
    admin: Admin = Depends(require_admin_write),
    db: Session = Depends(get_db),
) -> AdjustPointsOut:
    """Manual credit or debit. A reason is mandatory, in three places.

    The schema requires it, ledger.add_entry refuses without it, and a CHECK
    constraint in the database rejects the row anyway. A manual adjustment with
    no explanation is indistinguishable from theft, and this is the only
    endpoint in the system that can create points out of nothing.
    """
    dealer = _get_dealer(db, dealer_id)
    if body.amount == 0:
        raise AppError("invalid_amount", 400, "An adjustment of zero points is meaningless")

    entry = ledger.add_entry(
        db,
        dealer_id=dealer.id,
        amount=body.amount,
        type=ledger.ADMIN_CREDIT if body.amount > 0 else ledger.ADMIN_DEBIT,
        admin_id=admin.id,
        reason=body.reason,
        metadata={"ip": client_ip(request)},
    )
    record_audit(
        db,
        action="adjust_points",
        entity_type="dealer",
        entity_id=dealer.id,
        actor_id=admin.id,
        reason=body.reason,
        ip=client_ip(request),
        metadata={"amount": body.amount, "entry_id": str(entry.id)},
    )
    db.commit()

    return AdjustPointsOut(
        entry=LedgerEntryOut(
            id=entry.id,
            dealer_id=entry.dealer_id,
            amount=entry.amount,
            type=entry.type,
            warranty_id=entry.warranty_id,
            redemption_id=entry.redemption_id,
            rate_version_id=entry.rate_version_id,
            admin_id=entry.admin_id,
            staff_id=entry.staff_id,
            reason=entry.reason,
            metadata=entry.entry_metadata,
            created_at=entry.created_at,
        ),
        points=_summary(db, dealer.id),
    )
