from __future__ import annotations

import smtplib
from dataclasses import dataclass
from email.message import EmailMessage as MimeEmailMessage
from typing import Protocol

from finwall.config import Settings
from finwall.scheduled_report import ScheduledReportResult

DISCLAIMER = "Finwall outputs are decision support only and not financial advice."


@dataclass(frozen=True)
class EmailConfig:
    provider: str
    from_address: str
    to_addresses: tuple[str, ...]
    smtp_host: str
    smtp_port: int
    smtp_username: str
    smtp_password: str
    smtp_use_starttls: bool
    timeout_seconds: float
    enabled: bool
    config_warnings: tuple[str, ...]


@dataclass(frozen=True)
class EmailMessage:
    subject: str
    text_body: str
    html_body: str | None
    from_address: str
    to_addresses: tuple[str, ...]


@dataclass(frozen=True)
class EmailSendResult:
    attempted: bool
    sent: bool
    provider: str
    warnings: tuple[str, ...] = ()
    error: str | None = None

    def as_dict(self) -> dict[str, object]:
        return {
            "attempted": self.attempted,
            "sent": self.sent,
            "provider": self.provider,
            "warnings": list(self.warnings),
            "error": self.error,
        }


class EmailProvider(Protocol):
    def send(self, message: EmailMessage) -> EmailSendResult: ...


class DisabledEmailProvider:
    def __init__(self, warning: str | None = None, provider: str = "disabled") -> None:
        warnings = (warning,) if warning else ()
        self.result = EmailSendResult(
            attempted=False,
            sent=False,
            provider=provider,
            warnings=warnings,
        )

    def send(self, message: EmailMessage) -> EmailSendResult:
        return self.result


class SmtpEmailProvider:
    def __init__(self, config: EmailConfig) -> None:
        self.config = config

    def send(self, message: EmailMessage) -> EmailSendResult:
        try:
            mime = MimeEmailMessage()
            mime["Subject"] = message.subject
            mime["From"] = message.from_address
            mime["To"] = ", ".join(message.to_addresses)
            mime.set_content(message.text_body)
            if message.html_body:
                mime.add_alternative(message.html_body, subtype="html")

            with smtplib.SMTP(
                self.config.smtp_host,
                self.config.smtp_port,
                timeout=self.config.timeout_seconds,
            ) as client:
                if self.config.smtp_use_starttls:
                    client.starttls()
                if self.config.smtp_username:
                    client.login(self.config.smtp_username, self.config.smtp_password)
                client.send_message(mime)
        except (smtplib.SMTPException, OSError, ValueError):
            return EmailSendResult(
                attempted=True,
                sent=False,
                provider="smtp",
                warnings=self.config.config_warnings,
                error="unable to send email notification via SMTP",
            )

        return EmailSendResult(
            attempted=True,
            sent=True,
            provider="smtp",
            warnings=self.config.config_warnings,
        )


def build_email_provider(
    settings: Settings, to_addresses_override: tuple[str, ...] | None = None
) -> EmailProvider:
    provider = settings.email_provider.strip().lower()
    if provider == "disabled":
        return DisabledEmailProvider("email notifications are disabled")

    if provider != "smtp":
        return DisabledEmailProvider(
            f"unsupported email provider '{settings.email_provider}'; using disabled provider",
            provider=provider,
        )

    to_addresses = to_addresses_override or settings.email_to_addresses
    config_warnings: list[str] = []
    missing_required: list[str] = []
    if not settings.email_from:
        missing_required.append("FINWALL_EMAIL_FROM")
    if not to_addresses:
        missing_required.append("FINWALL_EMAIL_TO")
    if not settings.smtp_host:
        missing_required.append("FINWALL_SMTP_HOST")

    if missing_required:
        return DisabledEmailProvider(
            "email disabled because required SMTP settings are missing: "
            + ", ".join(missing_required),
            provider="smtp",
        )

    if settings.smtp_port <= 0:
        config_warnings.append("invalid SMTP port configured; using disabled provider")
        return DisabledEmailProvider(config_warnings[0], provider="smtp")

    config = EmailConfig(
        provider="smtp",
        from_address=settings.email_from,
        to_addresses=to_addresses,
        smtp_host=settings.smtp_host,
        smtp_port=settings.smtp_port,
        smtp_username=settings.smtp_username,
        smtp_password=settings.smtp_password,
        smtp_use_starttls=settings.smtp_use_starttls,
        timeout_seconds=settings.email_timeout_seconds,
        enabled=True,
        config_warnings=tuple(config_warnings),
    )
    return SmtpEmailProvider(config)


def build_scheduled_success_email(
    result: ScheduledReportResult,
    portfolio_name: str,
    from_address: str,
    to_addresses: tuple[str, ...],
) -> EmailMessage:
    report_summary = "n/a"
    if isinstance(result.report, dict):
        report_summary = str(result.report.get("summary", "n/a"))
    comparison_summary = "none"
    if result.comparison and isinstance(result.comparison, dict):
        comparison_summary = str(result.comparison.get("summary", "none"))
    warning_lines = "none"
    if result.warnings:
        warning_lines = "\n".join(f"- {item}" for item in result.warnings)
    saved_run_line = (
        f"Saved report run ID: {result.saved_report_id}"
        if result.saved_report_id is not None
        else "Full report was generated locally and not saved."
    )
    body = (
        "Scheduled report completed successfully.\n\n"
        f"Status: {result.status.value}\n"
        f"Run context: {result.run_context}\n"
        f"Run date: {result.trading_day.get('calendar_date', 'n/a')}\n"
        f"Portfolio: {portfolio_name}\n"
        f"Message: {result.message}\n"
        f"{saved_run_line}\n"
        f"Comparison summary: {comparison_summary}\n"
        f"Warnings count: {len(result.warnings)}\n"
        f"Warnings:\n{warning_lines}\n"
        f"Report summary: {report_summary}\n\n"
        f"{DISCLAIMER}\n"
    )
    return EmailMessage(
        subject=f"Finwall scheduled report: {result.run_context} {result.status.value}",
        text_body=body,
        html_body=None,
        from_address=from_address,
        to_addresses=to_addresses,
    )


def build_scheduled_failure_email(
    result: ScheduledReportResult,
    portfolio_name: str,
    from_address: str,
    to_addresses: tuple[str, ...],
) -> EmailMessage:
    warning_lines = "none"
    if result.warnings:
        warning_lines = "\n".join(f"- {item}" for item in result.warnings)
    body = (
        "Scheduled report failed.\n\n"
        f"Status: {result.status.value}\n"
        f"Run context: {result.run_context}\n"
        f"Run date: {result.trading_day.get('calendar_date', 'n/a')}\n"
        f"Portfolio: {portfolio_name}\n"
        f"Message: {result.message}\n"
        f"Warnings:\n{warning_lines}\n\n"
        f"{DISCLAIMER}\n"
    )
    return EmailMessage(
        subject=f"Finwall scheduled report: {result.run_context} failed",
        text_body=body,
        html_body=None,
        from_address=from_address,
        to_addresses=to_addresses,
    )
