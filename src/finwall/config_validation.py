from __future__ import annotations

from finwall.config import Settings
from finwall.security import safe_config_warnings

_WEAK_TOKENS = {"change-me", "changeme", "password", "secret", "token", "admin"}


def validate_runtime_security_settings(settings: Settings) -> tuple[str, ...]:
    warnings: list[str] = []
    env = settings.app_env.strip().lower()
    api_token = settings.api_token.strip()

    if settings.api_enabled and not api_token:
        warnings.append("FINWALL_API_ENABLED=true requires FINWALL_API_TOKEN to be set")
    if settings.api_enabled and api_token.lower() in _WEAK_TOKENS:
        warnings.append("FINWALL_API_TOKEN uses a weak placeholder value")

    if settings.email_provider.strip().lower() == "smtp":
        if not settings.email_from:
            warnings.append("FINWALL_EMAIL_PROVIDER=smtp requires FINWALL_EMAIL_FROM")
        if not settings.email_to_addresses:
            warnings.append("FINWALL_EMAIL_PROVIDER=smtp requires FINWALL_EMAIL_TO")
        if not settings.smtp_host:
            warnings.append("FINWALL_EMAIL_PROVIDER=smtp requires FINWALL_SMTP_HOST")

    if settings.storage_backend == "postgres" and not settings.database_url:
        warnings.append(
            "FINWALL_STORAGE_BACKEND=postgres requires FINWALL_DATABASE_URL"
        )

    if env == "production" and settings.api_enabled and not api_token:
        warnings.append(
            "FINWALL_ENV=production requires FINWALL_API_TOKEN when API is enabled"
        )
    if (
        env == "production"
        and settings.api_enabled
        and settings.api_host == "0.0.0.0"
        and not api_token
    ):
        warnings.append(
            "FINWALL_API_HOST=0.0.0.0 in production requires FINWALL_API_TOKEN"
        )
    return safe_config_warnings(warnings)
