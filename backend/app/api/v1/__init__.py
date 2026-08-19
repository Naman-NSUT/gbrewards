from fastapi import APIRouter

from app.api.v1 import auth, catalog, health, me, redemptions, scan
from app.api.v1.admin import admin_router
from app.dealer.api import dealer_api_router

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(health.router)
api_router.include_router(auth.router)
api_router.include_router(scan.router)
api_router.include_router(me.router)
api_router.include_router(redemptions.router)
api_router.include_router(catalog.router)
api_router.include_router(admin_router)

# Dealer Rewards. Mounted under its own prefixes so the worker surfaces above
# are untouched:
#   /api/v1/dealer/*        aud='dealer'  — shop staff on the dealer app
#   /api/v1/dealer-admin/*  aud='admin'   — the dealer back office
#   /api/v1/public/*        no auth       — the customer support site
api_router.include_router(dealer_api_router)
