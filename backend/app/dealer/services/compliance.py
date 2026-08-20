"""Dealer compliance — the screen the client opens every morning.

The question it answers: WHICH DEALERS ARE TAKING STOCK AND NOT REGISTERING IT?
That is the entire commercial reason this product exists, so the numbers here
are the product's report card, not an analytics nicety.

Six signals per dealer, in increasing order of how damning they are:

  warranties_registered        sales they recorded
  self_registrations           customers who had to do it themselves
  days_since_last_registration a shop that has gone quiet
  self_registrations           THE PROOF. A customer registered a unit that was
                               allocated to this dealer, which means the sale
                               definitely happened and the dealer definitely did
                               not record it. Unregistered stock is a suspicion;
                               this is evidence.

ONE QUERY, NOT A LOOP. Written as a single aggregate over CTEs because the
client runs it across every dealer every morning; a per-dealer query would be
hundreds of round-trips to render one table. Nullable parameters are CAST
explicitly — psycopg cannot infer the type of a bare NULL bind inside a
comparison, and the query would fail only when a filter is omitted.
"""

import uuid
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.errors import AppError

# How much one proven miss outweighs one possibly-unsold unit when ranking the
# worst offenders. Unregistered stock may simply be sitting in a warehouse; a
# customer self-registration is a sale that happened without the dealer. Five is
# a judgement call, exposed as a constant so the client can argue with it.
SELF_REGISTRATION_WEIGHT = 5

_SORTS: dict[str, str] = {
    # Default. Ranks by the composite score, then by exposure, so a big dealer
    # with a bad rate outranks a one-unit shop that registered nothing.
    # Stock is no longer scoped to shops, so there is no allocated-versus-
    # registered ratio to rank on. What is still true, and is the whole point of
    # this screen, is: whose customers are registering their own warranties, and
    # who has gone quiet.
    "worst": "non_compliance_score DESC, self_registrations DESC, d.code ASC",
    "self_registrations": "self_registrations DESC, d.code ASC",
    "quietest": "days_since_last_registration DESC NULLS FIRST, d.code ASC",
    "registrations": "warranties_registered DESC, d.code ASC",
    "backdated": "backdated_registrations DESC, d.code ASC",
    "registered": "warranties_registered DESC, d.code ASC",
    "name": "d.name ASC",
    "code": "d.code ASC",
}

# Shared by the page query, the totals query and the single-dealer drilldown, so
# the drilldown can never disagree with the row the admin clicked on.
_CTES = """
WITH win_reg AS (
    SELECT w.dealer_id,
           count(*) AS warranties_registered,
           count(*) FILTER (WHERE w.backdate_days > 0) AS backdated_registrations
    FROM warranties w
    WHERE w.source = 'dealer'
      AND w.status <> 'voided'
      AND (CAST(:from_ts AS timestamptz) IS NULL
           OR w.registered_at >= CAST(:from_ts AS timestamptz))
      AND (CAST(:to_ts AS timestamptz) IS NULL
           OR w.registered_at < CAST(:to_ts AS timestamptz))
    GROUP BY w.dealer_id
),
win_self AS (
    -- THE signal. A customer registering their own warranty is direct evidence
    -- that a shop did not. The shop is whoever the CUSTOMER named when they
    -- registered (warranties.dealer_id on a customer_self row); when they named
    -- nobody the row is simply unattributed rather than blamed on a guess.
    SELECT w.dealer_id, count(*) AS self_registrations
    FROM warranties w
    WHERE w.source = 'customer_self'
      AND w.status <> 'voided'
      AND w.dealer_id IS NOT NULL
      AND (CAST(:from_ts AS timestamptz) IS NULL
           OR w.registered_at >= CAST(:from_ts AS timestamptz))
      AND (CAST(:to_ts AS timestamptz) IS NULL
           OR w.registered_at < CAST(:to_ts AS timestamptz))
    GROUP BY w.dealer_id
),
last_reg AS (
    -- Deliberately NOT windowed. "Days since last registration" is a live
    -- signal about a shop that has gone quiet; restricting it to the selected
    -- window would report 'never' for every dealer on a one-day filter.
    SELECT w.dealer_id, max(w.registered_at) AS last_registration_at
    FROM warranties w
    WHERE w.source = 'dealer' AND w.status <> 'voided'
    GROUP BY w.dealer_id
)
"""

