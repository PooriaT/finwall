from decimal import Decimal

from finwall.market_data import IndexQuote
from finwall.models import CashBalance, Holding, Portfolio, RiskLevel, RiskProfile
from finwall.recommendations import build_recommendation_report
from finwall.reports import build_decision_support_report
from finwall.risk import assess_portfolio_risk
from finwall.snapshot import generate_snapshot


def _build_base_report(with_index: bool = False):
    portfolio = Portfolio(
        name="Primary",
        risk_profile=RiskProfile(RiskLevel.CONSERVATIVE),
        cash_balances=(CashBalance("USD", Decimal("10")),),
        holdings=(Holding("NVDA", Decimal("1"), Decimal("100")),),
    )
    snapshot = generate_snapshot(portfolio, {"NVDA": Decimal("100")})
    risk = assess_portfolio_risk(portfolio, snapshot)
    rec = build_recommendation_report(portfolio, snapshot, risk)
    quote = IndexQuote("SP500", Decimal("5050"), "static", True) if with_index else None
    return build_decision_support_report(portfolio, snapshot, risk, rec, quote)


def test_report_json_contains_required_keys() -> None:
    report = _build_base_report()
    payload = report.as_dict()
    assert set(payload.keys()) == {
        "disclaimer",
        "portfolio_snapshot",
        "market_condition",
        "holding_recommendations",
        "cash_allocation_plan",
        "suggested_orders",
        "strategy_assessment",
        "risks_and_warnings",
        "final_action_plan",
        "limitations",
    }


def test_markdown_contains_required_headings() -> None:
    md = _build_base_report().to_markdown()
    for heading in [
        "# Finwall Decision-Support Report",
        "## Disclaimer",
        "## Portfolio Snapshot",
        "## Market Condition",
        "## Holding Recommendations",
        "## Cash Allocation Plan",
        "## Suggested Orders",
        "## Strategy Assessment",
        "## Risks and Warnings",
        "## Final Action Plan",
        "## Limitations",
    ]:
        assert heading in md


def test_market_condition_without_quote_not_evaluated() -> None:
    report = _build_base_report()
    assert report.market_condition.status == "not_evaluated"


def test_market_condition_with_quote_raw_index_only() -> None:
    report = _build_base_report(with_index=True)
    assert report.market_condition.status == "raw_index_only"


def test_strategy_insufficient_data_when_missing_prices() -> None:
    portfolio = Portfolio(
        name="Primary", holdings=(Holding("NVDA", Decimal("1"), Decimal("100")),)
    )
    snapshot = generate_snapshot(portfolio)
    risk = assess_portfolio_risk(portfolio, snapshot)
    rec = build_recommendation_report(portfolio, snapshot, risk)
    report = build_decision_support_report(portfolio, snapshot, risk, rec)
    assert report.strategy_assessment.status == "insufficient_data"


def test_suggested_orders_does_not_invent_orders() -> None:
    report = _build_base_report()
    assert report.suggested_orders.evaluated_orders == ()


def test_cash_allocation_plan_from_recommendation_report() -> None:
    report = _build_base_report()
    assert report.cash_allocation_plan["status"] == "avoid_new_buys"


def test_holding_recommendations_include_warnings() -> None:
    report = _build_base_report()
    assert report.holding_recommendations[0]["warnings"]


def test_report_builds_with_empty_portfolio() -> None:
    portfolio = Portfolio(name="Primary")
    snapshot = generate_snapshot(portfolio)
    risk = assess_portfolio_risk(portfolio, snapshot)
    rec = build_recommendation_report(portfolio, snapshot, risk)
    report = build_decision_support_report(portfolio, snapshot, risk, rec)
    assert report.portfolio_snapshot["holdings_summary"] == 0


def test_report_output_omits_stale_recommendation_limitation_wording() -> None:
    report = _build_base_report()
    markdown = report.to_markdown()
    payload_text = str(report.as_dict())
    output_text = f"{markdown}\n{payload_text}"

    stale_phrases = (
        "Technical analysis" + " is not implemented",
        "Fundamental analysis" + " is not implemented",
        "News/sentiment inputs" + " are not implemented",
        "Technical/fundamental engines" + " are unavailable",
    )
    for phrase in stale_phrases:
        assert phrase not in output_text

    assert "optional/experimental decision-support inputs" in output_text
