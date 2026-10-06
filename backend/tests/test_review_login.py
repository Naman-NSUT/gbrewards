"""The fixed sign-in Google Play's reviewers use.

They cannot receive an Indian SMS, so the app would be untestable without this.
One number accepts one fixed code; every other number still needs a real OTP.

These exist mostly to pin what it must NOT do. It is a guessable credential by
design, so the blast radius has to stay exactly one account: a wrong code on the
review number is still refused, a real number is unaffected, and disabling the
account still disables it.
"""

from app.core.config import settings
from app.models.user import User

REVIEW_PHONE = "+919999999999"
REVIEW_CODE = "999999"

PROFILE = {
    "name": "Play Review",
    "address": "Google Play review",
    "city": "Pune",
    "state": "Maharashtra",
    "pincode": "411001",
    "dob": "1990-01-01",
    "gender": "male",
}


def _request(client, phone=REVIEW_PHONE):  # type: ignore[no-untyped-def]
    return client.post("/api/v1/auth/otp/request", json={"phone": phone, **PROFILE})


def _verify(client, phone=REVIEW_PHONE, code=REVIEW_CODE):  # type: ignore[no-untyped-def]
    return client.post("/api/v1/auth/otp/verify", json={"phone": phone, "code": code})


def test_the_reviewer_can_sign_in_without_ever_receiving_an_sms(client):
    assert _request(client).status_code == 200

    resp = _verify(client)

    assert resp.status_code == 200, resp.text
    assert resp.json()["access_token"]


def test_verifying_works_even_with_no_prior_request(client, db):
    """A reinstall, or the account cleaned out between submissions."""
    resp = _verify(client)

    assert resp.status_code == 200, resp.text
    assert db.query(User).filter(User.phone == REVIEW_PHONE).one_or_none() is not None


def test_the_review_number_still_refuses_the_wrong_code(client):
    """One credential, not an open door on one number."""
    _request(client)

    assert _verify(client, code="123456").status_code == 400


def test_an_ordinary_number_cannot_use_the_review_code(client):
    """The bypass must be one account wide, not one code wide."""
    other = "+919812300044"
    _request(client, phone=other)

    assert _verify(client, phone=other).status_code in (400, 429), (
        "the fixed code must only ever work for the review number"
    )


def test_disabling_the_account_still_disables_it(client, db):
    _request(client)
    user = db.query(User).filter(User.phone == REVIEW_PHONE).one()
    user.is_active = False
    db.commit()

    assert _verify(client).status_code == 403


def test_it_can_be_switched_off_without_a_deploy(client, monkeypatch):
    """Review ends; the credential should be retirable from the environment."""
    monkeypatch.setattr(settings, "review_login_phone", "")

    assert _verify(client).status_code == 400, (
        "with no review phone configured this is just a bad code"
    )
