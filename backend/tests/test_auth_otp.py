from fastapi.testclient import TestClient

from app.services.otp_provider import FakeOtpProvider


def _request(client: TestClient, phone: str, name: str, address: str) -> None:
    r = client.post(
        "/api/v1/auth/otp/request",
        json={"phone": phone, "name": name, "address": address},
    )
    assert r.status_code == 200, r.text
    assert r.json()["sent"] is True


def test_otp_flow_creates_user_and_issues_tokens(
    client: TestClient, fake_otp: FakeOtpProvider
) -> None:
    phone = "+919900000001"
    _request(client, phone, "Alice", "12 MG Road, Pune")

    code = fake_otp.last_codes[phone]
    r = client.post("/api/v1/auth/otp/verify", json={"phone": phone, "code": code})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["access_token"]
    assert body["refresh_token"]
    assert body["user"]["phone"] == phone
    assert body["user"]["name"] == "Alice"
    assert body["user"]["address"] == "12 MG Road, Pune"
    assert body["user"]["is_verified"] is True


def test_otp_request_is_idempotent_and_updates_profile(
    client: TestClient, fake_otp: FakeOtpProvider
) -> None:
    phone = "+919900000002"
    _request(client, phone, "Bob", "Old address")
    first = client.post(
        "/api/v1/auth/otp/verify", json={"phone": phone, "code": fake_otp.last_codes[phone]}
    )
    assert first.status_code == 200, first.text
    first_id = first.json()["user"]["id"]

    # Same phone re-requests: same account, refreshed name + address.
    _request(client, phone, "Bobby", "New address")
    second = client.post(
        "/api/v1/auth/otp/verify", json={"phone": phone, "code": fake_otp.last_codes[phone]}
    )
    assert second.status_code == 200, second.text
    assert second.json()["user"]["id"] == first_id
    assert second.json()["user"]["name"] == "Bobby"
    assert second.json()["user"]["address"] == "New address"


def test_verify_rejects_wrong_code(client: TestClient) -> None:
    phone = "+919900000004"
    _request(client, phone, "Dana", "Somewhere")
    r = client.post("/api/v1/auth/otp/verify", json={"phone": phone, "code": "000000"})
    assert r.status_code == 400
    assert r.json()["error"]["code"] == "invalid_otp"


def test_verify_without_request_is_expired(client: TestClient) -> None:
    r = client.post("/api/v1/auth/otp/verify", json={"phone": "+919900000005", "code": "123456"})
    assert r.status_code == 400
    assert r.json()["error"]["code"] == "otp_expired"


def test_request_requires_name_and_address(client: TestClient) -> None:
    r = client.post("/api/v1/auth/otp/request", json={"phone": "+919900000003"})
    assert r.status_code == 422

    r = client.post(
        "/api/v1/auth/otp/request",
        json={"phone": "+919900000003", "name": "", "address": ""},
    )
    assert r.status_code == 422


def test_request_rejects_bad_phone(client: TestClient) -> None:
    r = client.post(
        "/api/v1/auth/otp/request",
        json={"phone": "98765", "name": "Carol", "address": "Somewhere"},
    )
    assert r.status_code == 422
