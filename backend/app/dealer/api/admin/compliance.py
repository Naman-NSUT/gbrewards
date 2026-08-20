"""Dealer compliance — the screen the client opens every morning.

Thin on purpose: the entire report is one aggregate query in
services/compliance.py, including the ranking. The router picks the window,
validates the sort key and hands back rows.
"""

import uuid
from datetime import date

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.deps import get_current_dealer_admin, get_db
from app.core.errors import AppError
from app.dealer.api.admin._common import Pagination, day_window, pagination
from app.dealer.models.admin import DealerAdmin as Admin
from app.dealer.models.dealer import Dealer
from app.dealer.schemas.admin import (
    ComplianceOut,
    ComplianceRowOut,
    ComplianceTotalsOut,
    CustomerBrief,
    DealerBrief,
    DealerComplianceDetailOut,
    SelfRegistrationOut,
    StaffActivityOut,
    StaffBrief,
)
from app.dealer.services import compliance as compliance_svc

router = APIRouter(tags=["admin-compliance"])


@router.get("/compliance", response_model=ComplianceOut)
def dealer_compliance(
    date_from: date | None = None,
    date_to: date | None = None,
    status: str | None = Query(default=None, pattern="^(active|suspended|closed)$"),
    q: str | None = Query(default=None, max_length=120),
    with_stock_only: bool = Query(
        default=False,
        description="Only dealers holding allocated stock in the window",
    ),
    sort: str = Query(default="worst"),
    page: Pagination = Depends(pagination),
    _: Admin = Depends(get_current_dealer_admin),
    db: Session = Depends(get_db),
) -> ComplianceOut:
    """Every dealer's registration behaviour, worst offenders first.

    March and registered in April falls in two different windows — so a windowed
    rate is a trend, not an exact ratio.
    """
    from_ts, to_ts = day_window(date_from, date_to)
    result = compliance_svc.dealer_compliance(
        db,
        from_ts=from_ts,
        to_ts=to_ts,
        dealer_status=status,
        q=q,
        with_stock_only=with_stock_only,
        sort=sort,
        limit=page.limit,
        offset=page.offset,
    )
    return ComplianceOut(
        items=[ComplianceRowOut.model_validate(row) for row in result.items],
        total=result.total,
        limit=page.limit,
        offset=page.offset,
        date_from=date_from,
        date_to=date_to,
        sort=sort,
        totals=ComplianceTotalsOut.model_validate(result.totals),
    )


@router.get("/compliance/dealers/{dealer_id}", response_model=DealerComplianceDetailOut)
def dealer_drilldown(
    dealer_id: uuid.UUID,
    date_from: date | None = None,
    date_to: date | None = None,
    limit: int = Query(default=100, ge=1, le=500),
    _: Admin = Depends(get_current_dealer_admin),
    db: Session = Depends(get_db),
) -> DealerComplianceDetailOut:
    """Why this dealer is on the list, in the order an account manager argues it.

    The summary row comes from the same SQL as the table, so the drilldown can
    never disagree with the row that was clicked. Below it: the stock they are
    sitting on, the sales their customers registered for them, and which of
    their staff are actually scanning.
    """
    dealer = db.get(Dealer, dealer_id)
    if dealer is None:
        raise AppError("dealer_not_found", 404, "No such dealer")

    from_ts, to_ts = day_window(date_from, date_to)
    summary = compliance_svc.dealer_summary(db, dealer_id=dealer_id, from_ts=from_ts, to_ts=to_ts)
    if summary is None:  # pragma: no cover - the dealer row was just loaded
        raise AppError("dealer_not_found", 404, "No such dealer")
    self_regs = compliance_svc.self_registrations(
        db, dealer_id=dealer_id, from_ts=from_ts, to_ts=to_ts, limit=limit
    )
    staff = compliance_svc.staff_activity(db, dealer_id=dealer_id, from_ts=from_ts, to_ts=to_ts)

    return DealerComplianceDetailOut(
        dealer=DealerBrief(
            id=dealer.id,
            code=dealer.code,
            name=dealer.name,
            status=dealer.status,
            city=dealer.city,
        ),
        summary=ComplianceRowOut.model_validate(summary),
        date_from=date_from,
        date_to=date_to,
        self_registrations=[
            SelfRegistrationOut(
                warranty_id=row.warranty_id,
                serial=row.serial,
                status=row.status,
                registered_at=row.registered_at,
                invoice_date=row.invoice_date,
                proof_file_key=row.proof_file_key,
                customer=CustomerBrief(
                    id=row.customer_id, name=row.customer_name, phone=row.customer_phone
                ),
            )
            for row in self_regs
        ],
        staff_activity=[
            StaffActivityOut(
                staff=StaffBrief(id=row.staff_id, name=row.name, phone=row.phone, role=row.role),
                is_active=row.is_active,
                last_active_at=row.last_active_at,
                registrations=row.registrations,
            )
            for row in staff
        ],
    )
