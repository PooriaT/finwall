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


settings = Settings()
