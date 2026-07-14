from sqlalchemy import String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.mixins import TimestampMixin, UUIDPkMixin


class ContentDoc(UUIDPkMixin, TimestampMixin, Base):
    __tablename__ = "content_docs"
    __table_args__ = (UniqueConstraint("key", name="uq_content_docs_key"),)

    key: Mapped[str] = mapped_column(String, nullable=False)
    title: Mapped[str] = mapped_column(String, nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
