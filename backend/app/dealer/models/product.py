from sqlalchemy import Boolean, CheckConstraint, Integer, String, Text, text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.dealer.models.mixins import TimestampMixin, UUIDPkMixin


class DealerProduct(UUIDPkMixin, TimestampMixin, Base):
    """The dealer programme's own product catalogue.

    Separate from the worker programme's `products`. The same physical mattress
    model may exist in both catalogues; there is no foreign key between them and
    no sync. If the two disagree about a model's name, nothing breaks — they are
    simply two independent records used by two independent programmes.

    `warranty_months` lives here because warranty length is a dealer-programme
    concept: it is frozen onto each warranty at the moment of sale, so changing
    it later never rewrites warranties already sold.
    """

    __tablename__ = "dealer_products"
    __table_args__ = (CheckConstraint("warranty_months > 0", name="warranty_months_positive"),)

    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Printed on the physical label, under the QR.
    terms: Mapped[str | None] = mapped_column(Text, nullable=True)
    model_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    warranty_months: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("60"))
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"))
