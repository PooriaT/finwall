import importlib

import finwall.config as config


def test_default_environment(monkeypatch) -> None:
    monkeypatch.delenv("FINWALL_MARKET_DATA_PROVIDER", raising=False)
    monkeypatch.delenv("FINWALL_MARKET_DATA_TIMEOUT_SECONDS", raising=False)

    reloaded = importlib.reload(config)

    assert reloaded.settings.app_env == "development"
    assert reloaded.settings.market_data_provider == "yfinance"
    assert reloaded.settings.market_data_timeout_seconds == 5.0


def test_market_data_settings_accept_yahoo_override(monkeypatch) -> None:
    monkeypatch.setenv("FINWALL_MARKET_DATA_PROVIDER", "yahoo")
    monkeypatch.setenv("FINWALL_MARKET_DATA_TIMEOUT_SECONDS", "12")

    reloaded = importlib.reload(config)

    assert reloaded.settings.market_data_provider == "yahoo"
    assert reloaded.settings.market_data_timeout_seconds == 12.0


def test_market_data_settings_accept_static_override(monkeypatch) -> None:
    monkeypatch.setenv("FINWALL_MARKET_DATA_PROVIDER", "static")

    reloaded = importlib.reload(config)

    assert reloaded.settings.market_data_provider == "static"


def test_market_data_blank_provider_uses_default(monkeypatch) -> None:
    monkeypatch.setenv("FINWALL_MARKET_DATA_PROVIDER", "")

    reloaded = importlib.reload(config)

    assert reloaded.settings.market_data_provider == "yfinance"


def test_market_data_whitespace_provider_uses_default(monkeypatch) -> None:
    monkeypatch.setenv("FINWALL_MARKET_DATA_PROVIDER", "  ")

    reloaded = importlib.reload(config)

    assert reloaded.settings.market_data_provider == "yfinance"


def test_news_blank_provider_uses_default(monkeypatch) -> None:
    monkeypatch.setenv("FINWALL_NEWS_PROVIDER", "")

    reloaded = importlib.reload(config)

    assert reloaded.settings.news_provider == "yfinance"


def test_market_data_timeout_invalid_env_uses_default(monkeypatch) -> None:
    monkeypatch.setenv("FINWALL_MARKET_DATA_TIMEOUT_SECONDS", "not-a-number")

    reloaded = importlib.reload(config)

    assert reloaded.settings.market_data_timeout_seconds == 5.0


def test_fundamental_data_settings_from_environment(monkeypatch) -> None:
    monkeypatch.setenv("FINWALL_FUNDAMENTAL_DATA_PROVIDER", "bogus")
    monkeypatch.setenv("FINWALL_FUNDAMENTAL_DATA_TIMEOUT_SECONDS", "9")

    reloaded = importlib.reload(config)

    assert reloaded.settings.fundamental_data_provider == "bogus"
    assert reloaded.settings.fundamental_data_timeout_seconds == 9.0


def test_narrative_settings_defaults_and_validation(monkeypatch) -> None:
    monkeypatch.setenv("FINWALL_NARRATIVE_PROVIDER", "disabled")
    monkeypatch.setenv("FINWALL_NARRATIVE_MAX_WORDS", "-1")
    monkeypatch.setenv("FINWALL_NARRATIVE_STYLE", "plain_english")

    reloaded = importlib.reload(config)

    assert reloaded.settings.narrative_provider == "disabled"
    assert reloaded.settings.narrative_max_words == 500
    assert reloaded.settings.narrative_style == "plain_english"


def test_ollama_settings_defaults_and_timeout_validation(monkeypatch) -> None:
    monkeypatch.delenv("FINWALL_OLLAMA_BASE_URL", raising=False)
    monkeypatch.delenv("FINWALL_OLLAMA_MODEL", raising=False)
    monkeypatch.setenv("FINWALL_OLLAMA_TIMEOUT_SECONDS", "-5")
    reloaded = importlib.reload(config)
    assert reloaded.settings.ollama_base_url == "http://localhost:11434"
    assert reloaded.settings.ollama_model == "gemma3:latest"
    assert reloaded.settings.ollama_timeout_seconds == 30.0


def test_email_to_csv_parsing(monkeypatch) -> None:
    monkeypatch.setenv(
        "FINWALL_EMAIL_TO", "a@example.com, b@example.com ,,c@example.com"
    )
    reloaded = importlib.reload(config)
    assert reloaded.settings.email_to_addresses == (
        "a@example.com",
        "b@example.com",
        "c@example.com",
    )


def test_storage_settings_defaults(monkeypatch) -> None:
    monkeypatch.delenv("FINWALL_STORAGE_BACKEND", raising=False)
    monkeypatch.delenv("FINWALL_DATABASE_URL", raising=False)
    reloaded = importlib.reload(config)
    assert reloaded.settings.storage_backend == "sqlite"
    assert reloaded.settings.database_url == ""
