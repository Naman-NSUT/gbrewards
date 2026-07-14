"""add rewards, faqs, content docs; link redemptions to rewards

Revision ID: 0004
Revises: 0003
Create Date: 2026-07-14 00:00:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0004"
down_revision: str | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "rewards",
        sa.Column("title", sa.String(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("points_cost", sa.Integer(), nullable=False),
        sa.Column("image_url", sa.Text(), nullable=True),
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
        sa.CheckConstraint(
            "points_cost >= 0", name=op.f("ck_rewards_points_cost_non_negative")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_rewards")),
    )
    op.create_index(
        op.f("ix_rewards_is_active_sort_order"),
        "rewards",
        ["is_active", "sort_order"],
    )

    op.create_table(
        "faqs",
        sa.Column("question", sa.Text(), nullable=False),
        sa.Column("answer", sa.Text(), nullable=False),
        sa.Column("sort_order", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("is_published", sa.Boolean(), server_default=sa.text("true"), nullable=False),
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
        sa.PrimaryKeyConstraint("id", name=op.f("pk_faqs")),
    )
    op.create_index(
        op.f("ix_faqs_is_published_sort_order"),
        "faqs",
        ["is_published", "sort_order"],
    )

    op.create_table(
        "content_docs",
        sa.Column("key", sa.String(), nullable=False),
        sa.Column("title", sa.String(), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
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
        sa.PrimaryKeyConstraint("id", name=op.f("pk_content_docs")),
        sa.UniqueConstraint("key", name=op.f("uq_content_docs_key")),
    )

    op.add_column(
        "redemption_requests",
        sa.Column("reward_id", sa.UUID(), nullable=True),
    )
    op.create_foreign_key(
        op.f("fk_redemption_requests_reward_id_rewards"),
        "redemption_requests",
        "rewards",
        ["reward_id"],
        ["id"],
    )


def downgrade() -> None:
    op.drop_constraint(
        op.f("fk_redemption_requests_reward_id_rewards"),
        "redemption_requests",
        type_="foreignkey",
    )
    op.drop_column("redemption_requests", "reward_id")

    op.drop_table("content_docs")

    op.drop_index(op.f("ix_faqs_is_published_sort_order"), table_name="faqs")
    op.drop_table("faqs")

    op.drop_index(op.f("ix_rewards_is_active_sort_order"), table_name="rewards")
    op.drop_table("rewards")