_ROW_SELECT = """
SELECT d.id AS dealer_id,
       d.code AS dealer_code,
       d.name AS dealer_name,
       d.city AS city,
       d.status AS dealer_status,
       COALESCE(wr.warranties_registered, 0) AS warranties_registered,
       COALESCE(wr.backdated_registrations, 0) AS backdated_registrations,
       COALESCE(ws.self_registrations, 0) AS self_registrations,
       lr.last_registration_at,
       CASE WHEN lr.last_registration_at IS NULL THEN NULL
            ELSE (CURRENT_DATE - lr.last_registration_at::date) END
         AS days_since_last_registration,
       -- Weighted self-registrations, plus a penalty for going quiet. Both are
       -- things a shop DID or failed to do; neither needs stock to be scoped.
       (COALESCE(ws.self_registrations, 0) * CAST(:self_weight AS numeric)
        + CASE WHEN lr.last_registration_at IS NULL THEN CAST(:self_weight AS numeric)
               ELSE LEAST((CURRENT_DATE - lr.last_registration_at::date) / 30.0, 3) END)
         AS non_compliance_score
FROM dealers d
LEFT JOIN win_reg wr ON wr.dealer_id = d.id
LEFT JOIN win_self ws ON ws.dealer_id = d.id
LEFT JOIN last_reg lr ON lr.dealer_id = d.id
WHERE (CAST(:dealer_id AS uuid) IS NULL OR d.id = CAST(:dealer_id AS uuid))
  AND (CAST(:dealer_status AS text) IS NULL OR d.status = CAST(:dealer_status AS text))
  AND (CAST(:q AS text) IS NULL
       OR d.code ILIKE CAST(:q AS text)
       OR d.name ILIKE CAST(:q AS text)
       OR COALESCE(d.city, '') ILIKE CAST(:q AS text))
"""


@dataclass(frozen=True)
class ComplianceRow:
    dealer_id: uuid.UUID
    dealer_code: str
    dealer_name: str
    city: str | None
    dealer_status: str
    warranties_registered: int
    backdated_registrations: int
    self_registrations: int
    last_registration_at: datetime | None
    days_since_last_registration: int | None
    non_compliance_score: float


@dataclass(frozen=True)
class ComplianceTotals:
    dealers: int
    warranties_registered: int
    self_registrations: int


@dataclass(frozen=True)
class CompliancePage:
    items: list[ComplianceRow]
    total: int
    totals: ComplianceTotals


def _params(
    *,
    from_ts: datetime | None,
    to_ts: datetime | None,
    dealer_id: uuid.UUID | None = None,
    dealer_status: str | None = None,
    q: str | None = None,
    with_stock_only: bool = False,
) -> dict[str, Any]:
    return {
        "from_ts": from_ts,
        "to_ts": to_ts,
        "dealer_id": str(dealer_id) if dealer_id else None,
        "dealer_status": dealer_status,
        "q": f"%{q.strip()}%" if q and q.strip() else None,
        "with_stock_only": with_stock_only,
        "self_weight": SELF_REGISTRATION_WEIGHT,
    }


def _row(mapping: dict[str, Any]) -> ComplianceRow:
    return ComplianceRow(
        dealer_id=mapping["dealer_id"],
        dealer_code=mapping["dealer_code"],
        dealer_name=mapping["dealer_name"],
        city=mapping["city"],
        dealer_status=mapping["dealer_status"],
        warranties_registered=int(mapping["warranties_registered"]),
        backdated_registrations=int(mapping["backdated_registrations"]),
        self_registrations=int(mapping["self_registrations"]),
        last_registration_at=mapping["last_registration_at"],
        days_since_last_registration=(
            int(mapping["days_since_last_registration"])
            if mapping["days_since_last_registration"] is not None
            else None
        ),
        non_compliance_score=float(mapping["non_compliance_score"]),
    )


def dealer_compliance(
    db: Session,
    *,
    from_ts: datetime | None = None,
    to_ts: datetime | None = None,
    dealer_status: str | None = None,
    q: str | None = None,
    with_stock_only: bool = False,
    sort: str = "worst",
    limit: int = 50,
    offset: int = 0,
) -> CompliancePage:
    """One page of the compliance table, worst-first by default.

    Counts respect the date window; `days_since_last_registration` does not (see
    the last_reg CTE). Over a window, registrations are counted
    independently — a unit allocated in March and registered in April lands in
    two different windows — so a windowed rate is a trend, and the unwindowed
    rate is the true one.
    """
    if sort not in _SORTS:
        raise AppError("invalid_sort", 400, f"Unknown sort '{sort}'", {"allowed": sorted(_SORTS)})

    params = _params(
        from_ts=from_ts,
        to_ts=to_ts,
        dealer_status=dealer_status,
        q=q,
        with_stock_only=with_stock_only,
    )

    rows = db.execute(
        text(f"{_CTES}{_ROW_SELECT} ORDER BY {_SORTS[sort]} LIMIT :limit OFFSET :offset"),
        {**params, "limit": limit, "offset": offset},
    ).mappings()
    items = [_row(dict(row)) for row in rows]

    summary = (
        db.execute(
            text(
                f"{_CTES}"
                "SELECT count(*) AS dealers,"
                "       COALESCE(sum(warranties_registered), 0) AS warranties_registered,"
                "       COALESCE(sum(self_registrations), 0) AS self_registrations"
                f" FROM ({_ROW_SELECT}) rows"
            ),
            params,
        )
        .mappings()
        .one()
    )

    registered = int(summary["warranties_registered"])
    return CompliancePage(
        items=items,
        total=int(summary["dealers"]),
        totals=ComplianceTotals(
            dealers=int(summary["dealers"]),
            warranties_registered=registered,
            self_registrations=int(summary["self_registrations"]),
        ),
    )


