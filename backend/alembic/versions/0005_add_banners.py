"""add banners (ad-carousel) and seed default poster

Revision ID: 0005
Revises: 0004
Create Date: 2026-07-16 00:00:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0005"
down_revision: str | None = "0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "banners",
        sa.Column("image_url", sa.Text(), nullable=False),
        sa.Column("caption", sa.Text(), nullable=True),
        sa.Column("link_url", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("sort_order", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_banners")),
    )
    op.create_index(
        op.f("ix_banners_is_active_sort_order"),
        "banners",
        ["is_active", "sort_order"],
    )

    # Seed exactly one default poster banner in every environment.
    op.execute(
        """
        INSERT INTO banners (id, image_url, caption, link_url, is_active, sort_order, created_at, updated_at)
        VALUES (
            gen_random_uuid(),
            '/static/banners/goodbed-poster.jpg',
            'GoodBed HR Foam — 25 Year Warranty',
            NULL,
            true,
            0,
            now(),
            now()
        )
        """
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_banners_is_active_sort_order"), table_name="banners")
    op.drop_table("banners")
