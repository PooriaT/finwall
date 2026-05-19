from decimal import Decimal

from finwall.models import (
    CashBalance,
    Holding,
    InvestmentGoal,
    OrderSide,
    OrderType,
    Portfolio,
    RiskLevel,
    RiskProfile,
)
from finwall.order_evaluation import ProposedOrder, evaluate_proposed_order
from finwall.snapshot import generate_snapshot


def make_portfolio(**kwargs):
    return Portfolio(name="Primary", **kwargs)


def test_buy_limit_order_valid_stop_target():
    p = make_portfolio(cash_balances=(CashBalance("USD", Decimal("1000")),))
    s = generate_snapshot(p)
    e = evaluate_proposed_order(
        p,
        s,
        ProposedOrder(
            "NVDA",
            OrderSide.BUY,
            OrderType.LIMIT,
            Decimal("100"),
            Decimal("2"),
            stop_price=Decimal("90"),
            limit_price=Decimal("100"),
            target_price=Decimal("120"),
        ),
    )
    assert e.valid
    assert e.risk_reward_ratio == "2.00"


def test_buy_order_exceeds_cash_maximum():
    p = make_portfolio(cash_balances=(CashBalance("USD", Decimal("100")),))
    s = generate_snapshot(p)
    e = evaluate_proposed_order(
        p,
        s,
        ProposedOrder(
            "NVDA",
            OrderSide.BUY,
            OrderType.LIMIT,
            Decimal("60"),
            Decimal("2"),
            limit_price=Decimal("60"),
        ),
    )
    assert any(
        "exceed" in warning and "safe maximum" in warning for warning in e.warnings
    )


def test_buy_order_invalid_stop_above_entry():
    p = make_portfolio(cash_balances=(CashBalance("USD", Decimal("1000")),))
    s = generate_snapshot(p)
    e = evaluate_proposed_order(
        p,
        s,
        ProposedOrder(
            "NVDA",
            OrderSide.BUY,
            OrderType.LIMIT,
            Decimal("100"),
            Decimal("1"),
            stop_price=Decimal("101"),
            limit_price=Decimal("100"),
        ),
    )
    assert not e.valid


def test_buy_order_invalid_target_below_entry():
    p = make_portfolio(cash_balances=(CashBalance("USD", Decimal("1000")),))
    s = generate_snapshot(p)
    e = evaluate_proposed_order(
        p,
        s,
        ProposedOrder(
            "NVDA",
            OrderSide.BUY,
            OrderType.LIMIT,
            Decimal("100"),
            Decimal("1"),
            target_price=Decimal("99"),
            limit_price=Decimal("100"),
        ),
    )
    assert not e.valid


def test_sell_limit_and_reject_excess():
    p = make_portfolio(holdings=(Holding("NVDA", Decimal("2"), Decimal("100")),))
    s = generate_snapshot(p, {"NVDA": Decimal("110")})
    ok = evaluate_proposed_order(
        p,
        s,
        ProposedOrder(
            "NVDA",
            OrderSide.SELL,
            OrderType.LIMIT,
            Decimal("110"),
            Decimal("1"),
            limit_price=Decimal("110"),
        ),
    )
    bad = evaluate_proposed_order(
        p,
        s,
        ProposedOrder(
            "NVDA",
            OrderSide.SELL,
            OrderType.LIMIT,
            Decimal("110"),
            Decimal("3"),
            limit_price=Decimal("110"),
        ),
    )
    assert ok.valid
    assert not bad.valid


def test_sell_stop_validations():
    p = make_portfolio(holdings=(Holding("NVDA", Decimal("2"), Decimal("100")),))
    s = generate_snapshot(p)
    e1 = evaluate_proposed_order(
        p,
        s,
        ProposedOrder(
            "NVDA", OrderSide.SELL, OrderType.STOP_LOSS, Decimal("100"), Decimal("1")
        ),
    )
    e2 = evaluate_proposed_order(
        p,
        s,
        ProposedOrder(
            "NVDA",
            OrderSide.SELL,
            OrderType.STOP_LIMIT,
            Decimal("100"),
            Decimal("1"),
            stop_price=Decimal("95"),
        ),
    )
    assert not e1.valid
    assert not e2.valid


