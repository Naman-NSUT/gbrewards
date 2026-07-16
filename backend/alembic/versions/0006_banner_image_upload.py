"""Add uploaded-image storage columns to banners.

Banners can now be uploaded as image files (stored in the DB so they survive
redeploys on ephemeral hosting) instead of only referencing an external URL.

Revision ID: 0006
Revises: 0005
"""

import sqlalchemy as sa

from alembic import op

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("banners", sa.Column("image_data", sa.LargeBinary(), nullable=True))
    op.add_column("banners", sa.Column("image_mime", sa.String(), nullable=True))


def downgrade() -> None:
    op.drop_column("banners", "image_mime")
    op.drop_column("banners", "image_data")
