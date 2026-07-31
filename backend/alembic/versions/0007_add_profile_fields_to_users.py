"""Add structured address, DOB and gender to users.

The single free-text `address` column is kept as the street/line-1 field and is
joined by city, state and pincode so redemptions can actually be delivered.
DOB and gender are new profile fields collected at sign-in.

All columns are nullable: accounts that existed before this migration have no
value for them, and the app backfills on the owner's next login.

Revision ID: 0007
Revises: 0006
"""

import sqlalchemy as sa

from alembic import op

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("city", sa.String(), nullable=True))
    op.add_column("users", sa.Column("state", sa.String(), nullable=True))
    op.add_column("users", sa.Column("pincode", sa.String(), nullable=True))
    op.add_column("users", sa.Column("dob", sa.Date(), nullable=True))
    op.add_column("users", sa.Column("gender", sa.String(), nullable=True))
    op.create_check_constraint(
        "gender_valid",
        "users",
        "gender is null or gender in ('male','female')",
    )


def downgrade() -> None:
    op.drop_constraint("gender_valid", "users", type_="check")
    op.drop_column("users", "gender")
    op.drop_column("users", "dob")
    op.drop_column("users", "pincode")
    op.drop_column("users", "state")
    op.drop_column("users", "city")
