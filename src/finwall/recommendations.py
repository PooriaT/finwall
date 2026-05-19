from dataclasses import asdict, dataclass
from enum import StrEnum

from finwall.models import Portfolio, RiskLevel
from finwall.risk import RiskAssessment
from finwall.snapshot import HoldingSnapshot, PortfolioSnapshot


class RecommendationStatus(StrEnum):
    BUY = "buy"
    HOLD = "hold"
    REDUCE = "reduce"
    SELL = "sell"
    WATCH = "watch"


class RecommendationConfidence(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class RecommendationRiskLevel(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class CashDeploymentRecommendationStatus(StrEnum):
    KEEP_CASH = "keep_cash"
    DEPLOY_CAUTIOUSLY = "deploy_cautiously"
    AVOID_NEW_BUYS = "avoid_new_buys"
    INSUFFICIENT_DATA = "insufficient_data"


@dataclass(frozen=True)
class HoldingRecommendation:
    ticker: str
    status: RecommendationStatus
    confidence: RecommendationConfidence
    risk_level: RecommendationRiskLevel
    reasoning_inputs: tuple[str, ...]
    warnings: tuple[str, ...]
    invalidation_conditions: tuple[str, ...]
    blocked_by_risk: bool
    data_quality: str
    suggested_action: str


@dataclass(frozen=True)
class CashDeploymentStatus:
    status: CashDeploymentRecommendationStatus
    confidence: RecommendationConfidence
    reasoning_inputs: tuple[str, ...]
    warnings: tuple[str, ...]
    suggested_action: str


@dataclass(frozen=True)
class RecommendationReport:
    holdings: tuple[HoldingRecommendation, ...]
    cash_deployment: CashDeploymentStatus
    summary: str
    limitations: tuple[str, ...]

    def as_dict(self) -> dict[str, object]:
        payload = asdict(self)
        payload["holdings"] = [_holding_to_dict(item) for item in self.holdings]
        payload["cash_deployment"] = _cash_to_dict(self.cash_deployment)
        return payload


def build_recommendation_report(
    portfolio: Portfolio,
    snapshot: PortfolioSnapshot,
    risk_assessment: RiskAssessment,
) -> RecommendationReport:
    warnings_by_ticker = _warnings_by_ticker(risk_assessment)
    limitations = _build_limitations(portfolio, snapshot, risk_assessment)

    holdings = tuple(
        _recommend_holding(holding, warnings_by_ticker.get(holding.ticker.upper(), []))
        for holding in snapshot.holdings
    )

    cash_deployment = _recommend_cash_deployment(snapshot, risk_assessment)
    summary = (
        "Deterministic recommendation report generated from snapshot and risk rules; "
        "this is decision-support output and not financial advice."
    )

    return RecommendationReport(
        holdings=holdings,
        cash_deployment=cash_deployment,
        summary=summary,
        limitations=tuple(limitations),
    )


def _recommend_holding(
    holding: HoldingSnapshot,
    ticker_warnings: list[tuple[str, str]],
) -> HoldingRecommendation:
    reasoning = [
        (
            "Deterministic status derived from valuation, allocation, "
            "unrealized P/L, and risk warnings."
        ),
        "Technical analysis is not implemented; confidence is capped.",
        "Fundamental analysis is not implemented; confidence is capped.",
    ]
    warnings: list[str] = []
    invalidation: list[str] = []
    blocked_by_risk = False
    status = RecommendationStatus.HOLD
    confidence = RecommendationConfidence.MEDIUM
    risk_level = RecommendationRiskLevel.LOW
    data_quality = "complete"
    suggested_action = (
        "Suggested review action: maintain position size and continue "
        "monitoring risk warnings."
    )

    if not holding.price_available:
        status = RecommendationStatus.WATCH
        confidence = RecommendationConfidence.LOW
        risk_level = RecommendationRiskLevel.MEDIUM
        data_quality = "missing_price"
        warning_text = (
            "Risk warning: price data is missing, so recommendation "
            "confidence is limited."
        )
        warnings.append(warning_text)
        reasoning.append("Price data unavailable for holding valuation.")
        suggested_action = (
            "Suggested review action: provide a current price before "
            "considering position changes."
        )

    codes = {item[0] for item in ticker_warnings}
    for code, severity in ticker_warnings:
        reasoning.append(f"Risk warning applied: {code} ({severity}).")

    if "POSITION_CONCENTRATION_LIMIT" in codes:
        status = RecommendationStatus.REDUCE
        risk_level = RecommendationRiskLevel.HIGH
        blocked_by_risk = True
        confidence = RecommendationConfidence.MEDIUM
        warnings.append(
            "Risk warning: position concentration exceeds configured limits."
        )
        suggested_action = (
            "Suggested review action: review position size and risk "
            "concentration; avoid automatic liquidation."
        )

    if "HOLDING_UNREALIZED_LOSS_LIMIT" in codes:
        if status == RecommendationStatus.HOLD:
            status = RecommendationStatus.WATCH
        confidence = RecommendationConfidence.LOW
        risk_level = RecommendationRiskLevel.HIGH
        blocked_by_risk = True
        warnings.append("Risk warning: unrealized loss exceeds configured threshold.")
        invalidation.append(
            "Invalidate hold thesis if downside persists and loss widens "
            "beyond current risk limits."
        )

    if "STOP_PROTECTION_INVALID_ORDER" in codes:
        status = RecommendationStatus.REDUCE
        confidence = RecommendationConfidence.LOW
        risk_level = RecommendationRiskLevel.HIGH
        blocked_by_risk = True
        warnings.append(
            "Risk warning: active stop protection order is present but invalid."
        )
        invalidation.append(
            "If stop protection remains invalid, avoid adding exposure and "
            "replace with a valid protective sell stop order."
        )

    if "STOP_PROTECTION_MISSING" in codes:
        status = RecommendationStatus.REDUCE
        confidence = RecommendationConfidence.LOW
        risk_level = RecommendationRiskLevel.HIGH
        blocked_by_risk = True
        warnings.append(
            "Risk warning: stop protection is missing for a large position."
        )
        invalidation.append(
            "If no protective stop is added, avoid adding exposure and reassess risk controls."
        )

    if status == RecommendationStatus.HOLD and not holding.price_available:
        status = RecommendationStatus.WATCH

    return HoldingRecommendation(
        ticker=holding.ticker,
        status=status,
        confidence=confidence,
        risk_level=risk_level,
        reasoning_inputs=tuple(reasoning),
        warnings=tuple(warnings),
        invalidation_conditions=tuple(invalidation),
        blocked_by_risk=blocked_by_risk,
        data_quality=data_quality,
        suggested_action=suggested_action,
    )


def _recommend_cash_deployment(
    snapshot: PortfolioSnapshot,
    risk_assessment: RiskAssessment,
) -> CashDeploymentStatus:
    reasoning = [
        "Deterministic status uses valuation completeness, cash allocation, and risk warnings.",
        (
            "Technical/fundamental engines are unavailable, so no "
            "ticker-level buy candidates are provided."
        ),
    ]
    warnings: list[str] = []

    if snapshot.valuation_status != "complete":
        warnings.append(
            "Valuation is incomplete; portfolio-level deployment confidence is limited."
        )
        return CashDeploymentStatus(
            status=CashDeploymentRecommendationStatus.INSUFFICIENT_DATA,
            confidence=RecommendationConfidence.LOW,
            reasoning_inputs=tuple(reasoning),
            warnings=tuple(warnings),
            suggested_action=(
                "Suggested review action: complete valuation inputs before "
                "evaluating new buys."
            ),
        )

    high_risk_codes = {
        "LOW_CASH_RESERVE",
        "HIGH_CASH_DEPLOYMENT",
        "PORTFOLIO_UNREALIZED_LOSS_LIMIT",
        "POSITION_CONCENTRATION_LIMIT",
        "STOP_PROTECTION_MISSING",
    }
    present_high_risk = {
        warning.code
        for warning in risk_assessment.warnings
        if warning.code in high_risk_codes
    }
    if present_high_risk:
        reasoning.append(
            "Risk warnings influencing cash decision: "
            + ", ".join(sorted(present_high_risk))
        )
        return CashDeploymentStatus(
            status=CashDeploymentRecommendationStatus.AVOID_NEW_BUYS,
            confidence=RecommendationConfidence.MEDIUM,
            reasoning_inputs=tuple(reasoning),
            warnings=("Risk warning: high-risk portfolio conditions are active.",),
            suggested_action=(
                "Suggested review action: avoid increasing exposure until "
                "risk warnings clear."
            ),
        )

    cash_pct = float(snapshot.cash_allocation_percent or "0")
    if cash_pct < 10:
        return CashDeploymentStatus(
            status=CashDeploymentRecommendationStatus.KEEP_CASH,
            confidence=RecommendationConfidence.MEDIUM,
            reasoning_inputs=tuple(reasoning),
            warnings=("Cash reserve is near minimum thresholds; preserve liquidity.",),
            suggested_action=(
                "Suggested review action: rebuild cash reserve before "
                "considering new positions."
            ),
        )

    return CashDeploymentStatus(
        status=CashDeploymentRecommendationStatus.DEPLOY_CAUTIOUSLY,
        confidence=RecommendationConfidence.LOW,
        reasoning_inputs=tuple(reasoning),
        warnings=(),
        suggested_action=(
            "Suggested review action: only consider cautious deployment "
            "after separate technical/fundamental validation."
        ),
    )


def _warnings_by_ticker(
    risk_assessment: RiskAssessment,
) -> dict[str, list[tuple[str, str]]]:
    by_ticker: dict[str, list[tuple[str, str]]] = {}
    for warning in risk_assessment.warnings:
        if warning.ticker is None:
            continue
        by_ticker.setdefault(warning.ticker.upper(), []).append(
            (warning.code, warning.severity)
        )
    return by_ticker


def _build_limitations(
    portfolio: Portfolio, snapshot: PortfolioSnapshot, risk_assessment: RiskAssessment
) -> list[str]:
    limitations = [
        "Decision support only; not financial advice.",
        "Technical analysis is not implemented in this release.",
        "Fundamental analysis is not implemented in this release.",
        "News/sentiment inputs are not implemented in this release.",
    ]
    if snapshot.price_completeness_status != "complete":
        limitations.append(
            "Price coverage is incomplete, reducing recommendation confidence."
        )
    if snapshot.valuation_status != "complete":
        limitations.append("Portfolio valuation is incomplete or unavailable.")
    if not portfolio.goals:
        limitations.append("Goal/timeline data is missing.")
    if (
        portfolio.risk_profile is None
        or portfolio.risk_profile.level == RiskLevel.MODERATE
    ):
        if portfolio.risk_profile is None:
            limitations.append("Risk profile defaulted to moderate assumptions.")
    if any(item.code == "RISK_PROFILE_DEFAULTED" for item in risk_assessment.warnings):
        limitations.append("Risk profile default warning is active.")
    return limitations


def _holding_to_dict(item: HoldingRecommendation) -> dict[str, object]:
    payload = asdict(item)
    payload["status"] = item.status.value
    payload["confidence"] = item.confidence.value
    payload["risk_level"] = item.risk_level.value
    return payload


def _cash_to_dict(item: CashDeploymentStatus) -> dict[str, object]:
    payload = asdict(item)
    payload["status"] = item.status.value
    payload["confidence"] = item.confidence.value
    return payload
