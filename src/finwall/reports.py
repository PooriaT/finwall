from __future__ import annotations

import json
from dataclasses import asdict, dataclass

from finwall.market_data import IndexQuote
from finwall.models import Portfolio
from finwall.recommendations import (
    CashDeploymentRecommendationStatus,
    RecommendationReport,
)
from finwall.risk import RiskAssessment
from finwall.snapshot import PortfolioSnapshot


@dataclass(frozen=True)
class MarketConditionSection:
    status: str
    summary: str
    inputs: dict[str, object]
    limitations: tuple[str, ...]


@dataclass(frozen=True)
class SuggestedOrdersSection:
    active_orders: tuple[dict[str, object], ...]
    evaluated_orders: tuple[dict[str, object], ...]
    summary: str
    limitations: tuple[str, ...]


@dataclass(frozen=True)
class StrategyAssessmentSection:
    status: str
    summary: str
    reasoning_inputs: tuple[str, ...]
    warnings: tuple[str, ...]


@dataclass(frozen=True)
class FinalActionPlanSection:
    immediate_actions: tuple[str, ...]
    monitor: tuple[str, ...]
    avoid: tuple[str, ...]
    missing_information: tuple[str, ...]
    disclaimer: str


@dataclass(frozen=True)
class DecisionSupportReport:
    disclaimer: str
    portfolio_snapshot: dict[str, object]
    market_condition: MarketConditionSection
    holding_recommendations: tuple[dict[str, object], ...]
    cash_allocation_plan: dict[str, object]
    suggested_orders: SuggestedOrdersSection
    strategy_assessment: StrategyAssessmentSection
    risks_and_warnings: dict[str, object]
    final_action_plan: FinalActionPlanSection
    limitations: tuple[str, ...]

    def as_dict(self) -> dict[str, object]:
        payload = asdict(self)
        payload["market_condition"] = asdict(self.market_condition)
        payload["suggested_orders"] = asdict(self.suggested_orders)
        payload["strategy_assessment"] = asdict(self.strategy_assessment)
        payload["final_action_plan"] = asdict(self.final_action_plan)
        return payload

    def to_json(self) -> str:
        return json.dumps(self.as_dict(), indent=2)

    def to_markdown(self) -> str:
        lines = [
            "# Finwall Decision-Support Report",
            "",
            "## Disclaimer",
            self.disclaimer,
            "",
            "## Portfolio Snapshot",
        ]
        for key, value in self.portfolio_snapshot.items():
            lines.append(f"- {key}: {value}")

        lines.extend(
            [
                "",
                "## Market Condition",
                f"- Status: {self.market_condition.status}",
                f"- Summary: {self.market_condition.summary}",
            ]
        )
        for key, value in self.market_condition.inputs.items():
            lines.append(f"- Input {key}: {value}")

        lines.extend(["", "## Holding Recommendations"])
        if not self.holding_recommendations:
            lines.append("- None")
        for item in self.holding_recommendations:
            lines.append(
                f"- {item['ticker']}: status={item['status']} "
                f"confidence={item['confidence']} risk={item['risk_level']}"
            )
            lines.append(
                f"  - suggested_review_action: {item['suggested_review_action']}"
            )
            lines.append(f"  - blocked_by_risk: {item['blocked_by_risk']}")
            lines.append(f"  - data_quality: {item['data_quality']}")
            lines.append(
                f"  - warnings: {', '.join(item['warnings']) if item['warnings'] else 'none'}"
            )

        lines.extend(["", "## Cash Allocation Plan"])
        for key, value in self.cash_allocation_plan.items():
            lines.append(f"- {key}: {value}")

        lines.extend(
            [
                "",
                "## Suggested Orders",
                f"- Summary: {self.suggested_orders.summary}",
                "- Active orders:",
            ]
        )
        if not self.suggested_orders.active_orders:
            lines.append("  - none")
        for order in self.suggested_orders.active_orders:
            lines.append(f"  - {order['description']}")

        lines.extend(
            [
                "",
                "## Strategy Assessment",
                f"- Status: {self.strategy_assessment.status}",
                f"- Summary: {self.strategy_assessment.summary}",
                "",
                "## Risks and Warnings",
                f"- Summary: {self.risks_and_warnings['risk_summary']}",
            ]
        )
        for warning in self.risks_and_warnings["risk_warnings"]:
            lines.append(f"- {warning}")

        lines.extend(["", "## Final Action Plan"])
        for key in ("immediate_actions", "monitor", "avoid", "missing_information"):
            lines.append(f"- {key}: {', '.join(self.final_action_plan.__dict__[key])}")

        lines.extend(["", "## Limitations"])
        for item in self.limitations:
            lines.append(f"- {item}")

        return "\n".join(lines)


