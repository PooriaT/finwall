from decimal import Decimal

from finwall.models import (
    ActiveOrder,
    CashBalance,
    Holding,
    OrderSide,
    OrderType,
    Portfolio,
    RiskLevel,
    RiskProfile,
)
from finwall.recommendations import (
    CashDeploymentRecommendationStatus,
    RecommendationConfidence,
    RecommendationStatus,
    build_recommendation_report,
)
from finwall.risk import assess_portfolio_risk
from finwall.snapshot import generate_snapshot


def test_every_holding_receives_recommendation() -> None:
    portfolio = Portfolio(
        name="Primary",
        holdings=(
            Holding("NVDA", Decimal("1"), Decimal("100")),
            Holding("PLTR", Decimal("2"), Decimal("20")),
        ),
    )
    snapshot = generate_snapshot(
        portfolio, {"NVDA": Decimal("110"), "PLTR": Decimal("30")}
    )
    risk = assess_portfolio_risk(portfolio, snapshot)
    report = build_recommendation_report(portfolio, snapshot, risk)
    assert len(report.holdings) == 2


def test_missing_price_watch_low_confidence() -> None:
    portfolio = Portfolio(
        name="Primary",
        risk_profile=RiskProfile(RiskLevel.MODERATE),
        cash_balances=(CashBalance("USD", Decimal("1000")),),
        holdings=(Holding("NVDA", Decimal("1"), Decimal("100")),),
    )
    snapshot = generate_snapshot(portfolio)
    risk = assess_portfolio_risk(portfolio, snapshot)
    item = build_recommendation_report(portfolio, snapshot, risk).holdings[0]
    assert item.status == RecommendationStatus.WATCH
    assert item.confidence == RecommendationConfidence.LOW


def test_concentration_warning_reduces_and_blocks_buy() -> None:
    portfolio = Portfolio(
        name="Primary",
        risk_profile=RiskProfile(RiskLevel.CONSERVATIVE),
        cash_balances=(CashBalance("USD", Decimal("10")),),
        holdings=(Holding("NVDA", Decimal("1"), Decimal("100")),),
    )
    snapshot = generate_snapshot(portfolio, {"NVDA": Decimal("100")})
    risk = assess_portfolio_risk(portfolio, snapshot)
    item = build_recommendation_report(portfolio, snapshot, risk).holdings[0]
    assert item.status in {RecommendationStatus.REDUCE, RecommendationStatus.WATCH}
    assert item.blocked_by_risk is True


def test_large_unrealized_loss_lowers_confidence() -> None:
    portfolio = Portfolio(
        name="Primary",
        risk_profile=RiskProfile(RiskLevel.MODERATE),
        holdings=(Holding("NVDA", Decimal("1"), Decimal("200")),),
    )
    snapshot = generate_snapshot(portfolio, {"NVDA": Decimal("100")})
    risk = assess_portfolio_risk(portfolio, snapshot)
    item = build_recommendation_report(portfolio, snapshot, risk).holdings[0]
    assert item.confidence == RecommendationConfidence.LOW


def test_complete_data_without_high_risk_is_hold() -> None:
    portfolio = Portfolio(
        name="Primary",
        risk_profile=RiskProfile(RiskLevel.MODERATE),
        cash_balances=(CashBalance("USD", Decimal("1000")),),
        holdings=(Holding("NVDA", Decimal("1"), Decimal("100")),),
    )
    snapshot = generate_snapshot(portfolio, {"NVDA": Decimal("110")})
    risk = assess_portfolio_risk(portfolio, snapshot)
    item = build_recommendation_report(portfolio, snapshot, risk).holdings[0]
    assert item.status == RecommendationStatus.HOLD


def test_cash_insufficient_data_when_valuation_unavailable() -> None:
    portfolio = Portfolio(
        name="Primary",
        risk_profile=RiskProfile(RiskLevel.MODERATE),
        cash_balances=(CashBalance("USD", Decimal("1000")),),
        holdings=(Holding("NVDA", Decimal("1"), Decimal("100")),),
    )
    snapshot = generate_snapshot(portfolio)
    risk = assess_portfolio_risk(portfolio, snapshot)
    cash = build_recommendation_report(portfolio, snapshot, risk).cash_deployment
    assert cash.status == CashDeploymentRecommendationStatus.INSUFFICIENT_DATA