def dealer_summary(
    db: Session,
    *,
    dealer_id: uuid.UUID,
    from_ts: datetime | None = None,
    to_ts: datetime | None = None,
) -> ComplianceRow | None:
    """The same row the table shows, for one dealer. Same SQL, so same numbers."""
    row = (
        db.execute(
            text(f"{_CTES}{_ROW_SELECT}"),
            _params(from_ts=from_ts, to_ts=to_ts, dealer_id=dealer_id),
        )
        .mappings()
        .one_or_none()
    )
    return _row(dict(row)) if row is not None else None


@dataclass(frozen=True)
class UnregisteredUnit:
    serial: str
    model_name: str | None
    dispatch_ref: str | None
    allocated_at: datetime
    days_held: int


@dataclass(frozen=True)
class SelfRegistration:
    warranty_id: uuid.UUID
    serial: str
    status: str
    registered_at: datetime
    invoice_date: date | None
    proof_file_key: str | None
    customer_id: uuid.UUID
    customer_name: str
    customer_phone: str


@dataclass(frozen=True)
class StaffActivity:
    staff_id: uuid.UUID
    name: str
    phone: str
    role: str
    is_active: bool
    last_active_at: datetime | None
    registrations: int


def self_registrations(
    db: Session,
    *,
    dealer_id: uuid.UUID,
    from_ts: datetime | None = None,
    to_ts: datetime | None = None,
    limit: int = 100,
) -> list[SelfRegistration]:
    """Units this dealer held that the CUSTOMER had to register. The evidence."""
    rows = db.execute(
        text(
            """
            SELECT w.id AS warranty_id, w.serial, w.status, w.registered_at,
                   w.invoice_date, w.proof_file_key,
                   c.id AS customer_id, c.name AS customer_name, c.phone AS customer_phone
            FROM warranties w
            JOIN customers c ON c.id = w.customer_id
            -- The shop the CUSTOMER named when they registered. Stock is not
            -- scoped, so there is nothing else that could attribute this.
            WHERE w.dealer_id = CAST(:dealer_id AS uuid)
              AND w.source = 'customer_self'
              AND w.status <> 'voided'
              AND (CAST(:from_ts AS timestamptz) IS NULL
                   OR w.registered_at >= CAST(:from_ts AS timestamptz))
              AND (CAST(:to_ts AS timestamptz) IS NULL
                   OR w.registered_at < CAST(:to_ts AS timestamptz))
            ORDER BY w.registered_at DESC
            LIMIT :limit
            """
        ),
        {
            "dealer_id": str(dealer_id),
            "from_ts": from_ts,
            "to_ts": to_ts,
            "limit": limit,
        },
    ).mappings()
    return [
        SelfRegistration(
            warranty_id=row["warranty_id"],
            serial=row["serial"],
            status=row["status"],
            registered_at=row["registered_at"],
            invoice_date=row["invoice_date"],
            proof_file_key=row["proof_file_key"],
            customer_id=row["customer_id"],
            customer_name=row["customer_name"],
            customer_phone=row["customer_phone"],
        )
        for row in rows
    ]


def staff_activity(
    db: Session,
    *,
    dealer_id: uuid.UUID,
    from_ts: datetime | None = None,
    to_ts: datetime | None = None,
) -> list[StaffActivity]:
    """Who at this shop is actually registering, and who has never scanned once.

    A dealership is often 'non-compliant' because one person does all the
    registering and is on leave, which is a training problem rather than a fraud
    problem. Per-person counts are what distinguishes the two.
    """
    rows = db.execute(
        text(
            """
            SELECT s.id AS staff_id, s.name, s.phone, s.role, s.is_active, s.last_active_at,
                   count(w.id) AS registrations
            FROM dealer_staff s
            LEFT JOIN warranties w
              ON w.staff_id = s.id
             AND w.status <> 'voided'
             AND (CAST(:from_ts AS timestamptz) IS NULL
                  OR w.registered_at >= CAST(:from_ts AS timestamptz))
             AND (CAST(:to_ts AS timestamptz) IS NULL
                  OR w.registered_at < CAST(:to_ts AS timestamptz))
            WHERE s.dealer_id = CAST(:dealer_id AS uuid)
            GROUP BY s.id, s.name, s.phone, s.role, s.is_active, s.last_active_at
            ORDER BY registrations DESC, s.name ASC
            """
        ),
        {"dealer_id": str(dealer_id), "from_ts": from_ts, "to_ts": to_ts},
    ).mappings()
    return [
        StaffActivity(
            staff_id=row["staff_id"],
            name=row["name"],
            phone=row["phone"],
            role=row["role"],
            is_active=row["is_active"],
            last_active_at=row["last_active_at"],
            registrations=int(row["registrations"]),
        )
        for row in rows
    ]
