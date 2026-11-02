import uuid

from fastapi import APIRouter, Depends, File, Form, Request, UploadFile
from sqlalchemy.orm import Session

from app.core.deps import get_current_admin, get_db
from app.core.errors import AppError
from app.models.admin import Admin
from app.models.banner import Banner
from app.schemas.admin import BannerOut, BannerUpdateIn
from app.services import banners

router = APIRouter(tags=["admin-banners"])

# Raw upload cap before processing; the stored JPEG is far smaller.
MAX_UPLOAD_BYTES = 15 * 1024 * 1024


async def _read_upload(image: UploadFile) -> bytes:
    raw = await image.read()
    if not raw:
        raise AppError("invalid_image", 400, "The uploaded image is empty")
    if len(raw) > MAX_UPLOAD_BYTES:
        raise AppError("image_too_large", 413, "Image exceeds the 15 MB upload limit")
    return raw


@router.get("/banners", response_model=list[BannerOut])
def list_banners(
    admin: Admin = Depends(get_current_admin),
    db: Session = Depends(get_db),
) -> list[Banner]:
    return banners.list_banners(db)


@router.post("/banners", response_model=BannerOut, status_code=201)
async def create_banner(
    image: UploadFile = File(...),
    caption: str | None = Form(None),
    link_url: str | None = Form(None),
    is_active: bool = Form(True),
    sort_order: int = Form(0),
    admin: Admin = Depends(get_current_admin),
    db: Session = Depends(get_db),
) -> Banner:
    raw = await _read_upload(image)
    banner = banners.create_banner_from_upload(
        db,
        admin=admin,
        raw_image=raw,
        caption=caption or None,
        link_url=link_url or None,
        is_active=is_active,
        sort_order=sort_order,
    )
    db.commit()
    db.refresh(banner)
    return banner


@router.patch("/banners/{banner_id}", response_model=BannerOut)
async def update_banner(
    banner_id: uuid.UUID,
    request: Request,
    image: UploadFile | None = File(None),
    caption: str | None = Form(None),
    link_url: str | None = Form(None),
    is_active: bool | None = Form(None),
    sort_order: int | None = Form(None),
    admin: Admin = Depends(get_current_admin),
    db: Session = Depends(get_db),
) -> Banner:
    # None means "field not provided" — only apply what was actually sent.
    fields: dict[str, object] = {}

    # The two free-text fields are read from the raw form rather than from the
    # parameters above, because FastAPI substitutes a Form field's default when
    # the submitted value is an empty string (dependencies/utils.py: `value ==
    # ""` is treated as absent). That makes "clear this caption" indistinguishable
    # from "leave it alone", so a caption could never be removed once set —
    # including from the admin panel, which sends "" for a cleared field.
    # Starlette caches the parsed form, so this re-reads rather than re-parses.
    form = await request.form()
    for name in ("caption", "link_url"):
        if name not in form:
            continue
        submitted = form[name]
        if isinstance(submitted, str):
            # Store absence as NULL rather than an empty string, so there is one
            # representation of "no caption" for the app to test.
            fields[name] = submitted or None

    if is_active is not None:
        fields["is_active"] = is_active
    if sort_order is not None:
        fields["sort_order"] = sort_order
    raw = await _read_upload(image) if image is not None else None
    banner = banners.update_banner(
        db,
        admin=admin,
        banner_id=banner_id,
        body=BannerUpdateIn.model_validate(fields),
        raw_image=raw,
    )
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
