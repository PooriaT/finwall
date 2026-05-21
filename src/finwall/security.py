from __future__ import annotations

from collections.abc import Iterable, Mapping

SENSITIVE_KEYWORDS = (
    "token",
    "secret",
    "password",
    "credential",
    "authorization",
    "api_key",
    "apikey",
    "database_url",
    "smtp_password",
)

REDACTED = "[REDACTED]"
_GENERIC_ERROR = "unexpected error; check logs for safe diagnostics"


def is_sensitive_key(key: str) -> bool:
    lowered = key.strip().lower()
    return any(keyword in lowered for keyword in SENSITIVE_KEYWORDS)


def redact_value(value: object) -> str:
    if value is None:
        return ""
    return REDACTED


def redact_mapping(data: Mapping[str, object]) -> dict[str, object]:
    redacted: dict[str, object] = {}
    for key in sorted(data):
        value = data[key]
        redacted[key] = redact_value(value) if is_sensitive_key(key) else value
    return redacted


def redact_text(text: str, known_secrets: Iterable[str] = ()) -> str:
    result = text
    for secret in sorted({item for item in known_secrets if item}):
        result = result.replace(secret, REDACTED)
    return result


def safe_error_message(message: str | BaseException) -> str:
    if isinstance(message, BaseException):
        text = str(message).strip()
    else:
        text = str(message).strip()
    if not text:
        return _GENERIC_ERROR
    lowered = text.lower()
    if any(keyword in lowered for keyword in SENSITIVE_KEYWORDS):
        return _GENERIC_ERROR
    if any(token in text for token in ("Traceback", "\n", 'File "')):
        return _GENERIC_ERROR
    return text


def safe_config_warnings(warnings: Iterable[str]) -> tuple[str, ...]:
    cleaned: list[str] = []
    for warning in warnings:
        msg = str(warning).strip()
        if msg and msg not in cleaned:
            cleaned.append(msg)
    return tuple(cleaned)


def assert_no_known_secrets_in_output(
    output: str, known_secrets: Iterable[str]
) -> None:
    for secret in known_secrets:
        if secret and secret in output:
            raise AssertionError("secret leaked in output")
