from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    database_url: str = "postgresql+psycopg://scanrewards:scanrewards@localhost:5432/scanrewards"
    redis_url: str = "redis://localhost:6379/0"

    jwt_secret: str = "change-me-dev-secret"
    jwt_access_ttl_minutes: int = 60
    jwt_refresh_ttl_days: int = 30

    otp_provider: Literal["fake", "msg91"] = "fake"
    otp_ttl_seconds: int = 300
    otp_max_attempts: int = 5
    otp_resend_cooldown_seconds: int = 30
    otp_daily_cap_per_phone: int = 5
    otp_daily_cap_per_ip: int = 20

    msg91_auth_key: str = ""
    msg91_sender_id: str = ""
    msg91_template_id: str = ""

    env: Literal["dev", "staging", "prod"] = "dev"
    log_level: str = "INFO"

    # Production hardening / ops
    cors_origins: str = ""  # comma-separated allowed origins (non-dev)
    sentry_dsn: str = ""
    sentry_traces_sample_rate: float = 0.1
    scan_rate_per_min: int = 30

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    def assert_production_ready(self) -> None:
        """Fail fast on unsafe defaults outside dev."""
        if self.env == "dev":
            return
        problems: list[str] = []
        if self.jwt_secret == "change-me-dev-secret" or len(self.jwt_secret) < 32:
            problems.append("JWT_SECRET must be a strong, non-default value (>= 32 chars)")
        if not self.cors_origin_list:
            problems.append("CORS_ORIGINS must be set")
        # Real SMS is required in prod; staging may keep the fake provider for smoke testing.
        if self.env == "prod" and self.otp_provider == "fake":
            problems.append("OTP_PROVIDER must not be 'fake' in production")
        if problems:
            raise RuntimeError("Invalid production config: " + "; ".join(problems))


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
