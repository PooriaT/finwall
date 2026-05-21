import os
from dataclasses import dataclass


def _parse_bool(raw_value: str | None, default: bool) -> bool:
    if raw_value is None:
        return default
    value = raw_value.strip().lower()
    if not value:
        return default
    if value in {"1", "true", "yes", "on"}:
        return True
    if value in {"0", "false", "no", "off"}:
        return False
    return default


def _parse_timeout_seconds(raw_value: str | None, default: float) -> float:
    if raw_value is None:
        return default
    value = raw_value.strip()
    if not value:
        return default
    try:
        timeout_seconds = float(value)
    except ValueError:
        return default
    if timeout_seconds <= 0:
        return default
    return timeout_seconds


def _parse_csv(raw_value: str | None) -> tuple[str, ...]:
    if raw_value is None:
        return ()
    return tuple(item.strip() for item in raw_value.split(",") if item.strip())


def _parse_positive_int(raw_value: str | None, default: int) -> int:
    if raw_value is None:
        return default
    value = raw_value.strip()
    if not value:
        return default
    try:
        parsed = int(value)
    except ValueError:
        return default
    if parsed <= 0:
        return default
    return parsed


@dataclass(frozen=True)
class Settings:
    app_env: str = os.getenv("FINWALL_ENV", "development")
    market_data_provider: str = os.getenv("FINWALL_MARKET_DATA_PROVIDER", "static")
    market_data_timeout_seconds: float = _parse_timeout_seconds(
        os.getenv("FINWALL_MARKET_DATA_TIMEOUT_SECONDS"), 5.0
    )
    fundamental_data_provider: str = os.getenv(
        "FINWALL_FUNDAMENTAL_DATA_PROVIDER", "static"
    )
    fundamental_data_timeout_seconds: float = _parse_timeout_seconds(
        os.getenv("FINWALL_FUNDAMENTAL_DATA_TIMEOUT_SECONDS"), 5.0
    )
    news_provider: str = os.getenv("FINWALL_NEWS_PROVIDER", "static")
    news_timeout_seconds: float = _parse_timeout_seconds(
        os.getenv("FINWALL_NEWS_TIMEOUT_SECONDS"), 5.0
    )
    news_max_articles_per_topic: int = _parse_positive_int(
        os.getenv("FINWALL_NEWS_MAX_ARTICLES_PER_TOPIC"), 5
    )
    news_max_age_hours: int = _parse_positive_int(
        os.getenv("FINWALL_NEWS_MAX_AGE_HOURS"), 72
    )
    narrative_provider: str = os.getenv("FINWALL_NARRATIVE_PROVIDER", "disabled")
    narrative_max_words: int = _parse_positive_int(
        os.getenv("FINWALL_NARRATIVE_MAX_WORDS"), 500
    )
    narrative_style: str = os.getenv("FINWALL_NARRATIVE_STYLE", "plain_english")
    ollama_base_url: str = os.getenv(
        "FINWALL_OLLAMA_BASE_URL", "http://localhost:11434"
    ).strip()
    ollama_model: str = os.getenv("FINWALL_OLLAMA_MODEL", "gemma3:latest").strip()
    ollama_timeout_seconds: float = _parse_timeout_seconds(
        os.getenv("FINWALL_OLLAMA_TIMEOUT_SECONDS"), 30.0
    )
    email_provider: str = os.getenv("FINWALL_EMAIL_PROVIDER", "disabled")
    email_from: str = os.getenv("FINWALL_EMAIL_FROM", "").strip()
    email_to_addresses: tuple[str, ...] = _parse_csv(os.getenv("FINWALL_EMAIL_TO"))
    email_timeout_seconds: float = _parse_timeout_seconds(
        os.getenv("FINWALL_EMAIL_TIMEOUT_SECONDS"), 10.0
    )
    smtp_host: str = os.getenv("FINWALL_SMTP_HOST", "").strip()
    smtp_port: int = _parse_positive_int(os.getenv("FINWALL_SMTP_PORT"), 587)
    smtp_username: str = os.getenv("FINWALL_SMTP_USERNAME", "").strip()
    smtp_password: str = os.getenv("FINWALL_SMTP_PASSWORD", "")
    smtp_use_starttls: bool = _parse_bool(os.getenv("FINWALL_SMTP_USE_STARTTLS"), True)
    storage_backend: str = (
        os.getenv("FINWALL_STORAGE_BACKEND", "sqlite").strip().lower()
    )
    database_url: str = os.getenv("FINWALL_DATABASE_URL", "").strip()
    database_path: str = os.getenv("FINWALL_DATABASE_PATH", "finwall.db").strip()
    api_enabled: bool = _parse_bool(os.getenv("FINWALL_API_ENABLED"), False)
    api_token: str = os.getenv("FINWALL_API_TOKEN", "").strip()
    api_host: str = os.getenv("FINWALL_API_HOST", "127.0.0.1").strip()
    api_port: int = _parse_positive_int(os.getenv("FINWALL_API_PORT"), 8000)


settings = Settings()
