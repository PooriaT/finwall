from decimal import Decimal

import pytest

from finwall.cli import run
from finwall.storage import SQLitePortfolioStore


def test_record_buy_updates_cash_and_holdings(tmp_path) -> None:
    database = tmp_path / "finwall.db"

    run(
        [
            "--database",
            str(database),
            "add-cash",
            "USD",
            "1000",
        ]
    )

    run(
        [
            "--database",
            str(database),
            "record-buy",
            "NVDA",
            "2",
            "100",
            "--currency",
            "USD",
            "--date",
            "2026-05-13",
        ]
    )

    store = SQLitePortfolioStore(database)
    portfolio = store.get_portfolio("Primary")

    assert portfolio is not None
    assert portfolio.cash_balances[0].amount == Decimal("800")
    assert portfolio.holdings[0].ticker == "NVDA"
    assert portfolio.holdings[0].share_count == Decimal("2")
    assert portfolio.transactions[0].ticker == "NVDA"


def test_record_sell_rejects_excess_shares(tmp_path) -> None:
    database = tmp_path / "finwall.db"

    run(
        [
            "--database",
            str(database),
            "add-holding",
            "AAPL",
            "1",
            "150",
        ]
    )

    with pytest.raises(ValueError, match="cannot sell more shares than available"):
        run(
            [
                "--database",
                str(database),
                "record-sell",
                "AAPL",
                "2",
                "200",
            ]
        )


def test_order_update_and_remove(tmp_path) -> None:
    database = tmp_path / "finwall.db"

    run(
        [
            "--database",
            str(database),
            "add-order",
            "PLTR",
            "buy",
            "limit",
            "2",
            "--limit-price",
            "120",
        ]
    )

    run(
        [
            "--database",
            str(database),
            "update-order",
            "PLTR",
            "buy",
            "limit",
            "3",
            "--limit-price",
            "125",
        ]
    )

    run(
        [
            "--database",
            str(database),
            "remove-order",
            "PLTR",
        ]
    )

    store = SQLitePortfolioStore(database)
    portfolio = store.get_portfolio("Primary")

    assert portfolio is not None
    assert portfolio.active_orders == ()


def test_set_risk_profile(tmp_path) -> None:
    database = tmp_path / "finwall.db"

    run(
        [
            "--database",
            str(database),
            "set-risk",
            "moderate",
            "--notes",
            "Long-term growth",
        ]
    )

    store = SQLitePortfolioStore(database)
    portfolio = store.get_portfolio("Primary")

    assert portfolio is not None
    assert portfolio.risk_profile is not None
    assert portfolio.risk_profile.level.value == "moderate"
