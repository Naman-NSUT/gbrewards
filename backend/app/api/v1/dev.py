"""Dev-only helpers. Router is only mounted when ENV=dev (see api/v1/__init__)."""

from fastapi import APIRouter

from app.core.errors import AppError
from app.services.otp_provider import FakeOtpProvider, get_otp_provider

router = APIRouter(prefix="/_dev", tags=["dev"])


@router.get("/otp/{phone}")
def peek_otp(phone: str) -> dict[str, str]:
    provider = get_otp_provider()
    if not isinstance(provider, FakeOtpProvider):
        raise AppError("not_available", 404, "Only available with the fake OTP provider")
    code = provider.last_codes.get(phone)
    if code is None:
        raise AppError("invalid_code", 404, "No code outstanding for this phone")
    return {"phone": phone, "code": code}
