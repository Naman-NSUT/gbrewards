from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.deps import get_current_admin, get_db
from app.core.errors import AppError
from app.core.security import hash_secret, verify_secret
from app.models.admin import Admin
from app.schemas.admin import (
    AdminOut,
    AdminPasswordChangeIn,
    AdminProfileUpdateIn,
)
from app.services.audit import record_audit

router = APIRouter(prefix="/me", tags=["admin-account"])


@router.get("", response_model=AdminOut)
def get_me(admin: Admin = Depends(get_current_admin)) -> Admin:
    return admin


@router.patch("", response_model=AdminOut)
def update_me(
    body: AdminProfileUpdateIn,
    admin: Admin = Depends(get_current_admin),
    db: Session = Depends(get_db),
) -> Admin:
    if body.email is not None and body.email != admin.email:
        taken = db.execute(
            select(Admin).where(Admin.email == body.email, Admin.id != admin.id)
        ).scalar_one_or_none()
        if taken is not None:
            raise AppError("email_taken", 409, "That username/email is already in use")
        admin.email = body.email
    if body.name is not None:
        admin.name = body.name
    record_audit(
        db,
        actor_admin_id=admin.id,
        action="update_admin",
        entity_type="admin",
        entity_id=admin.id,
        metadata=body.model_dump(exclude_none=True),
    )
    db.commit()
    db.refresh(admin)
    return admin


@router.post("/password", status_code=204)
def change_password(
    body: AdminPasswordChangeIn,
    admin: Admin = Depends(get_current_admin),
    db: Session = Depends(get_db),
) -> None:
    if not verify_secret(admin.password_hash, body.current_password):
        raise AppError("invalid_credentials", 401, "Current password is incorrect")
    admin.password_hash = hash_secret(body.new_password)
    record_audit(
        db,
        actor_admin_id=admin.id,
        action="change_password",
        entity_type="admin",
        entity_id=admin.id,
    )
    db.commit()
