from sqlalchemy import Boolean, CheckConstraint, Integer, String, Text, text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.mixins import TimestampMixin, UUIDPkMixin


class Product(UUIDPkMixin, TimestampMixin, Base):
    __tablename__ = "products"
    __table_args__ = (CheckConstraint("points_value >= 0", name="points_value_non_negative"),)

    name: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    terms: Mapped[str | None] = mapped_column(Text, nullable=True)
    points_value: Mapped[int] = mapped_column(Integer, nullable=False)
    # How long this product's warranty runs, in months. Added by the dealer
    # merge and set from the dealer admin panel. Frozen onto each warranty at
    # registration, so changing it never rewrites warranties already sold.
    warranty_months: Mapped[int | None] = mapped_column(Integer, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"))
