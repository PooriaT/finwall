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
from finwall.risk import RISK_RULES_BY_LEVEL, assess_portfolio_risk
from finwall.snapshot import generate_snapshot


def test_profile_rule_defaults() -> None:
    assert (
        RISK_RULES_BY_LEVEL[RiskLevel.CONSERVATIVE].max_single_position_percent
        < RISK_RULES_BY_LEVEL[RiskLevel.MODERATE].max_single_position_percent
        < RISK_RULES_BY_LEVEL[RiskLevel.AGGRESSIVE].max_single_position_percent
    )


def test_defaults_to_moderate_when_profile_missing() -> None:
    portfolio = Portfolio(name="Primary")
    snapshot = generate_snapshot(portfolio)
    assessment = assess_portfolio_risk(portfolio, snapshot)
    assert assessment.risk_level == "moderate"
    assert any(item.code == "RISK_PROFILE_DEFAULTED" for item in assessment.warnings)


def test_concentration_and_cash_warnings() -> None:
    portfolio = Portfolio(
        name="Primary",
        risk_profile=RiskProfile(RiskLevel.CONSERVATIVE),
        cash_balances=(CashBalance("USD", Decimal("10")),),
        holdings=(Holding("NVDA", Decimal("1"), Decimal("100")),),
    )
    snapshot = generate_snapshot(portfolio, latest_prices={"NVDA": Decimal("100")})
    assessment = assess_portfolio_risk(portfolio, snapshot)
    codes = {item.code for item in assessment.warnings}
    assert "POSITION_CONCENTRATION_LIMIT" in codes
    assert "LOW_CASH_RESERVE" in codes


def test_missing_price_and_multi_currency_warnings() -> None:
    portfolio = Portfolio(
        name="Primary",
        risk_profile=RiskProfile(RiskLevel.MODERATE),
        cash_balances=(
            CashBalance("USD", Decimal("50")),
            CashBalance("EUR", Decimal("50")),
        ),
        holdings=(Holding("PLTR", Decimal("1"), Decimal("10")),),
    )
    snapshot = generate_snapshot(portfolio)
    assessment = assess_portfolio_risk(portfolio, snapshot)
    codes = {item.code for item in assessment.warnings}
    assert "PRICE_DATA_INCOMPLETE" in codes
    assert "MULTI_CURRENCY_VALUATION_UNAVAILABLE" in codes


def test_unrealized_loss_and_stop_protection_warnings() -> None:
    portfolio = Portfolio(
        name="Primary",
        risk_profile=RiskProfile(RiskLevel.MODERATE),
        cash_balances=(CashBalance("USD", Decimal("10")),),
        holdings=(Holding("NVDA", Decimal("1"), Decimal("200")),),
    )
    snapshot = generate_snapshot(portfolio, latest_prices={"NVDA": Decimal("100")})
    assessment = assess_portfolio_risk(portfolio, snapshot)
    codes = {item.code for item in assessment.warnings}
    assert "PORTFOLIO_UNREALIZED_LOSS_LIMIT" in codes
    assert "HOLDING_UNREALIZED_LOSS_LIMIT" in codes
    assert "STOP_PROTECTION_MISSING" in codes


def test_holding_loss_uses_cost_basis_denominator() -> None:
    portfolio = Portfolio(
        name="Primary",
        risk_profile=RiskProfile(RiskLevel.MODERATE),
        holdings=(Holding("NVDA", Decimal("1"), Decimal("100")),),
    )
    snapshot = generate_snapshot(portfolio, latest_prices={"NVDA": Decimal("86")})
    assessment = assess_portfolio_risk(portfolio, snapshot)
    holding_warning = next(
        (item for item in assessment.warnings if item.code == "HOLDING_UNREALIZED_LOSS_LIMIT"),
        None,
    )
    assert holding_warning is None

def test_no_stop_warning_when_valid_sell_stop_exists() -> None:
    portfolio = Portfolio(
        name="Primary",
        risk_profile=RiskProfile(RiskLevel.MODERATE),
        holdings=(Holding("NVDA", Decimal("1"), Decimal("100")),),
        active_orders=(
            ActiveOrder(
                "NVDA",
                OrderSide.SELL,
                OrderType.STOP_LOSS,
                Decimal("1"),
                stop_price=Decimal("95"),
            ),
        ),
    )
    snapshot = generate_snapshot(portfolio, latest_prices={"NVDA": Decimal("100")})
    assessment = assess_portfolio_risk(portfolio, snapshot)
    assert not any(
        item.code.startswith("STOP_PROTECTION") for item in assessment.warnings
    )
