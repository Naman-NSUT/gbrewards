import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.deps import get_current_admin, get_db
from app.models.admin import Admin
from app.models.faq import Faq
from app.schemas.admin import FaqIn, FaqOut, FaqUpdateIn
from app.services import faqs

router = APIRouter(tags=["admin-faqs"])


@router.get("/faqs", response_model=list[FaqOut])
def list_faqs(
    admin: Admin = Depends(get_current_admin),
    db: Session = Depends(get_db),
) -> list[Faq]:
    return faqs.list_faqs(db)


@router.post("/faqs", response_model=FaqOut, status_code=201)
def create_faq(
    body: FaqIn,
    admin: Admin = Depends(get_current_admin),
    db: Session = Depends(get_db),
) -> Faq:
    faq = faqs.create_faq(db, admin=admin, body=body)
    db.commit()
    db.refresh(faq)
    return faq


@router.patch("/faqs/{faq_id}", response_model=FaqOut)
def update_faq(
    faq_id: uuid.UUID,
    body: FaqUpdateIn,
    admin: Admin = Depends(get_current_admin),
    db: Session = Depends(get_db),
) -> Faq:
    faq = faqs.update_faq(db, admin=admin, faq_id=faq_id, body=body)
    db.commit()
    db.refresh(faq)
    return faq


@router.delete("/faqs/{faq_id}", status_code=204)
def delete_faq(
    faq_id: uuid.UUID,
    admin: Admin = Depends(get_current_admin),
    db: Session = Depends(get_db),
) -> None:
    faqs.delete_faq(db, admin=admin, faq_id=faq_id)
    db.commit()
