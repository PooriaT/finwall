from finwall.config import Settings
from finwall.config_validation import validate_runtime_security_settings


def test_runtime_validation_warnings_safe() -> None:
    settings = Settings(
        api_enabled=True,
        api_token="",
        email_provider="smtp",
        email_from="",
        email_to_addresses=(),
        smtp_host="",
        storage_backend="postgres",
        database_url="",
    )
    warnings = validate_runtime_security_settings(settings)
    assert any("FINWALL_API_TOKEN" in item for item in warnings)
    assert any("FINWALL_SMTP_HOST" in item for item in warnings)
    assert any("FINWALL_DATABASE_URL" in item for item in warnings)


def test_weak_token_warning_without_leak() -> None:
    settings = Settings(api_enabled=True, api_token="change-me")
    warnings = validate_runtime_security_settings(settings)
    assert any("weak placeholder" in item for item in warnings)
    assert all("change-me" not in item for item in warnings)
