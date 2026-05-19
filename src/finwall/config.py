import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    app_env: str = os.getenv("FINWALL_ENV", "development")
    market_data_provider: str = os.getenv("FINWALL_MARKET_DATA_PROVIDER", "static")
    market_data_timeout_seconds: float = float(
        os.getenv("FINWALL_MARKET_DATA_TIMEOUT_SECONDS", "5")
    )


settings = Settings()
