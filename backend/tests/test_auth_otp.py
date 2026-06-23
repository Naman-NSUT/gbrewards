import fakeredis
from fastapi.testclient import TestClient

from app.services.otp_provider import FakeOtpProvider, get_otp_provider


def _provider() -> FakeOtpProvider:
    provider = get_otp_provider()
    assert isinstance(provider, FakeOtpProvider)
    return provider


def test_full_otp_flow(client: TestClient) -> None:
    phone = "+919900000001"
    r = client.post("/api/v1/auth/otp/request", json={"phone": phone, "name": "Alice"})
    assert r.status_code == 200, r.text
    code = _provider().last_codes[phone]

    r = client.post("/api/v1/auth/otp/verify", json={"phone": phone, "code": code})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["access_token"]
    assert body["refresh_token"]
    assert body["user"]["phone"] == phone
    assert body["user"]["is_verified"] is True


def test_new_phone_requires_name(client: TestClient) -> None:
    r = client.post("/api/v1/auth/otp/request", json={"phone": "+919900000002"})
    assert r.status_code == 400
    assert r.json()["error"]["code"] == "validation_error"


def test_wrong_code_rejected(client: TestClient) -> None:
    phone = "+919900000003"
    client.post("/api/v1/auth/otp/request", json={"phone": phone, "name": "Bob"})
    r = client.post("/api/v1/auth/otp/verify", json={"phone": phone, "code": "000000"})
    assert r.status_code == 400
    assert r.json()["error"]["code"] == "invalid_otp"


def test_expired_or_unrequested_code(client: TestClient, redis: fakeredis.FakeRedis) -> None:
    phone = "+919900000004"
    client.post("/api/v1/auth/otp/request", json={"phone": phone, "name": "Carol"})
    redis.delete(f"otp:{phone}")
    code = _provider().last_codes[phone]
    r = client.post("/api/v1/auth/otp/verify", json={"phone": phone, "code": code})
    assert r.status_code == 400
    assert r.json()["error"]["code"] == "otp_expired"


def test_attempts_capped(client: TestClient) -> None:
    phone = "+919900000005"
    client.post("/api/v1/auth/otp/request", json={"phone": phone, "name": "Dan"})
    for _ in range(5):
        client.post("/api/v1/auth/otp/verify", json={"phone": phone, "code": "111111"})
    r = client.post("/api/v1/auth/otp/verify", json={"phone": phone, "code": "111111"})
    assert r.status_code == 429
    assert r.json()["error"]["code"] == "otp_too_many_attempts"


def test_resend_cooldown(client: TestClient) -> None:
    phone = "+919900000006"
    client.post("/api/v1/auth/otp/request", json={"phone": phone, "name": "Eve"})
    r = client.post("/api/v1/auth/otp/request", json={"phone": phone, "name": "Eve"})
    assert r.status_code == 429
    assert r.json()["error"]["code"] == "otp_cooldown"


def test_daily_cap(client: TestClient, redis: fakeredis.FakeRedis) -> None:
    phone = "+919900000007"
    for _ in range(5):
        redis.delete(f"otp:cooldown:{phone}")
        client.post("/api/v1/auth/otp/request", json={"phone": phone, "name": "Fae"})
    redis.delete(f"otp:cooldown:{phone}")
    r = client.post("/api/v1/auth/otp/request", json={"phone": phone, "name": "Fae"})
    assert r.status_code == 429
    assert r.json()["error"]["code"] == "otp_daily_cap"
