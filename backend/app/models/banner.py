from sqlalchemy import Boolean, Index, Integer, LargeBinary, String, Text, text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.mixins import TimestampMixin, UUIDPkMixin


class Banner(UUIDPkMixin, TimestampMixin, Base):
    __tablename__ = "banners"
    __table_args__ = (
        Index("ix_banners_is_active_sort_order", "is_active", "sort_order"),
    )

    # For uploaded images, `image_url` points at the serve endpoint
    # (/api/v1/catalog/banners/{id}/image) and the bytes live in `image_data`;
    # for externally-hosted or bundled-static banners `image_data` is null and
    # `image_url` is the absolute/relative URL directly.
    image_url: Mapped[str] = mapped_column(Text, nullable=False)
    image_data: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True)
    image_mime: Mapped[str | None] = mapped_column(String, nullable=True)
    caption: Mapped[str | None] = mapped_column(Text, nullable=True)
    link_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"))
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
