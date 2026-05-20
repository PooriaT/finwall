from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class StoredReportRun:
    id: int | None
    portfolio_name: str
    created_at: str
    command_context: str
    report_summary: str
    report_json: str
    price_completeness_status: str | None
    valuation_status: str | None
    recommendation_summary: str | None


@dataclass(frozen=True)
class StoredRecommendationStatus:
    ticker: str
    status: str
    confidence: str
    risk_level: str
    blocked_by_risk: bool
    suggested_action: str


@dataclass(frozen=True)
class StoredRiskWarning:
    code: str
    severity: str
    ticker: str | None
    message: str


@dataclass(frozen=True)
class StoredSuggestedOrder:
    ticker: str
    side: str
    order_type: str
    share_count: str
    limit_price: str | None
    stop_price: str | None
    description: str


@dataclass(frozen=True)
class RecommendationChange:
    ticker: str
    previous_status: str | None
    current_status: str | None
    previous_confidence: str | None
    current_confidence: str | None
    previous_risk_level: str | None
    current_risk_level: str | None
    previous_blocked_by_risk: bool | None
    current_blocked_by_risk: bool | None
    change_type: str
    summary: str


@dataclass(frozen=True)
class ReportRunComparison:
    previous_run_id: int | None
    current_run_id: int | None
    changes: tuple[RecommendationChange, ...]
    summary: str


def compare_recommendation_statuses(
    previous: tuple[StoredRecommendationStatus, ...],
    current: tuple[StoredRecommendationStatus, ...],
    previous_run_id: int | None,
    current_run_id: int | None,
) -> ReportRunComparison:
    if previous_run_id is None:
        return ReportRunComparison(
            previous_run_id=previous_run_id,
            current_run_id=current_run_id,
            changes=(),
            summary="First saved report run; no previous run available for comparison.",
        )

    previous_by_ticker = {item.ticker: item for item in previous}
    current_by_ticker = {item.ticker: item for item in current}
    changes: list[RecommendationChange] = []

    for ticker in sorted(set(previous_by_ticker) | set(current_by_ticker)):
        old = previous_by_ticker.get(ticker)
        new = current_by_ticker.get(ticker)
        if old is None and new is not None:
            changes.append(
                RecommendationChange(
                    ticker=ticker,
                    previous_status=None,
                    current_status=new.status,
                    previous_confidence=None,
                    current_confidence=new.confidence,
                    previous_risk_level=None,
                    current_risk_level=new.risk_level,
                    previous_blocked_by_risk=None,
                    current_blocked_by_risk=new.blocked_by_risk,
                    change_type="new_ticker",
                    summary=(
                        "New ticker added to recommendation output; "
                        "decision-support comparison only."
                    ),
                )
            )
            continue

        if old is not None and new is None:
            changes.append(
                RecommendationChange(
                    ticker=ticker,
                    previous_status=old.status,
                    current_status=None,
                    previous_confidence=old.confidence,
                    current_confidence=None,
                    previous_risk_level=old.risk_level,
                    current_risk_level=None,
                    previous_blocked_by_risk=old.blocked_by_risk,
                    current_blocked_by_risk=None,
                    change_type="removed_ticker",
                    summary=(
                        "Ticker removed from recommendation output; "
                        "review this change as decision-support only."
                    ),
                )
            )
            continue

        assert old is not None and new is not None
        reasons: list[str] = []
        if old.status != new.status:
            reasons.append("status_changed")
        if old.confidence != new.confidence:
            reasons.append("confidence_changed")
        if old.risk_level != new.risk_level:
            reasons.append("risk_level_changed")
        if old.blocked_by_risk != new.blocked_by_risk:
            reasons.append("blocked_by_risk_changed")

        if reasons:
            changes.append(
                RecommendationChange(
                    ticker=ticker,
                    previous_status=old.status,
                    current_status=new.status,
                    previous_confidence=old.confidence,
                    current_confidence=new.confidence,
                    previous_risk_level=old.risk_level,
                    current_risk_level=new.risk_level,
                    previous_blocked_by_risk=old.blocked_by_risk,
                    current_blocked_by_risk=new.blocked_by_risk,
                    change_type=",".join(reasons),
                    summary=(
                        "Recommendation status changed and/or risk state changed; "
                        "review this change as decision-support comparison only."
                    ),
                )
            )

    if not changes:
        summary = "No recommendation changes were detected."
    else:
        summary = f"{len(changes)} recommendation change(s) detected."

    return ReportRunComparison(
        previous_run_id=previous_run_id,
        current_run_id=current_run_id,
        changes=tuple(changes),
        summary=summary,
    )
