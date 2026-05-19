import os
from dataclasses import dataclass


def _parse_market_data_timeout_seconds(raw_value: str | None) -> float:
    if raw_value is None:
        return 5.0

    value = raw_value.strip()
    if not value:
        return 5.0

    try:
        timeout_seconds = float(value)
    except ValueError:
        return 5.0

    if timeout_seconds <= 0:
        return 5.0

    return timeout_seconds


@dataclass(frozen=True)
class Settings:
    app_env: str = os.getenv("FINWALL_ENV", "development")
    market_data_provider: str = os.getenv("FINWALL_MARKET_DATA_PROVIDER", "static")
    market_data_timeout_seconds: float = _parse_market_data_timeout_seconds(
        os.getenv("FINWALL_MARKET_DATA_TIMEOUT_SECONDS")
    )


settings = Settings()
