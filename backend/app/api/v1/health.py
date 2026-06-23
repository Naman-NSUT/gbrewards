from typing import Any

from fastapi import APIRouter, Depends
from redis import Redis
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.deps import get_db, get_redis

router = APIRouter(tags=["health"])


@router.get("/healthz")
def healthz() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/readyz")
def readyz(
    db: Session = Depends(get_db),
    redis: Redis = Depends(get_redis),
) -> dict[str, Any]:
    db.execute(text("SELECT 1"))
    redis.ping()
    return {"status": "ready", "db": "ok", "redis": "ok"}
