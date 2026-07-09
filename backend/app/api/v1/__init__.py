from fastapi import APIRouter

from app.api.v1 import auth, health, me, redemptions, scan
from app.api.v1.admin import admin_router

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(health.router)
api_router.include_router(auth.router)
api_router.include_router(scan.router)
api_router.include_router(me.router)
api_router.include_router(redemptions.router)
api_router.include_router(admin_router)
