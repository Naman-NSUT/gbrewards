"""FAQ CRUD with admin audit (mutations write audit, GET does not)."""

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.models.admin import Admin
from app.models.faq import Faq
from app.schemas.admin import FaqIn, FaqUpdateIn
from app.services.audit import record_audit


def list_faqs(db: Session) -> list[Faq]:
    return list(
        db.execute(select(Faq).order_by(Faq.sort_order, Faq.created_at)).scalars()
    )


def _get_or_404(db: Session, faq_id: uuid.UUID) -> Faq:
    faq = db.get(Faq, faq_id)
    if faq is None:
        raise AppError("faq_not_found", 404, "Unknown FAQ")
    return faq


def create_faq(db: Session, *, admin: Admin, body: FaqIn) -> Faq:
    faq = Faq(
        question=body.question,
        answer=body.answer,
        sort_order=body.sort_order,
        is_published=body.is_published,
    )
    db.add(faq)
    db.flush()
    record_audit(
        db,
        actor_admin_id=admin.id,
        action="create_faq",
        entity_type="faq",
        entity_id=faq.id,
        metadata={
            "question": faq.question,
            "is_published": faq.is_published,
            "sort_order": faq.sort_order,
        },
    )
    return faq


def update_faq(db: Session, *, admin: Admin, faq_id: uuid.UUID, body: FaqUpdateIn) -> Faq:
    faq = _get_or_404(db, faq_id)
    changes = body.model_dump(exclude_unset=True)
    for field, value in changes.items():
        setattr(faq, field, value)
    record_audit(
        db,
        actor_admin_id=admin.id,
        action="update_faq",
        entity_type="faq",
        entity_id=faq.id,
        metadata={"changes": changes},
    )
    return faq


def delete_faq(db: Session, *, admin: Admin, faq_id: uuid.UUID) -> None:
    faq = _get_or_404(db, faq_id)
    record_audit(
        db,
        actor_admin_id=admin.id,
        action="delete_faq",
        entity_type="faq",
        entity_id=faq.id,
        metadata={"question": faq.question},
    )
    db.delete(faq)
