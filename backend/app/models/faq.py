from sqlalchemy import Boolean, Index, Integer, Text, text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.mixins import TimestampMixin, UUIDPkMixin


class Faq(UUIDPkMixin, TimestampMixin, Base):
    __tablename__ = "faqs"
    __table_args__ = (Index("ix_faqs_is_published_sort_order", "is_published", "sort_order"),)

    question: Mapped[str] = mapped_column(Text, nullable=False)
    answer: Mapped[str] = mapped_column(Text, nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    is_published: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("true")
    )
