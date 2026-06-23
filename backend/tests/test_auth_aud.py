from datetime import UTC, datetime, timedelta

import jwt
import pytest

from app.core.config import settings
from app.core.errors import AppError
from app.core.security import create_access_token, create_refresh_token, decode_token


def test_broker_token_rejected_as_admin() -> None:
    token = create_access_token(sub="abc", aud="broker")
    with pytest.raises(AppError) as exc:
        decode_token(token, expected_aud="admin", expected_type="access")
    assert exc.value.code == "invalid_token"


def test_access_token_rejected_where_refresh_expected() -> None:
    token = create_access_token(sub="abc")
    with pytest.raises(AppError) as exc:
        decode_token(token, expected_aud="broker", expected_type="refresh")
    assert exc.value.code == "invalid_token"


def test_refresh_token_rejected_where_access_expected() -> None:
    token, _ = create_refresh_token(sub="abc")
    with pytest.raises(AppError) as exc:
        decode_token(token, expected_aud="broker", expected_type="access")
    assert exc.value.code == "invalid_token"


def test_expired_token_rejected() -> None:
    now = datetime.now(UTC)
    token = jwt.encode(
        {
            "sub": "abc",
            "aud": "broker",
            "type": "access",
            "iat": now - timedelta(hours=2),
            "exp": now - timedelta(hours=1),
            "jti": "x",
        },
        settings.jwt_secret,
        algorithm="HS256",
    )
    with pytest.raises(AppError) as exc:
        decode_token(token, expected_aud="broker", expected_type="access")
    assert exc.value.code == "invalid_token"


def test_refresh_token_rejected_as_bearer_on_me(client) -> None:  # type: ignore[no-untyped-def]
    refresh, _ = create_refresh_token(sub="abc")
    r = client.get("/api/v1/me", headers={"Authorization": f"Bearer {refresh}"})
    assert r.status_code == 401
    assert r.json()["error"]["code"] == "invalid_token"
