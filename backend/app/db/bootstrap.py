from app.core.config import settings
from app.core.logging import get_logger
from app.core.security import hash_secret
from app.db.session import SessionLocal
from app.models.admin import Admin

logger = get_logger("bootstrap")


def ensure_bootstrap_admin() -> None:
    """Create the configured admin account if it doesn't exist yet.

    No-op unless BOOTSTRAP_ADMIN_EMAIL/BOOTSTRAP_ADMIN_PASSWORD are set — lets
    environments without shell access (e.g. Render's free plan) get a first
    admin by setting env vars and redeploying, instead of running the CLI.
    """
    if not settings.bootstrap_admin_email or not settings.bootstrap_admin_password:
        return
    with SessionLocal() as db:
        existing = db.query(Admin).filter(Admin.email == settings.bootstrap_admin_email).one_or_none()
        if existing is not None:
            return
        db.add(
            Admin(
                email=settings.bootstrap_admin_email,
                password_hash=hash_secret(settings.bootstrap_admin_password),
                role="owner",
            )
        )
        db.commit()
        logger.info("bootstrap admin created: %s", settings.bootstrap_admin_email)
