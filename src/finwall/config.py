import os
from dataclasses import dataclass


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


settings = Settings()
