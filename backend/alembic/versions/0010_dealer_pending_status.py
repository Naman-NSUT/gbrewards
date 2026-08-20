"""dealer pending status

Revision ID: 0010
Revises: 0009
Create Date: 2026-08-20 00:00:00.000000

Shops sign themselves up now, so a dealership needs a state between "does not
exist" and "trusted with payouts". A self-signed-up shop starts 'pending': it can
log in and register sales straight away — capturing the sale record is the whole
product and must not wait on anyone — but it cannot redeem until an admin has
approved it once.

Widening a CHECK constraint only. No existing row changes: every dealer that
exists today is 'active' and stays that way.
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0010"
down_revision: str | None = "0009"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Raw SQL, not op.drop_constraint: the metadata naming convention would
    # prepend "ck_dealers_" to whatever name is passed, producing
    # ck_dealers_ck_dealers_status_valid.
    op.execute("ALTER TABLE dealers DROP CONSTRAINT ck_dealers_status_valid")
    op.execute(
        "ALTER TABLE dealers ADD CONSTRAINT ck_dealers_status_valid "
        "CHECK (status IN ('pending','active','suspended','closed'))"
    )


def downgrade() -> None:
    # Anything still pending becomes active rather than blocking the downgrade:
    # a shop that has been registering sales should not lose its login because
    # the schema moved backwards.
    op.execute("UPDATE dealers SET status = 'active' WHERE status = 'pending'")
    op.execute("ALTER TABLE dealers DROP CONSTRAINT ck_dealers_status_valid")
    op.execute(
        "ALTER TABLE dealers ADD CONSTRAINT ck_dealers_status_valid "
        "CHECK (status IN ('active','suspended','closed'))"
    )