def build_decision_support_report(
    portfolio: Portfolio,
    snapshot: PortfolioSnapshot,
    risk_assessment: RiskAssessment,
    recommendation_report: RecommendationReport,
    market_index_quote: IndexQuote | None = None,
) -> DecisionSupportReport:
    disclaimer = (
        "Decision-support output only. Not financial advice, not guaranteed outcomes, "
        "and not an instruction to buy or sell any security."
    )
    portfolio_snapshot = {
        "cash_balance": snapshot.cash_balance,
        "invested_value": snapshot.invested_value,
        "total_portfolio_value": snapshot.total_portfolio_value,
        "cash_allocation": snapshot.cash_allocation_percent,
        "invested_allocation": snapshot.invested_allocation_percent,
        "price_coverage": snapshot.price_completeness_status,
        "valuation_status": snapshot.valuation_status,
        "holdings_summary": len(snapshot.holdings),
        "total_unrealized_gain_loss": snapshot.total_unrealized_gain_loss,
    }

    market_condition = _build_market_condition(market_index_quote)
    holdings = tuple(_holding_dict(item) for item in recommendation_report.holdings)
    cash_plan = {
        "status": recommendation_report.cash_deployment.status.value,
        "confidence": recommendation_report.cash_deployment.confidence.value,
        "suggested_review_action": recommendation_report.cash_deployment.suggested_action,
        "reasoning_inputs": list(
            recommendation_report.cash_deployment.reasoning_inputs
        ),
        "warnings": list(recommendation_report.cash_deployment.warnings),
    }
    suggested_orders = SuggestedOrdersSection(
        active_orders=tuple(asdict(order) for order in snapshot.active_orders),
        evaluated_orders=tuple(),
        summary=(
            "Finwall report includes existing active orders only; new order "
            "suggestion generation is not implemented in this report."
            if snapshot.active_orders
            else (
                "No active orders recorded. Finwall does not generate new order "
                "suggestions in this report."
            )
        ),
        limitations=("No automatic order generation in this report layer.",),
    )

    strategy = _build_strategy(snapshot, risk_assessment, recommendation_report)
    risks_and_warnings = {
        "risk_summary": risk_assessment.summary,
        "risk_warnings": [w.message for w in risk_assessment.warnings],
        "recommendation_limitations": list(recommendation_report.limitations),
        "missing_price_warnings": [
            h.missing_price_message
            for h in snapshot.holdings
            if h.missing_price_message is not None
        ],
        "multi_currency_valuation_warnings": [
            "Multi-currency valuation unavailable without FX conversion."
        ]
        if snapshot.multi_currency_cash
        else [],
        "disclaimer": disclaimer,
    }

    final_action = _build_final_action(snapshot, risk_assessment, recommendation_report)
    limitations = tuple(
        dict.fromkeys(
            (*recommendation_report.limitations, *market_condition.limitations)
        )
    )

    return DecisionSupportReport(
        disclaimer=disclaimer,
        portfolio_snapshot=portfolio_snapshot,
        market_condition=market_condition,
        holding_recommendations=holdings,
        cash_allocation_plan=cash_plan,
        suggested_orders=suggested_orders,
        strategy_assessment=strategy,
        risks_and_warnings=risks_and_warnings,
        final_action_plan=final_action,
        limitations=limitations,
    )


