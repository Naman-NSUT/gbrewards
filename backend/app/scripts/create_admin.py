"""Create an admin account.

Usage: uv run python -m app.scripts.create_admin <email> <password> [name] [role]
  role defaults to 'owner'.
"""

import sys

from app.core.security import hash_secret
from app.db.session import SessionLocal
from app.models.admin import Admin


def main(email: str, password: str, name: str | None = None, role: str = "owner") -> None:
    with SessionLocal() as db:
        existing = db.query(Admin).filter(Admin.email == email).one_or_none()
        if existing is not None:
            raise SystemExit(f"admin already exists: {email}")
        admin = Admin(
            email=email,
            password_hash=hash_secret(password),
            name=name,
            role=role,
        )
        db.add(admin)
        db.commit()
        print(f"created admin {email} (role={role}) id={admin.id}")


if __name__ == "__main__":
    if len(sys.argv) < 3:
        raise SystemExit(
            "usage: python -m app.scripts.create_admin <email> <password> [name] [role]"
        )
    args = sys.argv[1:]
    main(*args)
