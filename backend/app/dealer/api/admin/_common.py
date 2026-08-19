"""Helpers shared by the admin routers. Not a router — nothing to wire up.

Three things every admin list screen needs and none of them should be
reimplemented eleven times: one pagination dependency, one date-window
interpretation, and one count-of-a-query helper.
"""

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from fastapi import Query
from sqlalchemy import Row, Select, and_, func, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.dealer.models.allocation import Allocation
from app.dealer.models.customer import Customer
from app.dealer.models.dealer import Dealer
from app.dealer.models.warranty import LIVE_STATUSES, Warranty
from app.dealer.schemas.admin import (
    AllocationOut,
    CustomerBrief,
    DealerBrief,
    WarrantyListItem,
)
from app.dealer.services import warranty as warranty_svc
from app.models.product import Product
from app.models.product_unit import ProductUnit as Unit

MAX_PAGE = 200


@dataclass(frozen=True)
class Pagination:
    limit: int
    offset: int


def pagination(
    limit: int = Query(default=50, ge=1, le=MAX_PAGE),
    offset: int = Query(default=0, ge=0),
) -> Pagination:
    return Pagination(limit=limit, offset=offset)


def day_window(
    date_from: date | None, date_to: date | None
) -> tuple[datetime | None, datetime | None]:
    """Turn an inclusive calendar-day filter into half-open timestamp bounds.

    In the SELLER's timezone, not UTC. An admin filtering "today" in Mumbai means
    the Indian day; comparing against UTC instants would silently drop the last
    five and a half hours of every day's registrations.
    """
    tz = ZoneInfo(settings.business_timezone)
    start = datetime.combine(date_from, time.min, tzinfo=tz) if date_from else None
    # Half-open upper bound: the whole of `date_to` is included without needing
    # a 23:59:59.999999 fudge that drops sub-second rows.
    end = datetime.combine(date_to + timedelta(days=1), time.min, tzinfo=tz) if date_to else None
    return start, end


def count_of(db: Session, stmt: Select[Any]) -> int:
    """Total rows a list query would return, ignoring paging and ordering."""
    counted = select(func.count()).select_from(stmt.order_by(None).subquery())
    return int(db.execute(counted).scalar_one())


def like(term: str) -> str:
    """Escape a user search term for ILIKE and wrap it in wildcards."""
    escaped = term.strip().replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return f"%{escaped}%"


def warranty_select() -> Select[tuple[Warranty, Customer, Dealer]]:
    """A warranty with the two rows nobody ever wants it without."""
    return (
        select(Warranty, Customer, Dealer)
        .join(Customer, Customer.id == Warranty.customer_id)
        .outerjoin(Dealer, Dealer.id == Warranty.dealer_id)
    )


def to_warranty_item(
    warranty: Warranty, customer: Customer | None, dealer: Dealer | None
) -> WarrantyListItem:
    """Map to the list shape, folding derived expiry into the reported status.

    `status` is what a human should be told and `stored_status` is the column.
    An expired warranty whose row still says 'active' must never be shown as
    active — expiry is derived on purpose (models/warranty.py) and this is the
    one place that derivation is applied.
    """
    return WarrantyListItem(
        id=warranty.id,
        serial=warranty.serial,
        model_name=warranty.model_name,
        model_code=warranty.model_code,
        status=warranty_svc.display_status(warranty),
        stored_status=warranty.status,
        source=warranty.source,
        warranty_months=warranty.warranty_months,
        warranty_start_date=warranty.warranty_start_date,
        warranty_end_date=warranty.warranty_end_date,
        backdate_days=warranty.backdate_days,
        unit_unverified=warranty.unit_unverified,
        invoice_ref=warranty.invoice_ref,
        invoice_date=warranty.invoice_date,
        registered_at=warranty.registered_at,
        customer=(
            CustomerBrief(id=customer.id, name=customer.name, phone=customer.phone)
            if customer is not None
            else None
        ),
        dealer=(
            DealerBrief(
                id=dealer.id,
                code=dealer.code,
                name=dealer.name,
                status=dealer.status,
                city=dealer.city,
            )
            if dealer is not None
            else None
        ),
    )


AllocationRow = Row[tuple[Allocation, str, str, str | None, Any]]


def allocation_select() -> Select[Any]:
    """An allocation with the three things every screen shows beside it.

    Who holds it, what the product is, and whether it has been sold — joined
    once here so the allocation list, the warranty detail and the serial lookup
    all render the same row rather than three subtly different ones.
    """
    return (
        select(Allocation, Dealer.code, Dealer.name, Product.name, Warranty.id)
        .join(Dealer, Dealer.id == Allocation.dealer_id)
        .outerjoin(Unit, Unit.token == Allocation.serial)
        .outerjoin(Product, Product.id == Unit.product_id)
        .outerjoin(
            Warranty,
            and_(Warranty.serial == Allocation.serial, Warranty.status.in_(LIVE_STATUSES)),
        )
    )


def to_allocation_out(row: AllocationRow) -> AllocationOut:
    allocation, dealer_code, dealer_name, model_name, warranty_id = row
    return AllocationOut.model_validate(allocation).model_copy(
        update={
            "dealer_code": dealer_code,
            "dealer_name": dealer_name,
            "model_name": model_name,
            "warranty_id": warranty_id,
        }
    )
