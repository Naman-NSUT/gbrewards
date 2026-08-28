"""registration by product, with the invoice number as the thing that cannot repeat

Revision ID: 0011
Revises: 0010
Create Date: 2026-08-28 00:00:00.000000

Dealers no longer scan anything. They pick the product from a dropdown and type
their own invoice number, which deletes the one thing that made a registration
unfarmable: uq_warranties_live_serial guaranteed one live warranty per physical
mattress, so the total payout was capped by the labels the factory printed, not
by how much a dealer felt like typing. With no serial, a dealer picks the same
product five hundred times and is paid five hundred times — at the current 120
points a registration that is 60,000 points of real rewards for an afternoon at
a keyboard.

The replacement cap is the dealer's own invoice number: one live warranty per
(dealer, invoice). A second sale needs a second invoice, which means a second
real piece of paper in the shop's books.

Two details are load-bearing:

  * lower(). Without it "INV-1" and "inv-1" are two different rows and the whole
    guarantee is one shift key away.
  * It is an INDEX, not a SELECT in the service. A check in application code
    loses the race between two submissions of the same invoice arriving at the
    same instant, and both would be paid. The service still checks first, but
    only to produce a friendly error; this is what actually holds.

`serial` becomes NULLABLE rather than dropped. Historic rows keep their serials
and stay protected by uq_warranties_live_serial — Postgres allows any number of
NULLs in a unique index, so old rows and new rows live under both indexes
without either one weakening the other. Nothing is deleted: those serials are
the record of what was physically sold.
"""

from collections.abc import Sequence

from alembic import op
from sqlalchemy import text

revision: str = "0011"
down_revision: str | None = "0010"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Exactly the statuses uq_warranties_live_serial counts. A warranty occupies its
# invoice number in every state except `voided`: a returned sale frees the number
# for the legitimate re-sale that replaces it.
LIVE_STATUSES = (
    "'pending_confirmation','pending_review','pending_backdate','active','claimed'"
)


def upgrade() -> None:
    op.execute("ALTER TABLE warranties ALTER COLUMN serial DROP NOT NULL")

    # Before the old rule is replaced, check the existing rows can live under the
    # new one. Until today one invoice could legitimately carry two mattresses —
    # a bedroom set was two serials on one bill — so a shop's history may hold
    # pairs the new index forbids. Postgres would refuse the CREATE INDEX anyway;
    # doing it here names every offending pair at once instead of one per failed
    # deploy, and says what to do about them.
    duplicates = (
        op.get_bind()
        .execute(
            text(
                "SELECT dealer_id, lower(invoice_ref) AS invoice, count(*) AS n "
                "FROM warranties "
                f"WHERE status IN ({LIVE_STATUSES}) "
                "AND dealer_id IS NOT NULL AND invoice_ref IS NOT NULL "
                "GROUP BY 1, 2 HAVING count(*) > 1 ORDER BY 3 DESC"
            )
        )
        .fetchall()
    )
    if duplicates:
        listed = ", ".join(
            f"dealer {row.dealer_id} invoice {row.invoice!r} x{row.n}" for row in duplicates
        )
        raise RuntimeError(
            "warranties already hold live duplicate (dealer, invoice) pairs, so "
            "uq_warranties_live_dealer_invoice cannot be created: "
            f"{listed}. These are real sales — do not delete them. Make each "
            "invoice_ref distinct (an admin edit, e.g. 'INV-7' and 'INV-7-2') or "
            "void the ones that were never sales, then run this migration again."
        )

    # One live warranty per (dealer, invoice). Partial on status so voiding a
    # warranty gives the number back, and partial on the NULL checks so the
    # historic customer self-registrations — no dealer — and any row without an
    # invoice stay out of it entirely rather than colliding with each other.
    op.execute(
        "CREATE UNIQUE INDEX uq_warranties_live_dealer_invoice "
        "ON warranties (dealer_id, lower(invoice_ref)) "
        f"WHERE status IN ({LIVE_STATUSES}) "
        "AND dealer_id IS NOT NULL AND invoice_ref IS NOT NULL"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS uq_warranties_live_dealer_invoice")

    # Every registration made under the new flow has serial IS NULL, and NOT NULL
    # cannot come back while those rows exist. Deleting them would delete real
    # sales and real warranties, so they are given a synthetic serial built from
    # their own id: unique by construction, so uq_warranties_live_serial still
    # holds, and unmistakable for a factory code to anyone who reads one.
    op.execute("UPDATE warranties SET serial = 'NO-SERIAL-' || id::text WHERE serial IS NULL")
    op.execute("ALTER TABLE warranties ALTER COLUMN serial SET NOT NULL")
