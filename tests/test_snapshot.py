from decimal import Decimal

from finwall.models import (
    ActiveOrder,
    CashBalance,
    Holding,
    OrderSide,
    OrderType,
    Portfolio,
)
from finwall.snapshot import generate_snapshot


def test_generate_snapshot_with_prices() -> None:
    portfolio = Portfolio(
        name="Primary",
        cash_balances=(CashBalance("USD", Decimal("500")),),
        holdings=(
            Holding("NVDA", Decimal("2"), Decimal("100")),
            Holding("PLTR", Decimal("1"), Decimal("10")),
        ),
        active_orders=(
            ActiveOrder(
                "NVDA",
                OrderSide.BUY,
                OrderType.LIMIT,
                Decimal("1"),
                limit_price=Decimal("90"),
            ),
            ActiveOrder(
                "PLTR",
                OrderSide.SELL,
                OrderType.STOP_LIMIT,
                Decimal("2"),
                limit_price=Decimal("11"),
                stop_price=Decimal("10.5"),
            ),
        ),
    )

    snapshot = generate_snapshot(
        portfolio,
        latest_prices={"NVDA": Decimal("120"), "PLTR": Decimal("12")},
    )

    assert snapshot.cash_balance == "USD 500.00"
    assert snapshot.cash_balances == {"USD": "500.00"}
    assert snapshot.invested_value == "252.00"
    assert snapshot.total_portfolio_value == "752.00"
    assert snapshot.cash_allocation_percent == "66.49"
    assert snapshot.invested_allocation_percent == "33.51"
    assert snapshot.total_unrealized_gain_loss == "42.00"
    assert snapshot.total_unrealized_gain_loss_percent == "20.00"
    assert snapshot.price_completeness_status == "complete"

    holding = snapshot.holdings[0]
    assert holding.current_price == "120.00"
    assert holding.estimated_value == "240.00"
    assert holding.unrealized_gain_loss == "40.00"
    assert holding.price_available is True
    assert holding.price_status == "available"
    assert holding.allocation_in_invested_percent == "95.24"
    assert holding.allocation_in_total_percent == "31.91"

    assert (
        snapshot.active_orders[0].description
        == "NVDA buy limit shares=1.00 limit=90.00"
    )
    assert snapshot.active_orders[1].stop_price == "10.50"


def test_generate_snapshot_without_prices() -> None:
    portfolio = Portfolio(
        name="Primary",
        holdings=(Holding("PLTR", Decimal("1"), Decimal("100")),),
    )

    snapshot = generate_snapshot(portfolio)

    holding = snapshot.holdings[0]
    assert holding.current_price is None
    assert holding.estimated_value is None
    assert holding.unrealized_gain_loss is None
    assert holding.price_available is False
    assert holding.price_status == "missing"
    assert holding.missing_price_message is not None
    assert snapshot.price_completeness_status == "missing"


def test_snapshot_json_export() -> None:
    portfolio = Portfolio(
        name="Primary",
        cash_balances=(CashBalance("USD", Decimal("100")),),
        active_orders=(
            ActiveOrder(
                "NVDA",
                OrderSide.BUY,
                OrderType.LIMIT,
                Decimal("1"),
                limit_price=Decimal("95"),
            ),
        ),
    )

    snapshot = generate_snapshot(portfolio)
    payload = snapshot.to_json()

    assert '"cash_balance": "USD 100.00"' in payload
    assert '"total_portfolio_value": "100.00"' in payload
    assert '"active_orders": [' in payload
    assert '"limit_price": "95.00"' in payload


def test_multi_currency_cash_does_not_sum_raw_amounts() -> None:
    portfolio = Portfolio(
        name="Primary",
        cash_balances=(
            CashBalance("USD", Decimal("100")),
            CashBalance("EUR", Decimal("100")),
        ),
    )

    snapshot = generate_snapshot(portfolio)

    assert snapshot.cash_balance == "EUR 100.00, USD 100.00"
    assert snapshot.total_portfolio_value is None
    assert snapshot.cash_allocation_percent is None
    assert snapshot.invested_allocation_percent is None
    assert snapshot.multi_currency_cash is True
    assert snapshot.valuation_status == "multi_currency_cash_unsupported"


def test_price_matching_is_case_insensitive() -> None:
    portfolio = Portfolio(
        name="Primary",
        holdings=(Holding("nvda", Decimal("1"), Decimal("100")),),
    )

    snapshot = generate_snapshot(
        portfolio,
        latest_prices={"NVDA": Decimal("120")},
    )

    holding = snapshot.holdings[0]
    assert holding.current_price == "120.00"
    assert holding.price_available is True
