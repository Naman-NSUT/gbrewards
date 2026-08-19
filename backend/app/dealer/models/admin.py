from sqlalchemy import Boolean, CheckConstraint, String, text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.dealer.models.mixins import TimestampMixin, UUIDPkMixin


class DealerAdmin(UUIDPkMixin, TimestampMixin, Base):
    """Back-office accounts for the DEALER programme only.

    Deliberately separate from the worker programme's `admins`. The two systems
    share no tables, so a person who works on both holds two accounts and logs
    into each panel independently.
    """

    __tablename__ = "dealer_admins"
    __table_args__ = (
        CheckConstraint("role in ('owner','staff','support')", name="role_valid"),
    )

    email: Mapped[str] = mapped_column(String(200), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    # `support` is read-mostly: it works the serial lookup and claims queue but
    # cannot adjust points or approve backdates.
    role: Mapped[str] = mapped_column(String(20), nullable=False, server_default=text("'staff'"))
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"))
