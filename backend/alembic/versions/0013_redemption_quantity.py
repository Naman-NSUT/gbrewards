"""Add redemption_requests.quantity — how many of the reward was asked for.

A reward is priced per unit ("Cash 500 — 50 pts"), and a worker with 300 points
wants to redeem six of them, not six separate requests. Multiplying the points
alone is not enough: the admin fulfilling a request would see "300 pts, Cash 500"
and have to divide to work out how many to hand over. Recording the count is what
makes the request actionable.

Backfilled to 1 rather than points/points_cost: every existing request was made
one unit at a time, and dividing would be a guess on any reward whose cost has
been edited since.

Revision ID: 0013
Revises: 0012
"""

import sqlalchemy as sa
from alembic import op

revision = "0013"
down_revision = "0012"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "redemption_requests",
        sa.Column("quantity", sa.Integer(), nullable=False, server_default=sa.text("1")),
    )
    # Points is the authority on what gets debited; quantity only has to stay a
    # real count. The CHECK is here so no code path can write a zero or negative
    # one, the same way points_positive guards the amount.
    op.create_check_constraint(
        "quantity_positive", "redemption_requests", "quantity > 0"
    )


def downgrade() -> None:
    op.drop_constraint("quantity_positive", "redemption_requests", type_="check")
    op.drop_column("redemption_requests", "quantity")
