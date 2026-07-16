import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.deps import get_current_admin, get_db
from app.models.admin import Admin
from app.models.banner import Banner
from app.schemas.admin import BannerIn, BannerOut, BannerUpdateIn
from app.services import banners

router = APIRouter(tags=["admin-banners"])


@router.get("/banners", response_model=list[BannerOut])
def list_banners(
    admin: Admin = Depends(get_current_admin),
    db: Session = Depends(get_db),
) -> list[Banner]:
    return banners.list_banners(db)


@router.post("/banners", response_model=BannerOut, status_code=201)
def create_banner(
    body: BannerIn,
    admin: Admin = Depends(get_current_admin),
    db: Session = Depends(get_db),
) -> Banner:
    banner = banners.create_banner(db, admin=admin, body=body)
    db.commit()
    db.refresh(banner)
    return banner


@router.patch("/banners/{banner_id}", response_model=BannerOut)
def update_banner(
    banner_id: uuid.UUID,
    body: BannerUpdateIn,
    admin: Admin = Depends(get_current_admin),
    db: Session = Depends(get_db),
) -> Banner:
    banner = banners.update_banner(db, admin=admin, banner_id=banner_id, body=body)
    db.commit()
    db.refresh(banner)
    return banner


@router.delete("/banners/{banner_id}", status_code=204)
def delete_banner(
    banner_id: uuid.UUID,
    admin: Admin = Depends(get_current_admin),
    db: Session = Depends(get_db),
) -> None:
    banners.delete_banner(db, admin=admin, banner_id=banner_id)
    db.commit()
