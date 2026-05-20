from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class ScheduledReportStatus(StrEnum):
    GENERATED = "generated"
    SKIPPED = "skipped"
    FAILED = "failed"


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
        }
