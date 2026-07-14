from fastapi import APIRouter

from app.api.v1.admin import (
    account,
    auth,
    content,
    faqs,
    products,
    redemptions,
    reporting,
    rewards,
    units,
    users,
)

admin_router = APIRouter(prefix="/admin")
admin_router.include_router(auth.router)
admin_router.include_router(account.router)
admin_router.include_router(products.router)
admin_router.include_router(units.router)
admin_router.include_router(users.router)
admin_router.include_router(redemptions.router)
admin_router.include_router(reporting.router)
admin_router.include_router(rewards.router)
admin_router.include_router(faqs.router)
admin_router.include_router(content.router)
