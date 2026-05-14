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
        ),
        active_orders=(
            ActiveOrder(
                "NVDA",
                OrderSide.BUY,
                OrderType.LIMIT,
                Decimal("1"),
                limit_price=Decimal("90"),
            ),
        ),
    )

    snapshot = generate_snapshot(
        portfolio,
        latest_prices={"NVDA": Decimal("120")},
    )

    assert snapshot.cash_balance == "USD 500.00"
    assert snapshot.cash_balances == {"USD": "500.00"}
    assert snapshot.invested_value == "240.00"
    assert snapshot.total_portfolio_value == "740.00"
    assert snapshot.cash_allocation_percent == "67.57"
    assert snapshot.invested_allocation_percent == "32.43"

    holding = snapshot.holdings[0]
    assert holding.current_price == "120.00"
    assert holding.estimated_value == "240.00"
    assert holding.unrealized_gain_loss == "40.00"
    assert holding.price_available is True

    assert snapshot.active_orders[0] == "NVDA buy limit shares=1.00"


def test_generate_snapshot_without_prices() -> None:
    portfolio = Portfolio(
        name="Primary",
        holdings=(
            Holding("PLTR", Decimal("1"), Decimal("100")),
        ),
    )

    snapshot = generate_snapshot(portfolio)

    holding = snapshot.holdings[0]
    assert holding.current_price is None
    assert holding.estimated_value is None
    assert holding.unrealized_gain_loss is None
    assert holding.price_available is False


def test_snapshot_json_export() -> None:
    portfolio = Portfolio(
        name="Primary",
        cash_balances=(CashBalance("USD", Decimal("100")),),
    )

    snapshot = generate_snapshot(portfolio)
    payload = snapshot.to_json()

    assert '"cash_balance": "USD 100.00"' in payload
    assert '"total_portfolio_value": "100.00"' in payload



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



def test_price_matching_is_case_insensitive() -> None:
    portfolio = Portfolio(
        name="Primary",
        holdings=(
            Holding("nvda", Decimal("1"), Decimal("100")),
        ),
    )

    snapshot = generate_snapshot(
        portfolio,
        latest_prices={"NVDA": Decimal("120")},
    )

    holding = snapshot.holdings[0]
    assert holding.current_price == "120.00"
    assert holding.price_available is True
