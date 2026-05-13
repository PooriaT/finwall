from finwall.config import settings


def test_default_environment() -> None:
    assert settings.app_env == "development"
