from datetime import date
from decimal import Decimal

import pytest

from finwall.models import (
    ActiveOrder,
    CashBalance,
    Holding,
    InvestmentGoal,
    OrderSide,
    OrderType,
    Portfolio,
    RiskLevel,
    RiskProfile,
    Timeline,
    TradeSide,
    TradeTransaction,
    WatchlistItem,
)
from finwall.storage import SQLitePortfolioStore


@pytest.fixture
def store(tmp_path):
    database_path = tmp_path / "finwall.db"
    storage = SQLitePortfolioStore(database_path)
    storage.initialize()
    return storage


def build_portfolio() -> Portfolio:
    return Portfolio(
        name="Primary",
        cash_balances=(CashBalance(currency="USD", amount=Decimal("5000")),),
        holdings=(
            Holding(
                ticker="AAPL",
                share_count=Decimal("10"),
                average_purchase_price=Decimal("180"),
                sector="Technology",
            ),
        ),
        transactions=(
            TradeTransaction(
                ticker="AAPL",
                side=TradeSide.BUY,
                share_count=Decimal("10"),
                price=Decimal("180"),
                traded_on=date(2026, 1, 10),
            ),
        ),
        active_orders=(
            ActiveOrder(
                ticker="NVDA",
                side=OrderSide.BUY,
                order_type=OrderType.LIMIT,
                share_count=Decimal("2"),
                limit_price=Decimal("950"),
            ),
        ),
        watchlist=(WatchlistItem(ticker="MSFT", note="Cloud exposure"),),
        goals=(
            InvestmentGoal(
                name="Retirement",
                target_amount=Decimal("1000000"),
                timeline=Timeline(
                    start_date=date(2026, 1, 1),
                    target_date=date(2045, 1, 1),
                ),
            ),
        ),
        risk_profile=RiskProfile(level=RiskLevel.MODERATE),
    )


def test_initialize_creates_database(store, tmp_path) -> None:
    assert (tmp_path / "finwall.db").exists()


def test_save_and_read_portfolio(store) -> None:
    portfolio = build_portfolio()

    store.save_portfolio(portfolio)

    loaded = store.get_portfolio("Primary")

    assert loaded == portfolio


def test_update_existing_portfolio(store) -> None:
    store.save_portfolio(build_portfolio())

    updated = Portfolio(
        name="Primary",
        cash_balances=(CashBalance(currency="USD", amount=Decimal("8000")),),
    )

    store.save_portfolio(updated)

    loaded = store.get_portfolio("Primary")

    assert loaded is not None
    assert loaded.cash_balances[0].amount == Decimal("8000")
    assert loaded.holdings == ()


def test_delete_portfolio(store) -> None:
    store.save_portfolio(build_portfolio())

    store.delete_portfolio("Primary")

    assert store.get_portfolio("Primary") is None


def test_trade_history_is_stored_separately(store) -> None:
    portfolio = Portfolio(name="Primary")
    transaction = TradeTransaction(
        ticker="META",
        side=TradeSide.BUY,
        share_count=Decimal("3"),
        price=Decimal("400"),
        traded_on=date(2026, 2, 1),
    )

    store.save_portfolio(portfolio)
    store.add_trade_transaction("Primary", transaction)

    transactions = store.list_trade_transactions("Primary")

    assert transactions == (transaction,)


def test_trade_history_survives_portfolio_state_updates(store) -> None:
    store.save_portfolio(Portfolio(name="Primary"))

    transaction = TradeTransaction(
        ticker="AMD",
        side=TradeSide.BUY,
        share_count=Decimal("5"),
        price=Decimal("120"),
        traded_on=date(2026, 4, 1),
    )

    store.add_trade_transaction("Primary", transaction)

    updated = Portfolio(
        name="Primary",
        holdings=(
            Holding(
                ticker="AMD",
                share_count=Decimal("5"),
                average_purchase_price=Decimal("120"),
            ),
        ),
    )

    store.save_portfolio(updated)

    assert store.list_trade_transactions("Primary") == (transaction,)


def test_cash_history_is_stored_separately(store) -> None:
    portfolio = Portfolio(name="Primary")
    cash_balance = CashBalance(currency="USD", amount=Decimal("1200"))

    store.save_portfolio(portfolio)
    store.record_cash_history("Primary", cash_balance, date(2026, 3, 1))

    history = store.list_cash_history("Primary")

    assert history == ((cash_balance, date(2026, 3, 1)),)


def test_invalid_portfolio_state_is_rejected(store) -> None:
    with pytest.raises(ValueError):
        store.save_portfolio("invalid")
