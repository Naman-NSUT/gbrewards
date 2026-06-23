from fastapi import APIRouter

from app.api.v1 import auth, health, me, redemptions, scan
from app.api.v1 import dev as dev_router
from app.api.v1.admin import admin_router
from app.core.config import settings

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(health.router)
api_router.include_router(auth.router)
api_router.include_router(scan.router)
api_router.include_router(me.router)
api_router.include_router(redemptions.router)
api_router.include_router(admin_router)

if settings.env == "dev":
    api_router.include_router(dev_router.router)
