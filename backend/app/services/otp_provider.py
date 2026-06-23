"""OTP delivery provider abstraction (PRD D5).

The backend always generates and stores the code; providers are transport only.
`FakeOtpProvider` records codes in-memory for dev/test introspection.
"""

from abc import ABC, abstractmethod
from functools import lru_cache

import httpx

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)


class OtpProvider(ABC):
    @abstractmethod
    def send(self, phone: str, code: str) -> None: ...


class FakeOtpProvider(OtpProvider):
    def __init__(self) -> None:
        self.last_codes: dict[str, str] = {}

    def send(self, phone: str, code: str) -> None:
        self.last_codes[phone] = code
        logger.debug("fake_otp_send phone=%s code=%s", phone, code)


class MSG91Provider(OtpProvider):
    """Sends the backend-generated code via MSG91 as transport (TECH_SPEC §7.1)."""

    def send(self, phone: str, code: str) -> None:
        resp = httpx.post(
            "https://control.msg91.com/api/v5/flow/",
            headers={"authkey": settings.msg91_auth_key},
            json={
                "template_id": settings.msg91_template_id,
                "sender": settings.msg91_sender_id,
                "recipients": [{"mobiles": phone.lstrip("+"), "otp": code}],
            },
            timeout=10.0,
        )
        resp.raise_for_status()


@lru_cache
def get_otp_provider() -> OtpProvider:
    if settings.otp_provider == "msg91":
        return MSG91Provider()
    return FakeOtpProvider()
