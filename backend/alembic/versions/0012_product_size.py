"""Add products.size — the mattress dimensions printed on the label.

A GoodBed product is a model AND a size: "HR Foam 6 inch" is sold as 72x36,
75x60 and so on, and the size is the first thing a customer checks on the tag.
It was not recorded anywhere, so the printed label could not show it and the
back office could not tell two sizes of one model apart.

Nullable on purpose: products already in the catalogue have no size recorded and
nobody can infer one for them. The label simply omits the line when it is unset,
so an existing product keeps printing exactly as it does today.

Revision ID: 0012
Revises: 0011
"""

import sqlalchemy as sa
from alembic import op

revision = "0012"
down_revision = "0011"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("products", sa.Column("size", sa.String(length=60), nullable=True))


def downgrade() -> None:
    op.drop_column("products", "size")
