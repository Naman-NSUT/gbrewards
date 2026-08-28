"""The promotional carousel on the dealer app's home screen.

Deliberately reads the WORKER programme's `banners` table rather than adding a
dealer-specific one. Everywhere else the two programmes are kept strictly apart
— separate products, separate registries, separate operators — because that
separation protects data that belongs to different populations and different
money. A banner is neither: it is GoodBed marketing artwork, it is already
managed from a back office the client uses daily, and giving it a second table
would mean the same poster uploaded twice and drifting apart.

The images themselves need nothing new: `/catalog/banners/{id}/image` is already
public so an <Image> can load it without a token, and only the LIST was gated to
worker accounts.
"""

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.deps import get_current_staff, get_db
from app.dealer.models.dealer import DealerStaff
from app.models.banner import Banner
from app.schemas.admin import BannerOut

router = APIRouter(tags=["dealer-banners"])


@router.get("/banners", response_model=list[BannerOut])
def list_banners(
    _staff: DealerStaff = Depends(get_current_staff),
    db: Session = Depends(get_db),
) -> list[Banner]:
    """Active banners, in the order the back office arranged them.

    Same rows and same ordering the worker app sees, so a poster published once
    appears in both apps without anyone republishing it.
    """
    return list(
        db.execute(
            select(Banner)
            .where(Banner.is_active.is_(True))
            .order_by(Banner.sort_order, Banner.created_at)
        ).scalars()
    )
