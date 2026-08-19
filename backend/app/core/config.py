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

    # OTP / SMS auth. `fake` logs the code (dev/test); `twofactor` sends real SMS.
    otp_provider: Literal["fake", "twofactor"] = "fake"
    otp_ttl_seconds: int = 300
    otp_max_attempts: int = 5
    otp_resend_cooldown_seconds: int = 30
    otp_daily_cap_per_phone: int = 5
    otp_daily_cap_per_ip: int = 20

    # 2Factor.in (India, DLT-registered transactional SMS). The backend generates
    # the code; 2Factor delivers it via the approved template (default "OTP1").
    twofactor_api_key: str = ""
    twofactor_template_name: str = "OTP1"

    # --- Dealer Rewards -----------------------------------------------------
    # Warranty policy. The clock is server-authoritative; a dealer-supplied
    # invoice date may only pull the start BACKWARD, and only this far, before
    # it needs an admin's approval instead.
    backdate_grace_days: int = 7
    default_warranty_months: int = 60
    dealer_edit_window_hours: int = 24
    require_customer_confirmation: bool = False
    # Warranty dates are calendar dates where the sale happens, not UTC instants:
    # a 9pm sale in India must not book as tomorrow.
    business_timezone: str = "Asia/Kolkata"

    registrations_per_hour_per_staff: int = 60
    registrations_per_day_per_dealer: int = 400
    public_lookup_per_min_per_ip: int = 20
    uploads_dir: str = "var/uploads"

    # Transactional SMS for warranty confirmations. Separate from the OTP
    # provider above: the OTP template carries one value in a URL path and
    # cannot express a warranty message, and each needs its own DLT approval.
    sms_provider: Literal["fake", "msg91"] = "fake"
    sms_sender_id: str = ""
    msg91_auth_key: str = ""
    msg91_warranty_template_id: str = ""
    msg91_otp_template_id: str = ""
    sms_timeout_seconds: float = 10.0
    public_base_url: str = "http://localhost:5174"

    env: Literal["dev", "staging", "prod"] = "dev"
    log_level: str = "INFO"

    # Production hardening / ops
    cors_origins: str = ""  # comma-separated allowed origins (non-dev)
    sentry_dsn: str = ""
    sentry_traces_sample_rate: float = 0.1
    scan_rate_per_min: int = 30

    # Bootstrap the first admin account on startup if it doesn't exist yet.
    # Set both to create it without needing shell/CLI access (e.g. on Render's free plan).
    bootstrap_admin_email: str = ""
    bootstrap_admin_password: str = ""

    # The dealer back office has its own accounts table, so it needs its own
    # first-run bootstrap. Same reason as the worker one above: Render's plan
    # has no shell, so without this the panel deploys with nobody able to log in.
    dealer_bootstrap_admin_email: str = ""
    dealer_bootstrap_admin_password: str = ""

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    # Populated by assert_production_ready and logged at startup. Things that
    # degrade a feature but must not stop the service from serving.
    startup_warnings: list[str] = []

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
        if self.otp_provider == "twofactor" and not self.twofactor_api_key:
            problems.append("TWOFACTOR_API_KEY must be set when OTP_PROVIDER=twofactor")
        # Dealer SMS gaps are WARNINGS, not boot failures.
        #
        # One process now serves both programmes. Refusing to start because the
        # dealer programme's DLT template is not approved yet would take the
        # worker app — which has live users scanning right now — offline for a
        # feature it does not use. The dealer side degrades instead: warranty
        # messages are still recorded and visible on the admin SMS screen, they
        # are simply not delivered until a real provider is configured.
        #
        # The worker programme's own OTP provider check above stays fail-fast,
        # because that IS its feature and a silent failure there is worse.
        if self.env == "prod":
            if self.sms_provider == "fake":
                self.startup_warnings.append(
                    "SMS_PROVIDER=fake in production — warranty confirmations are "
                    "recorded but NOT delivered to customers"
                )
            elif self.sms_provider == "msg91" and not self.msg91_warranty_template_id:
                self.startup_warnings.append(
                    "MSG91_WARRANTY_TEMPLATE_ID is unset — the warranty SMS needs its "
                    "own DLT-approved template, distinct from the OTP one"
                )
        if problems:
            raise RuntimeError("Invalid production config: " + "; ".join(problems))


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
