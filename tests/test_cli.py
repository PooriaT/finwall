from decimal import Decimal

import pytest

from finwall.cli import run
from finwall.market_data import IndexQuote, MarketPrice, StaticMarketDataProvider
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


def test_snapshot_live_prices_with_manual_override(
    tmp_path, monkeypatch, capsys
) -> None:
    database = tmp_path / "finwall.db"

    run(["--database", str(database), "add-holding", "NVDA", "2", "100"])
    run(["--database", str(database), "add-holding", "PLTR", "1", "10"])

    provider = StaticMarketDataProvider(
        prices={
            "NVDA": MarketPrice("NVDA", Decimal("120"), "USD", "static", True),
            "PLTR": MarketPrice("PLTR", None, "USD", "static", False, "provider down"),
        }
    )

    monkeypatch.setattr("finwall.cli.build_market_data_provider", lambda *_: provider)

    run(
        [
            "--database",
            str(database),
            "snapshot",
            "--live-prices",
            "--price",
            "NVDA=130",
            "--json",
        ]
    )

    out = capsys.readouterr().out
    assert "Warning: unable to fetch price for PLTR: provider down" in out
    assert '"ticker": "NVDA"' in out
    assert '"current_price": "130.00"' in out


def test_market_index_command_with_mock_provider(tmp_path, monkeypatch, capsys) -> None:
    database = tmp_path / "finwall.db"
    provider = StaticMarketDataProvider(
        index_quotes={
            "SP500": IndexQuote("SP500", Decimal("5050.50"), "static", True),
        }
    )
    monkeypatch.setattr("finwall.cli.build_market_data_provider", lambda *_: provider)

    exit_code = run(["--database", str(database), "market-index", "SP500"])

    assert exit_code == 0
    assert "SP500: 5050.50 (static)" in capsys.readouterr().out


def test_snapshot_with_risk_output(tmp_path, capsys) -> None:
    database = tmp_path / "finwall.db"
    run(["--database", str(database), "add-cash", "USD", "10"])
    run(["--database", str(database), "add-holding", "NVDA", "1", "100"])

    run(["--database", str(database), "snapshot", "--price", "NVDA=100", "--risk"])

    out = capsys.readouterr().out
    assert "Risk profile:" in out
    assert "Risk warnings:" in out


def test_snapshot_json_includes_risk_assessment(tmp_path, capsys) -> None:
    database = tmp_path / "finwall.db"
    run(["--database", str(database), "add-holding", "NVDA", "1", "100"])

    run(
        [
            "--database",
            str(database),
            "snapshot",
            "--price",
            "NVDA=100",
            "--risk",
            "--json",
        ]
    )

    out = capsys.readouterr().out
    assert '"risk_assessment": {' in out
    assert '"warnings": [' in out


def test_evaluate_order_text_output(tmp_path, capsys) -> None:
    database = tmp_path / "finwall.db"
    run(["--database", str(database), "add-cash", "USD", "1000"])
    run(
        [
            "--database",
            str(database),
            "evaluate-order",
            "NVDA",
            "buy",
            "limit",
            "--entry-price",
            "100",
            "--shares",
            "2",
            "--limit-price",
            "100",
            "--stop-price",
            "90",
            "--target-price",
            "120",
        ]
    )
    out = capsys.readouterr().out
    assert "Proposed order:" in out
    assert "This is an evaluation of the provided order, not a recommendation." in out


def test_evaluate_order_json_output(tmp_path, capsys) -> None:
    database = tmp_path / "finwall.db"
    run(["--database", str(database), "add-cash", "USD", "1000"])
    run(
        [
            "--database",
            str(database),
            "evaluate-order",
            "NVDA",
            "buy",
            "limit",
            "--entry-price",
            "100",
            "--shares",
            "2",
            "--limit-price",
            "100",
            "--json",
        ]
    )
    out = capsys.readouterr().out
    assert '"ticker": "NVDA"' in out
    assert '"warnings": [' in out
