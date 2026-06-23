import fakeredis
from fastapi.testclient import TestClient

from app.services.otp_provider import FakeOtpProvider, get_otp_provider


def _onboard(client: TestClient, phone: str) -> dict:
    client.post("/api/v1/auth/otp/request", json={"phone": phone, "name": "Refresh User"})
    provider = get_otp_provider()
    assert isinstance(provider, FakeOtpProvider)
    code = provider.last_codes[phone]
    r = client.post("/api/v1/auth/otp/verify", json={"phone": phone, "code": code})
    assert r.status_code == 200, r.text
    return r.json()


def test_refresh_rotates_and_revokes_old(client: TestClient, redis: fakeredis.FakeRedis) -> None:
    tokens = _onboard(client, "+919900500001")
    old_refresh = tokens["refresh_token"]

    r = client.post("/api/v1/auth/refresh", json={"refresh_token": old_refresh})
    assert r.status_code == 200, r.text
    new_refresh = r.json()["refresh_token"]
    assert new_refresh != old_refresh

    # the rotated (old) refresh token is now denylisted
    r2 = client.post("/api/v1/auth/refresh", json={"refresh_token": old_refresh})
    assert r2.status_code == 401
    assert r2.json()["error"]["code"] == "invalid_token"

    # the new one still works
    r3 = client.post("/api/v1/auth/refresh", json={"refresh_token": new_refresh})
    assert r3.status_code == 200


def test_logout_revokes_refresh(client: TestClient) -> None:
    tokens = _onboard(client, "+919900500002")
    refresh = tokens["refresh_token"]

    assert client.post("/api/v1/auth/logout", json={"refresh_token": refresh}).status_code == 204
    r = client.post("/api/v1/auth/refresh", json={"refresh_token": refresh})
    assert r.status_code == 401
    assert r.json()["error"]["code"] == "invalid_token"


def test_access_token_cannot_be_used_to_refresh(client: TestClient) -> None:
    tokens = _onboard(client, "+919900500003")
    r = client.post("/api/v1/auth/refresh", json={"refresh_token": tokens["access_token"]})
    assert r.status_code == 401
    assert r.json()["error"]["code"] == "invalid_token"