def test_cash_avoid_new_buys_when_high_risk_exists() -> None:
    portfolio = Portfolio(
        name="Primary",
        risk_profile=RiskProfile(RiskLevel.CONSERVATIVE),
        cash_balances=(CashBalance("USD", Decimal("10")),),
        holdings=(Holding("NVDA", Decimal("1"), Decimal("100")),),
    )
    snapshot = generate_snapshot(portfolio, {"NVDA": Decimal("100")})
    risk = assess_portfolio_risk(portfolio, snapshot)
    cash = build_recommendation_report(portfolio, snapshot, risk).cash_deployment
    assert cash.status == CashDeploymentRecommendationStatus.AVOID_NEW_BUYS


def test_cash_deploy_cautiously_when_healthy_and_no_warnings() -> None:
    portfolio = Portfolio(
        name="Primary",
        risk_profile=RiskProfile(RiskLevel.MODERATE),
        cash_balances=(CashBalance("USD", Decimal("3000")),),
        holdings=(Holding("NVDA", Decimal("1"), Decimal("100")),),
    )
    snapshot = generate_snapshot(portfolio, {"NVDA": Decimal("100")})
    risk = assess_portfolio_risk(portfolio, snapshot)
    cash = build_recommendation_report(portfolio, snapshot, risk).cash_deployment
    assert cash.status == CashDeploymentRecommendationStatus.DEPLOY_CAUTIOUSLY


def test_invalid_stop_protection_order_blocks_by_risk() -> None:
    portfolio = Portfolio(
        name="Primary",
        risk_profile=RiskProfile(RiskLevel.MODERATE),
        holdings=(Holding("NVDA", Decimal("1"), Decimal("100")),),
        active_orders=(
            ActiveOrder(
                "NVDA",
                OrderSide.SELL,
                OrderType.LIMIT,
                Decimal("1"),
                limit_price=Decimal("120"),
            ),
        ),
    )
    snapshot = generate_snapshot(portfolio, {"NVDA": Decimal("100")})
    risk = assess_portfolio_risk(portfolio, snapshot)
    item = build_recommendation_report(portfolio, snapshot, risk).holdings[0]

    assert item.status == RecommendationStatus.REDUCE
    assert item.blocked_by_risk is True
    assert any("invalid" in warning.lower() for warning in item.warnings)


def test_recommendation_wording_reflects_optional_analysis_inputs() -> None:
    portfolio = Portfolio(
        name="Primary",
        cash_balances=(CashBalance("USD", Decimal("1000")),),
        holdings=(Holding("NVDA", Decimal("1"), Decimal("100")),),
    )
    snapshot = generate_snapshot(portfolio, {"NVDA": Decimal("110")})
    risk = assess_portfolio_risk(portfolio, snapshot)
    report = build_recommendation_report(portfolio, snapshot, risk)

    output_text = "\n".join(
        (
            *report.limitations,
            *report.holdings[0].reasoning_inputs,
            *report.cash_deployment.reasoning_inputs,
        )
    )

    stale_phrases = (
        "Technical analysis" + " is not implemented",
        "Fundamental analysis" + " is not implemented",
        "News/sentiment inputs" + " are not implemented",
        "Technical/fundamental engines" + " are unavailable",
    )
    for phrase in stale_phrases:
        assert phrase not in output_text

    assert "Decision support only; not financial advice." in report.limitations
    assert "optional technical/fundamental/news inputs" in output_text
    assert "not yet authoritative drivers" in output_text
    assert "optional/experimental decision-support inputs" in output_text
    assert "not used to generate ticker-level buy candidates" in output_text


def test_recommendation_limitations_preserve_data_quality_warnings() -> None:
    portfolio = Portfolio(
        name="Primary",
        holdings=(Holding("NVDA", Decimal("1"), Decimal("100")),),
    )
    snapshot = generate_snapshot(portfolio)
    risk = assess_portfolio_risk(portfolio, snapshot)
    report = build_recommendation_report(portfolio, snapshot, risk)

    assert "Decision support only; not financial advice." in report.limitations
    assert "Price coverage is incomplete, reducing recommendation confidence." in (
        report.limitations
    )
    assert "Portfolio valuation is incomplete or unavailable." in report.limitations
    assert "Goal/timeline data is missing." in report.limitations
    assert "Risk profile defaulted to moderate assumptions." in report.limitations
    assert "Risk profile default warning is active." in report.limitations
