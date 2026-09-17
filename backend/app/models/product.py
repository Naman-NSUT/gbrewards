from sqlalchemy import Boolean, CheckConstraint, Integer, String, Text, text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.mixins import TimestampMixin, UUIDPkMixin


class Product(UUIDPkMixin, TimestampMixin, Base):
    __tablename__ = "products"
    __table_args__ = (CheckConstraint("points_value >= 0", name="points_value_non_negative"),)

    name: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Dimensions as the shop quotes them, e.g. "72 x 36 x 6 inch". Free text
    # rather than parsed numbers: the client writes sizes several ways and this
    # is printed verbatim on the label, never computed with.
    size: Mapped[str | None] = mapped_column(String(60), nullable=True)
    terms: Mapped[str | None] = mapped_column(Text, nullable=True)
    points_value: Mapped[int] = mapped_column(Integer, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"))
