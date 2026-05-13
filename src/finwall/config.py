from dataclasses import dataclass
import os


@dataclass(frozen=True)
class Settings:
    app_env: str = os.getenv("FINWALL_ENV", "development")


settings = Settings()
