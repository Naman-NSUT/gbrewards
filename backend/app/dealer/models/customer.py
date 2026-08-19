from sqlalchemy import Boolean, Index, String, text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.dealer.models.mixins import TimestampMixin, UUIDPkMixin


class Customer(UUIDPkMixin, TimestampMixin, Base):
    """The end buyer.

    Keyed on phone because that is what the dealer types at the counter and what
    the customer later uses to look their warranty up. One customer may own
    several mattresses, so warranties reference customers rather than embedding
    them.
    """

    __tablename__ = "customers"
    __table_args__ = (Index("ix_customers_name", "name"),)

    phone: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    email: Mapped[str | None] = mapped_column(String(200), nullable=True)
    address: Mapped[str | None] = mapped_column(String(400), nullable=True)
    city: Mapped[str | None] = mapped_column(String(100), nullable=True)
    state: Mapped[str | None] = mapped_column(String(100), nullable=True)
    pincode: Mapped[str | None] = mapped_column(String(10), nullable=True)
    # Set when the customer themselves acts on the SMS link. Distinguishes "a
    # dealer typed this number" from "the person holding that number agreed",
    # which is the whole difference between a claimed sale and a proven one.
    is_phone_verified: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("false")
    )
