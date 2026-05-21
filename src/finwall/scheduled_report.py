from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class ScheduledReportStatus(StrEnum):
    GENERATED = "generated"
    SKIPPED = "skipped"
    FAILED = "failed"
    DUPLICATE = "duplicate"


class ScheduledRunStatus(StrEnum):
    STARTED = "started"
    GENERATED = "generated"
    SKIPPED = "skipped"
    FAILED = "failed"
    DUPLICATE = "duplicate"


class ScheduledRunErrorCategory(StrEnum):
    NONE = "none"
    NON_TRADING_DAY = "non_trading_day"
    DUPLICATE_RUN = "duplicate_run"
    REPORT_GENERATION_FAILED = "report_generation_failed"
    EMAIL_SEND_FAILED = "email_send_failed"
    STORAGE_FAILED = "storage_failed"
    UNKNOWN = "unknown"


class ScheduledRunContext(StrEnum):
    MORNING = "morning"
    AFTER_CLOSE = "after_close"
    MANUAL = "manual"


@dataclass(frozen=True)
class ScheduledReportResult:
    status: ScheduledReportStatus
    run_context: str
    trading_day: dict[str, object]
    report: dict[str, object] | None
    saved_report_id: int | None
    comparison: dict[str, object] | None
    message: str
    warnings: tuple[str, ...]
    notification: dict[str, object] | None = None
    scheduled_run: dict[str, object] | None = None

    def as_dict(self) -> dict[str, object]:
        return {
            "status": self.status.value,
            "run_context": self.run_context,
            "trading_day": self.trading_day,
            "report": self.report,
            "saved_report_id": self.saved_report_id,
            "comparison": self.comparison,
            "message": self.message,
            "warnings": list(self.warnings),
            "notification": self.notification,
            "scheduled_run": self.scheduled_run,
        }


@dataclass(frozen=True)
class StoredScheduledRun:
    id: int
    portfolio_name: str
    run_date: str
    run_context: str
    status: str
    started_at: str
    finished_at: str | None
    report_run_id: int | None
    notification_attempted: bool
    notification_sent: bool
    notification_provider: str | None
    error_category: str
    safe_error_message: str | None

    def as_dict(self) -> dict[str, object]:
        return {
            "id": self.id,
            "portfolio_name": self.portfolio_name,
            "run_date": self.run_date,
            "run_context": self.run_context,
            "status": self.status,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "report_run_id": self.report_run_id,
            "notification_attempted": self.notification_attempted,
            "notification_sent": self.notification_sent,
            "notification_provider": self.notification_provider,
            "error_category": self.error_category,
            "safe_error_message": self.safe_error_message,
        }
