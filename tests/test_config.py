import importlib

import finwall.config as config


def test_default_environment() -> None:
    assert config.settings.app_env == "development"
    assert config.settings.market_data_provider == "static"
    assert config.settings.market_data_timeout_seconds == 5.0


def test_market_data_settings_from_environment(monkeypatch) -> None:
    monkeypatch.setenv("FINWALL_MARKET_DATA_PROVIDER", "yahoo")
    monkeypatch.setenv("FINWALL_MARKET_DATA_TIMEOUT_SECONDS", "12")

    reloaded = importlib.reload(config)

    assert reloaded.settings.market_data_provider == "yahoo"
    assert reloaded.settings.market_data_timeout_seconds == 12.0
