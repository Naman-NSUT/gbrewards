"""Auth-domain separation enforced on every protected route (invariant §9)."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from tests.factories import admin_headers, auth_headers, make_admin, make_user

ADMIN_GET_ROUTES = [
    "/api/v1/admin/products",
    "/api/v1/admin/units",
    "/api/v1/admin/users",
    "/api/v1/admin/redemptions",
    "/api/v1/admin/dashboard",
    "/api/v1/admin/scans",
    "/api/v1/admin/audit",
]

BROKER_GET_ROUTES = [
    "/api/v1/me",
    "/api/v1/me/ledger",
    "/api/v1/redemptions",
]


@pytest.mark.parametrize("route", ADMIN_GET_ROUTES)
def test_broker_token_rejected_on_admin_routes(client: TestClient, db: Session, route: str) -> None:
    user = make_user(db)
    db.commit()
    r = client.get(route, headers=auth_headers(user))
    assert r.status_code == 401
    assert r.json()["error"]["code"] == "invalid_token"


@pytest.mark.parametrize("route", BROKER_GET_ROUTES)
def test_admin_token_rejected_on_broker_routes(client: TestClient, db: Session, route: str) -> None:
    admin = make_admin(db)
    db.commit()
    r = client.get(route, headers=admin_headers(admin))
    assert r.status_code == 401
    assert r.json()["error"]["code"] == "invalid_token"


def test_unauthenticated_rejected(client: TestClient) -> None:
    for route in [*ADMIN_GET_ROUTES, *BROKER_GET_ROUTES]:
        r = client.get(route)
        assert r.status_code == 401, route
