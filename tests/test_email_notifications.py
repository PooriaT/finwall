from types import SimpleNamespace

from finwall.email_notifications import (
    DisabledEmailProvider,
    EmailMessage,
    build_email_provider,
    build_scheduled_failure_email,
    build_scheduled_success_email,
)
from finwall.scheduled_report import ScheduledReportResult, ScheduledReportStatus


def _settings(**kwargs):
    base = dict(
        email_provider="disabled",
        email_from="sender@example.com",
        email_to_addresses=("to@example.com",),
        email_timeout_seconds=10.0,
        smtp_host="smtp.example.com",
        smtp_port=587,
        smtp_username="",
        smtp_password="",
        smtp_use_starttls=True,
    )
    base.update(kwargs)
    return SimpleNamespace(**base)


def test_disabled_provider_returns_noop_result() -> None:
    provider = DisabledEmailProvider("disabled")
    result = provider.send(
        EmailMessage("x", "y", None, "a@example.com", ("b@example.com",))
    )
    assert result.attempted is False
    assert result.sent is False


def test_missing_smtp_config_disables_provider() -> None:
    provider = build_email_provider(_settings(email_provider="smtp", smtp_host=""))
    result = provider.send(
        EmailMessage("x", "y", None, "a@example.com", ("b@example.com",))
    )
    assert result.attempted is False
    assert "missing" in result.warnings[0]


def test_unsupported_provider_disables() -> None:
    provider = build_email_provider(_settings(email_provider="api_foo"))
    result = provider.send(
        EmailMessage("x", "y", None, "a@example.com", ("b@example.com",))
    )
    assert result.attempted is False
    assert "unsupported" in result.warnings[0]


def test_success_template_includes_saved_id_and_disclaimer() -> None:
    result = ScheduledReportResult(
        status=ScheduledReportStatus.GENERATED,
        run_context="morning",
        trading_day={"calendar_date": "2026-05-20"},
        report={"summary": "All good"},
        saved_report_id=5,
        comparison={"summary": "No changes"},
        message="Generated scheduled report for 2026-05-20.",
        warnings=("one",),
    )
    message = build_scheduled_success_email(
        result, "Primary", "from@example.com", ("to@example.com",)
    )
    assert "Status: generated" in message.text_body
    assert "Run context: morning" in message.text_body
    assert "Saved report run ID: 5" in message.text_body
    assert "decision support only" in message.text_body.lower()


def test_failure_template_omits_traceback() -> None:
    result = ScheduledReportResult(
        status=ScheduledReportStatus.FAILED,
        run_context="after_close",
        trading_day={"calendar_date": "2026-05-20"},
        report=None,
        saved_report_id=None,
        comparison=None,
        message="Scheduled report failed unexpectedly.",
        warnings=("safe warning",),
    )
    message = build_scheduled_failure_email(
        result, "Primary", "from@example.com", ("to@example.com",)
    )
    assert "Scheduled report failed." in message.text_body
    assert "Traceback" not in message.text_body
