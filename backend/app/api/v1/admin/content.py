from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.deps import get_current_admin, get_db
from app.models.admin import Admin
from app.models.content_doc import ContentDoc
from app.schemas.admin import ContentDocOut, ContentDocUpsertIn
from app.services import content

router = APIRouter(tags=["admin-content"])


@router.get("/content", response_model=list[ContentDocOut])
def list_content(
    admin: Admin = Depends(get_current_admin),
    db: Session = Depends(get_db),
) -> list[ContentDoc]:
    return content.list_content(db)


@router.get("/content/{key}", response_model=ContentDocOut)
def get_content(
    key: str,
    admin: Admin = Depends(get_current_admin),
    db: Session = Depends(get_db),
) -> ContentDoc:
    return content.get_content(db, key)


@router.put("/content/{key}", response_model=ContentDocOut)
def upsert_content(
    key: str,
    body: ContentDocUpsertIn,
    admin: Admin = Depends(get_current_admin),
    db: Session = Depends(get_db),
) -> ContentDoc:
    doc = content.upsert_content(db, admin=admin, key=key, body=body)
    db.commit()
    db.refresh(doc)
    return doc
