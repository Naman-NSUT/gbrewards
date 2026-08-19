"""First-run bootstrap for the dealer back office.

The dealer programme authenticates against `dealer_admins`, which starts empty.
Render's plan has no shell, so without an env-driven path the panel would deploy
with nobody able to sign in.

Mirrors the worker programme's ensure_bootstrap_admin. Both are idempotent and
both should have their env vars cleared once the account exists — a password
sitting in the service's environment is a password in every deploy log.
"""

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.core.config import settings
from app.core.logging import get_logger
from app.core.security import hash_password
from app.db.session import SessionLocal
from app.dealer.models.admin import DealerAdmin

logger = get_logger(__name__)


def ensure_bootstrap_dealer_admin() -> None:
    if not (settings.dealer_bootstrap_admin_email and settings.dealer_bootstrap_admin_password):
        return

    email = settings.dealer_bootstrap_admin_email.lower().strip()
    with SessionLocal() as db:
        existing = db.execute(
            select(DealerAdmin).where(DealerAdmin.email == email)
        ).scalar_one_or_none()
        if existing is not None:
            return
        db.add(
            DealerAdmin(
                email=email,
                password_hash=hash_password(settings.dealer_bootstrap_admin_password),
                name="Dealer Owner",
                role="owner",
            )
        )
        try:
            db.commit()
        except IntegrityError:
            # Another instance won the race at the same boot. Correct outcome,
            # but an unhandled error here would crash this instance on startup.
            db.rollback()
            return
        logger.info("bootstrap_dealer_admin_created email=%s", email)
