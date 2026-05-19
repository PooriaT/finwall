from decimal import Decimal

from finwall.models import CashBalance, Holding, Portfolio, RiskLevel, RiskProfile
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
