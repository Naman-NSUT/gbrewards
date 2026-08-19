"""Dealer Rewards router tree.

Three audiences, three prefixes, three auth dependencies:

    /api/v1/dealer/*        aud='dealer' — shop staff on the mobile app
    /api/v1/dealer-admin/*  aud='admin'  — the dealer back office
    /api/v1/public/*        NO auth      — rate limited, every response redacted

`dealer-admin` rather than `admin` because the worker back office already owns
/api/v1/admin. One admins table serves both panels, so a single login works in
either; the prefixes keep the two feature sets from colliding.
"""

from fastapi import APIRouter

from app.dealer.api.admin import (
    allocations,
    approvals,
    audit,
    claims,
    compliance,
    dashboard,
    dealers,
    lookup,
    points,
    products,
    rewards,
    sms,
    warranties,
)
from app.dealer.api.dealer import auth, corrections, profile, registrations
from app.dealer.api.dealer import rewards as dealer_rewards
from app.dealer.api.public import claims as public_claims
from app.dealer.api.public import confirm as public_confirm
from app.dealer.api.public import lookup as public_lookup
from app.dealer.api.public import self_registration as public_self_registration

dealer_api_router = APIRouter()

for _r in (auth, registrations, corrections, dealer_rewards, profile):
    dealer_api_router.include_router(_r.router, prefix="/dealer")

# NOTE: admin/_common.py is a helper module, not a router — do not mount it.
for _r in (
    dashboard,
    dealers,
    products,
    allocations,
    warranties,
    approvals,
    compliance,
    claims,
    points,
    rewards,
    sms,
    audit,
    lookup,
):
    dealer_api_router.include_router(_r.router, prefix="/dealer-admin")

for _r in (public_lookup, public_self_registration, public_claims, public_confirm):
    dealer_api_router.include_router(_r.router, prefix="/public")
