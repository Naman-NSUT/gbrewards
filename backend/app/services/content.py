"""Keyed content docs (terms/privacy/about) — upsert-by-key with admin audit."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.models.admin import Admin
from app.models.content_doc import ContentDoc
from app.schemas.admin import ContentDocUpsertIn
from app.services.audit import record_audit


def list_content(db: Session) -> list[ContentDoc]:
    return list(db.execute(select(ContentDoc).order_by(ContentDoc.key)).scalars())


def get_content(db: Session, key: str) -> ContentDoc:
    doc = db.execute(select(ContentDoc).where(ContentDoc.key == key)).scalar_one_or_none()
    if doc is None:
        raise AppError("content_not_found", 404, "Unknown content doc")
    return doc


def upsert_content(db: Session, *, admin: Admin, key: str, body: ContentDocUpsertIn) -> ContentDoc:
    doc = db.execute(select(ContentDoc).where(ContentDoc.key == key)).scalar_one_or_none()
    if doc is None:
        doc = ContentDoc(key=key, title=body.title, body=body.body)
        db.add(doc)
    else:
        doc.title = body.title
        doc.body = body.body
    db.flush()
    record_audit(
        db,
        actor_admin_id=admin.id,
        action="update_content",
        entity_type="content",
        entity_id=doc.id,
        metadata={"key": doc.key, "title": doc.title},
    )
    return doc
