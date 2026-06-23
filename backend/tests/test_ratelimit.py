import fakeredis
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.errors import AppError
from app.services.ratelimit import enforce_rate
from tests.factories import auth_headers, make_product, make_unit, make_user


def test_enforce_rate_allows_then_blocks() -> None:
    r = fakeredis.FakeRedis(decode_responses=True)
    for _ in range(3):
        enforce_rate(r, "k", limit=3, window_s=60)
    with pytest.raises(AppError) as exc:
        enforce_rate(r, "k", limit=3, window_s=60)
    assert exc.value.code == "rate_limited"
    assert exc.value.status_code == 429


def test_scan_endpoint_rate_limited(
    client: TestClient, db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "scan_rate_per_min", 2)
    user = make_user(db)
    product = make_product(db, points_value=10)
    units = [make_unit(db, product=product) for _ in range(4)]
    db.commit()
    h = auth_headers(user)

    # first 2 succeed (distinct fresh codes)
    assert (
        client.post("/api/v1/scan/claim", headers=h, json={"token": units[0].token}).status_code
        == 200
    )
    assert (
        client.post("/api/v1/scan/claim", headers=h, json={"token": units[1].token}).status_code
        == 200
    )
    # 3rd is rate limited (before the claim even runs)
    r = client.post("/api/v1/scan/claim", headers=h, json={"token": units[2].token})
    assert r.status_code == 429
    assert r.json()["error"]["code"] == "rate_limited"
