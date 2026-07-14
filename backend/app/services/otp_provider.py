"""OTP delivery provider abstraction (PRD D5).

The backend always generates and stores the code; providers are transport only.
`FakeOtpProvider` records codes in-memory for dev/test introspection.
"""

from abc import ABC, abstractmethod
from functools import lru_cache

import httpx

from app.core.config import settings
from app.core.errors import AppError
from app.core.logging import get_logger

logger = get_logger(__name__)


class OtpProvider(ABC):
    @abstractmethod
    def send(self, phone: str, code: str) -> None: ...


class FakeOtpProvider(OtpProvider):
    """No SMS — records the last code per phone and logs it. Dev/test only."""

    def __init__(self) -> None:
        self.last_codes: dict[str, str] = {}

    def send(self, phone: str, code: str) -> None:
        self.last_codes[phone] = code
        logger.info("fake_otp_send phone=%s code=%s", phone, code)


class TwoFactorProvider(OtpProvider):
    """Delivers the backend-generated code via 2Factor.in's DLT-approved template.

    Uses the transactional template endpoint from the 2Factor onboarding email:
        GET https://2factor.in/API/V1/{api_key}/SMS/{phone}/{otp}/{template_name}
    A 2xx with JSON {"Status": "Success", ...} means queued for delivery.
    """

    BASE_URL = "https://2factor.in/API/V1"

    def send(self, phone: str, code: str) -> None:
        # E.164 (+91XXXXXXXXXX) → 2Factor accepts the number without the leading '+'.
        number = phone.lstrip("+")
        url = (
            f"{self.BASE_URL}/{settings.twofactor_api_key}"
            f"/SMS/{number}/{code}/{settings.twofactor_template_name}"
        )
        try:
            resp = httpx.get(url, timeout=10.0)
        except httpx.HTTPError as exc:
            logger.error("twofactor_http_error phone=%s err=%s", number, exc)
            raise AppError(
                "otp_send_failed",
                502,
                "Could not send verification code",
                {"provider": "2factor", "reason": f"network error: {exc}"},
            ) from exc

        # 2Factor signals failure via either a non-2xx status or Status != "Success",
        # and puts the human-readable reason in "Details" — surface it either way.
        details = self._details(resp)
        if resp.is_error or details.get("status") != "success":
            reason = details.get("message") or f"HTTP {resp.status_code}"
            logger.error(
                "twofactor_send_failed phone=%s http=%s details=%s",
                number,
                resp.status_code,
                reason,
            )
            raise AppError(
                "otp_send_failed",
                502,
                "Could not send verification code",
                {"provider": "2factor", "reason": reason},
            )

    @staticmethod
    def _details(resp: httpx.Response) -> dict[str, str]:
        try:
            data = resp.json()
        except ValueError:
            return {"status": "", "message": resp.text[:200]}
        return {
            "status": str(data.get("Status", "")).lower(),
            "message": str(data.get("Details", "")),
        }


@lru_cache
def get_otp_provider() -> OtpProvider:
    if settings.otp_provider == "twofactor":
        return TwoFactorProvider()
    return FakeOtpProvider()
