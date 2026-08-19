"""Ad-carousel banner CRUD with admin audit (mutations write audit, GET does not).

Banners are uploaded as image files: the bytes are processed (auto-oriented,
flattened, resized/optimized) and stored in the DB so they survive redeploys on
ephemeral hosting. `image_url` then points at the serve endpoint. External/static
URLs are still supported for the seeded default poster.
"""

import io
import uuid

from PIL import Image, ImageOps
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.models.admin import Admin
from app.models.banner import Banner
from app.schemas.admin import BannerUpdateIn
from app.services.audit import record_audit

# Ad banners render full-width; 1600px wide is plenty for any phone and keeps the
# stored bytes small. Larger uploads are downscaled; smaller ones are left as-is.
MAX_WIDTH = 1600


def process_banner_image(raw: bytes) -> tuple[bytes, str]:
    """Normalise an uploaded image: honour EXIF orientation, flatten onto white,
    cap the width, and re-encode as optimised JPEG. Returns (bytes, mime)."""
    try:
        img: Image.Image = Image.open(io.BytesIO(raw))
        img = ImageOps.exif_transpose(img)  # phones store rotation in EXIF
    except Exception as exc:  # noqa: BLE001 - surface any decode failure uniformly
        raise AppError(
            "invalid_image", 400, "Could not read the uploaded image", {"reason": str(exc)}
        ) from exc

    if img.mode in ("RGBA", "LA", "P"):
        img = img.convert("RGBA")
        flattened = Image.new("RGB", img.size, (255, 255, 255))
        flattened.paste(img, mask=img.split()[-1])
        img = flattened
    else:
        img = img.convert("RGB")

    if img.width > MAX_WIDTH:
        height = round(img.height * MAX_WIDTH / img.width)
        img = img.resize((MAX_WIDTH, height), Image.Resampling.LANCZOS)

    out = io.BytesIO()
    img.save(out, format="JPEG", quality=82, optimize=True)
    return out.getvalue(), "image/jpeg"


def list_banners(db: Session) -> list[Banner]:
    return list(db.execute(select(Banner).order_by(Banner.sort_order, Banner.created_at)).scalars())


def get_banner(db: Session, banner_id: uuid.UUID) -> Banner:
    return _get_or_404(db, banner_id)


def _get_or_404(db: Session, banner_id: uuid.UUID) -> Banner:
    banner = db.get(Banner, banner_id)
    if banner is None:
        raise AppError("banner_not_found", 404, "Unknown banner")
    return banner


def _apply_image(banner: Banner, raw_image: bytes) -> None:
    """Store a processed image on the banner and point image_url at the serve
    endpoint. Requires the banner to already have an id (call after flush)."""
    data, mime = process_banner_image(raw_image)
    banner.image_data = data
    banner.image_mime = mime
    banner.image_url = f"/api/v1/catalog/banners/{banner.id}/image"


def create_banner_from_upload(
    db: Session,
    *,
    admin: Admin,
    raw_image: bytes,
    caption: str | None,
    link_url: str | None,
    is_active: bool,
    sort_order: int,
) -> Banner:
    banner = Banner(
        image_url="",  # replaced by _apply_image once we have an id
        caption=caption,
        link_url=link_url,
        is_active=is_active,
        sort_order=sort_order,
    )
    db.add(banner)
    db.flush()  # assign the id used in the serve URL
    _apply_image(banner, raw_image)
    db.flush()
    record_audit(
        db,
        actor_admin_id=admin.id,
        action="create_banner",
        entity_type="banner",
        entity_id=banner.id,
        metadata={
            "uploaded": True,
            "bytes": len(banner.image_data or b""),
            "is_active": banner.is_active,
            "sort_order": banner.sort_order,
        },
    )
    return banner


def update_banner(
    db: Session,
    *,
    admin: Admin,
    banner_id: uuid.UUID,
    body: BannerUpdateIn,
    raw_image: bytes | None = None,
) -> Banner:
    banner = _get_or_404(db, banner_id)
    changes = body.model_dump(exclude_unset=True)
    for field, value in changes.items():
        setattr(banner, field, value)
    if raw_image is not None:
        _apply_image(banner, raw_image)
        changes["image"] = "replaced"
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
