"""Structured address, DOB and gender captured at sign-in and on PATCH /me."""

from datetime import date

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.services.otp_provider import FakeOtpProvider
from tests.factories import admin_headers, make_admin

FULL_PROFILE = {
    "name": "Asha Rao",
    "address": "12 MG Road",
    "city": "Pune",
    "state": "Maharashtra",
    "pincode": "411001",
    "dob": "1990-04-17",
    "gender": "female",
}


def _sign_in(
    client: TestClient, fake_otp: FakeOtpProvider, phone: str, **overrides: object
) -> dict:
    payload = {"phone": phone, **FULL_PROFILE, **overrides}
    r = client.post("/api/v1/auth/otp/request", json=payload)
    assert r.status_code == 200, r.text
    verify = client.post(
        "/api/v1/auth/otp/verify", json={"phone": phone, "code": fake_otp.last_codes[phone]}
    )
    assert verify.status_code == 200, verify.text
    return verify.json()


def test_signin_captures_every_profile_field(client: TestClient, fake_otp: FakeOtpProvider) -> None:
    user = _sign_in(client, fake_otp, "+919900001001")["user"]
    for field, expected in FULL_PROFILE.items():
        assert user[field] == expected


def test_omitted_fields_do_not_blank_stored_values(
    client: TestClient, fake_otp: FakeOtpProvider
) -> None:
    """An older app build sends only name + address; the rest must survive."""
    phone = "+919900001002"
    _sign_in(client, fake_otp, phone)

    r = client.post(
        "/api/v1/auth/otp/request",
        json={"phone": phone, "name": "Asha R", "address": "13 MG Road"},
    )
    assert r.status_code == 200, r.text
    user = client.post(
        "/api/v1/auth/otp/verify", json={"phone": phone, "code": fake_otp.last_codes[phone]}
    ).json()["user"]

    assert user["name"] == "Asha R"
    assert user["address"] == "13 MG Road"
    assert user["city"] == "Pune"
    assert user["pincode"] == "411001"
    assert user["dob"] == "1990-04-17"
    assert user["gender"] == "female"


def test_under_18_is_rejected(client: TestClient) -> None:
    today = date.today()
    seventeen = today.replace(year=today.year - 17).isoformat()
    r = client.post(
        "/api/v1/auth/otp/request",
        json={"phone": "+919900001003", **FULL_PROFILE, "dob": seventeen},
    )
    assert r.status_code == 422
    assert r.json()["error"]["code"] == "validation_error"


def test_future_dob_is_rejected(client: TestClient) -> None:
    today = date.today()
    r = client.post(
        "/api/v1/auth/otp/request",
        json={
            "phone": "+919900001004",
            **FULL_PROFILE,
            "dob": today.replace(year=today.year + 1).isoformat(),
        },
    )
    assert r.status_code == 422


def test_bad_pincode_and_gender_are_rejected(client: TestClient) -> None:
    for bad in ({"pincode": "41100"}, {"pincode": "abc123"}, {"gender": "other"}):
        r = client.post(
            "/api/v1/auth/otp/request",
            json={"phone": "+919900001005", **FULL_PROFILE, **bad},
        )
        assert r.status_code == 422, f"{bad} should be rejected: {r.text}"


def test_me_returns_and_patches_profile_fields(
    client: TestClient, fake_otp: FakeOtpProvider
) -> None:
    tokens = _sign_in(client, fake_otp, "+919900001006")
    auth = {"Authorization": f"Bearer {tokens['access_token']}"}

    me = client.get("/api/v1/me", headers=auth)
    assert me.status_code == 200, me.text
    assert me.json()["city"] == "Pune"
    assert me.json()["gender"] == "female"

    patched = client.patch(
        "/api/v1/me",
        headers=auth,
        json={"city": "Mumbai", "pincode": "400001"},
    )
    assert patched.status_code == 200, patched.text
    body = patched.json()
    assert body["city"] == "Mumbai"
    assert body["pincode"] == "400001"
    # Untouched fields keep their values.
    assert body["state"] == "Maharashtra"
    assert body["address"] == "12 MG Road"


def test_admin_user_detail_exposes_profile(
    client: TestClient, fake_otp: FakeOtpProvider, db: Session
) -> None:
    """Staff need the full postal address to fulfil a redemption."""
    tokens = _sign_in(client, fake_otp, "+919900001008")
    user_id = tokens["user"]["id"]

    admin = make_admin(db)
    r = client.get(f"/api/v1/admin/users/{user_id}", headers=admin_headers(admin))
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["address"] == "12 MG Road"
    assert body["city"] == "Pune"
    assert body["state"] == "Maharashtra"
    assert body["pincode"] == "411001"
    assert body["dob"] == "1990-04-17"
    assert body["gender"] == "female"


def test_me_patch_rejects_invalid_pincode(client: TestClient, fake_otp: FakeOtpProvider) -> None:
    tokens = _sign_in(client, fake_otp, "+919900001007")
    auth = {"Authorization": f"Bearer {tokens['access_token']}"}
    r = client.patch("/api/v1/me", headers=auth, json={"pincode": "12"})
    assert r.status_code == 422