def test_risk_profile_and_default_and_goal_warnings():
    p1 = make_portfolio(
        cash_balances=(CashBalance("USD", Decimal("1000")),),
        risk_profile=RiskProfile(RiskLevel.CONSERVATIVE),
        goals=(InvestmentGoal("Goal", Decimal("5000")),),
    )
    p2 = make_portfolio(cash_balances=(CashBalance("USD", Decimal("1000")),))
    s1 = generate_snapshot(p1)
    s2 = generate_snapshot(p2)
    o = ProposedOrder(
        "NVDA",
        OrderSide.BUY,
        OrderType.LIMIT,
        Decimal("100"),
        Decimal("5"),
        stop_price=Decimal("90"),
        limit_price=Decimal("100"),
        target_price=Decimal("120"),
    )
    e1 = evaluate_proposed_order(p1, s1, o)
    e2 = evaluate_proposed_order(p2, s2, o)
    assert Decimal(e1.suggested_maximum_shares) <= Decimal(e2.suggested_maximum_shares)
    assert any("No portfolio goal" in w for w in e2.warnings)


def test_goal_target_missing_and_valuation_warning():
    p = make_portfolio(
        cash_balances=(
            CashBalance("USD", Decimal("100")),
            CashBalance("EUR", Decimal("50")),
        ),
        goals=(InvestmentGoal("Goal"),),
        holdings=(Holding("NVDA", Decimal("1"), Decimal("100")),),
    )
    s = generate_snapshot(p)
    e = evaluate_proposed_order(
        p,
        s,
        ProposedOrder(
            "NVDA",
            OrderSide.BUY,
            OrderType.LIMIT,
            Decimal("100"),
            Decimal("1"),
            limit_price=Decimal("100"),
        ),
    )
    assert any("target amount is missing" in w for w in e.warnings)
    assert any("valuation is unavailable" in w for w in e.warnings)


def test_rejects_non_positive_share_count():
    p = make_portfolio(cash_balances=(CashBalance("USD", Decimal("1000")),))
    s = generate_snapshot(p)
    buy_eval = evaluate_proposed_order(
        p,
        s,
        ProposedOrder(
            "NVDA",
            OrderSide.BUY,
            OrderType.LIMIT,
            Decimal("100"),
            Decimal("0"),
            limit_price=Decimal("100"),
        ),
    )
    sell_eval = evaluate_proposed_order(
        p,
        s,
        ProposedOrder(
            "NVDA",
            OrderSide.SELL,
            OrderType.LIMIT,
            Decimal("100"),
            Decimal("-1"),
            limit_price=Decimal("100"),
        ),
    )

    assert not buy_eval.valid
    assert "share_count must be greater than zero when provided." in buy_eval.errors
    assert not sell_eval.valid
    assert "share_count must be greater than zero when provided." in sell_eval.errors


def test_rejects_non_positive_entry_price():
    p = make_portfolio(cash_balances=(CashBalance("USD", Decimal("1000")),))
    s = generate_snapshot(p)
    zero_eval = evaluate_proposed_order(
        p,
        s,
        ProposedOrder(
            "NVDA",
            OrderSide.BUY,
            OrderType.LIMIT,
            Decimal("0"),
            Decimal("1"),
            limit_price=Decimal("0"),
        ),
    )
    negative_eval = evaluate_proposed_order(
        p,
        s,
        ProposedOrder(
            "NVDA",
            OrderSide.BUY,
            OrderType.LIMIT,
            Decimal("-10"),
            Decimal("1"),
            limit_price=Decimal("-10"),
        ),
    )

    assert not zero_eval.valid
    assert "entry_price must be greater than zero." in zero_eval.errors
    assert not negative_eval.valid
    assert "entry_price must be greater than zero." in negative_eval.errors
