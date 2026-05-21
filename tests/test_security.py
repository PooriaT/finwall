from finwall.security import (
    REDACTED,
    assert_no_known_secrets_in_output,
    is_sensitive_key,
    redact_mapping,
    redact_text,
    safe_error_message,
)


def test_sensitive_key_detection() -> None:
    assert is_sensitive_key("api_token")
    assert is_sensitive_key("smtp_password")
    assert not is_sensitive_key("news_provider")


def test_mapping_redaction() -> None:
    redacted = redact_mapping({"api_token": "x", "name": "Primary"})
    assert redacted["api_token"] == REDACTED
    assert redacted["name"] == "Primary"


def test_text_redaction_and_safe_message() -> None:
    text = redact_text("token=abc123", ["abc123"])
    assert REDACTED in text
    assert "abc123" not in text
    assert (
        safe_error_message("invalid decimal for amount") == "invalid decimal for amount"
    )
    assert "unexpected error" in safe_error_message(Exception("password leaked"))


def test_assert_no_known_secrets_in_output() -> None:
    assert_no_known_secrets_in_output("hello", ["nope"])
