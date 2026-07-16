import uuid

from fastapi import APIRouter, Depends, Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, get_db
from app.core.errors import AppError
from app.models.banner import Banner
from app.models.content_doc import ContentDoc
from app.models.faq import Faq
from app.models.product import Product
from app.models.reward import Reward
from app.models.user import User
from app.schemas.catalog import (
    BannerOut,
    ContentDocOut,
    FaqPublicOut,
    ProductPointsOut,
    RewardOut,
)
from app.services import banners as banners_service
from app.services import content

router = APIRouter(tags=["catalog"])


@router.get("/products", response_model=list[ProductPointsOut])
def list_products(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[Product]:
    return list(
        db.execute(
            select(Product).where(Product.is_active.is_(True)).order_by(Product.name)
        ).scalars()
    )


@router.get("/rewards", response_model=list[RewardOut])
def list_rewards(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[Reward]:
    return list(
        db.execute(
            select(Reward)
            .where(Reward.is_active.is_(True))
            .order_by(Reward.sort_order, Reward.title)
        ).scalars()
    )


@router.get("/catalog/banners", response_model=list[BannerOut])
def list_banners(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[Banner]:
    return list(
        db.execute(
            select(Banner)
            .where(Banner.is_active.is_(True))
            .order_by(Banner.sort_order, Banner.created_at)
        ).scalars()
    )


@router.get("/catalog/banners/{banner_id}/image")
def get_banner_image(
    banner_id: uuid.UUID,
    db: Session = Depends(get_db),
) -> Response:
    """Serve an uploaded banner's image bytes. Public (no auth) so the mobile
    <Image> component can load it directly, like the static poster."""
    banner = banners_service.get_banner(db, banner_id)
    if not banner.image_data:
        raise AppError("banner_not_found", 404, "No image for this banner")
    return Response(
        content=banner.image_data,
        media_type=banner.image_mime or "image/jpeg",
        headers={"Cache-Control": "public, max-age=86400"},
    )


@router.get("/faqs", response_model=list[FaqPublicOut])
def list_faqs(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[Faq]:
    return list(
        db.execute(
            select(Faq)
            .where(Faq.is_published.is_(True))
            .order_by(Faq.sort_order, Faq.created_at)
        ).scalars()
    )


@router.get("/content/{key}", response_model=ContentDocOut)
def get_content(
    key: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ContentDoc:
    return content.get_content(db, key)
