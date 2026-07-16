"""Ad-carousel banner CRUD with admin audit (mutations write audit, GET does not)."""

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.models.admin import Admin
from app.models.banner import Banner
from app.schemas.admin import BannerIn, BannerUpdateIn
from app.services.audit import record_audit


def list_banners(db: Session) -> list[Banner]:
    return list(
        db.execute(
            select(Banner).order_by(Banner.sort_order, Banner.created_at)
        ).scalars()
    )


def _get_or_404(db: Session, banner_id: uuid.UUID) -> Banner:
    banner = db.get(Banner, banner_id)
    if banner is None:
        raise AppError("banner_not_found", 404, "Unknown banner")
    return banner


def create_banner(db: Session, *, admin: Admin, body: BannerIn) -> Banner:
    banner = Banner(
        image_url=body.image_url,
        caption=body.caption,
        link_url=body.link_url,
        is_active=body.is_active,
        sort_order=body.sort_order,
    )
    db.add(banner)
    db.flush()
    record_audit(
        db,
        actor_admin_id=admin.id,
        action="create_banner",
        entity_type="banner",
        entity_id=banner.id,
        metadata={
            "image_url": banner.image_url,
            "is_active": banner.is_active,
            "sort_order": banner.sort_order,
        },
    )
    return banner


def update_banner(
    db: Session, *, admin: Admin, banner_id: uuid.UUID, body: BannerUpdateIn
) -> Banner:
    banner = _get_or_404(db, banner_id)
    changes = body.model_dump(exclude_unset=True)
    for field, value in changes.items():
        setattr(banner, field, value)
    record_audit(
        db,
        actor_admin_id=admin.id,
        action="update_banner",
        entity_type="banner",
        entity_id=banner.id,
        metadata={"changes": changes},
    )
    return banner


def delete_banner(db: Session, *, admin: Admin, banner_id: uuid.UUID) -> None:
    banner = _get_or_404(db, banner_id)
    record_audit(
        db,
        actor_admin_id=admin.id,
        action="delete_banner",
        entity_type="banner",
        entity_id=banner.id,
        metadata={"image_url": banner.image_url},
    )
    db.delete(banner)
