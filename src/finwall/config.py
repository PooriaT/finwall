import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    app_env: str = os.getenv("FINWALL_ENV", "development")


settings = Settings()
