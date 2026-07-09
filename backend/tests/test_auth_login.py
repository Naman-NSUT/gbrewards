from fastapi.testclient import TestClient


def test_login_creates_user_and_issues_tokens(client: TestClient) -> None:
    phone = "+919900000001"
    r = client.post(
        "/api/v1/auth/login",
        json={"phone": phone, "name": "Alice", "address": "12 MG Road, Pune"},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["access_token"]
    assert body["refresh_token"]
    assert body["user"]["phone"] == phone
    assert body["user"]["name"] == "Alice"
    assert body["user"]["address"] == "12 MG Road, Pune"
    assert body["user"]["is_verified"] is True


def test_login_is_idempotent_and_updates_profile(client: TestClient) -> None:
    phone = "+919900000002"
    first = client.post(
        "/api/v1/auth/login",
        json={"phone": phone, "name": "Bob", "address": "Old address"},
    )
    assert first.status_code == 200, first.text
    first_id = first.json()["user"]["id"]

    # Same phone logs into the same account, refreshing name + address.
    second = client.post(
        "/api/v1/auth/login",
        json={"phone": phone, "name": "Bobby", "address": "New address"},
    )
    assert second.status_code == 200, second.text
    assert second.json()["user"]["id"] == first_id
    assert second.json()["user"]["name"] == "Bobby"
    assert second.json()["user"]["address"] == "New address"


def test_login_requires_name_and_address(client: TestClient) -> None:
    r = client.post("/api/v1/auth/login", json={"phone": "+919900000003"})
    assert r.status_code == 422

    r = client.post(
        "/api/v1/auth/login",
        json={"phone": "+919900000003", "name": "", "address": ""},
    )
    assert r.status_code == 422


def test_login_rejects_bad_phone(client: TestClient) -> None:
    r = client.post(
        "/api/v1/auth/login",
        json={"phone": "98765", "name": "Carol", "address": "Somewhere"},
    )
    assert r.status_code == 422