def _build_market_condition(
    market_index_quote: IndexQuote | None,
) -> MarketConditionSection:
    if market_index_quote is None:
        return MarketConditionSection(
            status="not_evaluated",
            summary="Market condition is not evaluated; future analysis modules are required.",
            inputs={},
            limitations=("Trend classification is not implemented yet.",),
        )
    return MarketConditionSection(
        status="raw_index_only",
        summary="Raw index quote is included; trend classification is not implemented yet.",
        inputs={
            "symbol": market_index_quote.symbol,
            "price": str(market_index_quote.price)
            if market_index_quote.price is not None
            else None,
            "source": market_index_quote.source,
            "available": market_index_quote.available,
            "error": market_index_quote.error,
        },
        limitations=("Trend classification is not implemented yet.",),
    )


def _build_strategy(
    snapshot: PortfolioSnapshot,
    risk_assessment: RiskAssessment,
    recommendation_report: RecommendationReport,
) -> StrategyAssessmentSection:
    warnings = tuple(w.message for w in risk_assessment.warnings)
    if snapshot.valuation_status != "complete":
        status = "insufficient_data"
    elif risk_assessment.has_high_risk_warning:
        status = "reduce_risk_first"
    elif recommendation_report.cash_deployment.status in {
        CashDeploymentRecommendationStatus.KEEP_CASH,
        CashDeploymentRecommendationStatus.AVOID_NEW_BUYS,
    }:
        status = "preserve_cash"
    else:
        status = "continue_monitoring"

    return StrategyAssessmentSection(
        status=status,
        summary=(
            "Deterministic strategy status from valuation completeness, risk "
            "warnings, and cash deployment status."
        ),
        reasoning_inputs=(
            f"valuation_status={snapshot.valuation_status}",
            f"has_high_risk_warning={risk_assessment.has_high_risk_warning}",
            f"cash_deployment_status={recommendation_report.cash_deployment.status.value}",
        ),
        warnings=warnings,
    )


def _build_final_action(
    snapshot: PortfolioSnapshot,
    risk_assessment: RiskAssessment,
    recommendation_report: RecommendationReport,
) -> FinalActionPlanSection:
    immediate = [
        "Review risk warnings and valuation completeness before any portfolio changes."
    ]
    monitor = [
        "Monitor missing prices and active stop-loss/stop-limit protection coverage."
    ]
    avoid = ["Do not treat deterministic statuses as guaranteed outcomes."]
    missing = []

    if snapshot.price_completeness_status != "complete":
        immediate.append("Provide missing prices for incomplete holdings.")
        missing.append("Current prices for all holdings.")
    if any(
        w.code in {"STOP_PROTECTION_MISSING", "STOP_PROTECTION_INVALID_ORDER"}
        for w in risk_assessment.warnings
    ):
        immediate.append(
            "Check active stop-loss or stop-limit protection for large positions."
        )
    if (
        recommendation_report.cash_deployment.status
        == CashDeploymentRecommendationStatus.AVOID_NEW_BUYS
    ):
        avoid.append("Avoid new buys while cash deployment status is avoid_new_buys.")

    return FinalActionPlanSection(
        immediate_actions=tuple(immediate),
        monitor=tuple(monitor),
        avoid=tuple(avoid),
        missing_information=tuple(missing),
        disclaimer="Decision-support plan only; not financial advice.",
    )


def _holding_dict(item) -> dict[str, object]:
    return {
        "ticker": item.ticker,
        "status": item.status.value,
        "confidence": item.confidence.value,
        "risk_level": item.risk_level.value,
        "suggested_review_action": item.suggested_action,
        "blocked_by_risk": item.blocked_by_risk,
        "data_quality": item.data_quality,
        "reasoning_inputs": list(item.reasoning_inputs),
        "warnings": list(item.warnings),
        "invalidation_conditions": list(item.invalidation_conditions),
    }
