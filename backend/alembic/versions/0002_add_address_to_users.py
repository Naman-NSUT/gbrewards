"""add address to users

Revision ID: 0002
Revises: 0001
Create Date: 2026-06-26 00:00:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("users", sa.Column("address", sa.String(), nullable=True))


def downgrade() -> None:
    op.drop_column("users", "address")
