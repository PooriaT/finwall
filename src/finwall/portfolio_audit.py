from dataclasses import dataclass
from enum import StrEnum


class PortfolioAuditSource(StrEnum):
    API = "api"
    WEB = "web"
    CLI = "cli"


class PortfolioAuditStatus(StrEnum):
    SUCCEEDED = "succeeded"
    FAILED = "failed"


class PortfolioAuditEntityType(StrEnum):
    CASH = "cash"
    HOLDING = "holding"
    TRADE = "trade"
    ACTIVE_ORDER = "active_order"
    WATCHLIST = "watchlist"
    GOAL = "goal"
    TIMELINE = "timeline"
    RISK_PROFILE = "risk_profile"


@dataclass(frozen=True)
class PortfolioAuditEvent:
    id: int
    portfolio_name: str
    changed_at: str
    actor: str
    source: str
    action: str
    entity_type: str
    entity_id: str | None
    status: str
    summary: str
    before_json: str | None
    after_json: str | None
    safe_error_message: str | None

    def as_dict(self) -> dict[str, object]:
        return {
            "id": self.id,
            "portfolio_name": self.portfolio_name,
            "changed_at": self.changed_at,
            "actor": self.actor,
            "source": self.source,
            "action": self.action,
            "entity_type": self.entity_type,
            "entity_id": self.entity_id,
            "status": self.status,
            "summary": self.summary,
            "before_json": self.before_json,
            "after_json": self.after_json,
            "safe_error_message": self.safe_error_message,
        }
