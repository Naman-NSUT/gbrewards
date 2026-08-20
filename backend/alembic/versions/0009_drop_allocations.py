"""drop allocations

Revision ID: 0009
Revises: 0008
Create Date: 2026-08-20 00:00:00.000000

Allocation no longer gates registration — any registered dealer may register any
manufactured label — so allocations were left with nothing to do. The upload
page, the admin routers and the service are gone; these tables are the last of
it.

Safe to run: production held zero allocations and zero allocation batches when
this was written, because the gate was removed before anyone uploaded any.
The downgrade recreates the tables empty; the ROWS are not recoverable from
here, which is only acceptable because there were none.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0009"
down_revision: str | None = "0008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("DROP INDEX IF EXISTS uq_allocations_open_serial")
    op.drop_index("ix_allocations_batch_id", table_name="allocations")
    op.drop_index("ix_allocations_serial", table_name="allocations")
    op.drop_index("ix_allocations_dealer_id_status", table_name="allocations")
    op.drop_table("allocations")
    op.drop_table("allocation_batches")


def downgrade() -> None:
    op.create_table(
        "allocation_batches",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("filename", sa.String(length=400), nullable=True),
        sa.Column("uploaded_by_admin_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("row_count", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("ok_count", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("error_count", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("errors", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["uploaded_by_admin_id"], ["dealer_admins.id"], name=op.f("fk_allocation_batches_uploaded_by_admin_id_dealer_admins")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_allocation_batches")),
    )
    op.create_table(
        "allocations",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("serial", sa.String(length=128), nullable=False),
        sa.Column("dealer_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("batch_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("status", sa.String(length=20), server_default=sa.text("'allocated'"), nullable=False),
        sa.Column("dispatch_ref", sa.String(length=120), nullable=True),
        sa.Column("allocated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoke_reason", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("status in ('allocated','registered','revoked','returned')", name=op.f("ck_allocations_status_valid")),
        sa.ForeignKeyConstraint(["batch_id"], ["allocation_batches.id"], name=op.f("fk_allocations_batch_id_allocation_batches")),
        sa.ForeignKeyConstraint(["dealer_id"], ["dealers.id"], name=op.f("fk_allocations_dealer_id_dealers")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_allocations")),
    )
    op.create_index("ix_allocations_dealer_id_status", "allocations", ["dealer_id", "status"])
    op.create_index("ix_allocations_serial", "allocations", ["serial"])
    op.create_index("ix_allocations_batch_id", "allocations", ["batch_id"])
    op.execute(
        "CREATE UNIQUE INDEX uq_allocations_open_serial ON allocations (serial) "
        "WHERE status IN ('allocated','registered')"
    )
