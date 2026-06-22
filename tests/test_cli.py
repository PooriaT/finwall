import importlib
import json
import sqlite3
from decimal import Decimal

import pytest

from finwall.cli import run
from finwall.market_data import (
    HistoricalPriceBar,
    IndexQuote,
    MarketPrice,
    StaticMarketDataProvider,
)
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
    import finwall.config as config_module

    database = tmp_path / "finwall.db"

    run(["--database", str(database), "add-holding", "NVDA", "2", "100"])
    run(["--database", str(database), "add-holding", "PLTR", "1", "10"])

    provider = StaticMarketDataProvider(
        prices={
            "NVDA": MarketPrice("NVDA", Decimal("120"), "USD", "static", True),
            "PLTR": MarketPrice("PLTR", None, "USD", "static", False, "provider down"),
        }
    )

    provider_args = {}

    def fake_build_provider(provider_name, timeout_seconds):
        provider_args["provider_name"] = provider_name
        provider_args["timeout_seconds"] = timeout_seconds
        return provider

    monkeypatch.delenv("FINWALL_MARKET_DATA_PROVIDER", raising=False)
    monkeypatch.delenv("FINWALL_MARKET_DATA_TIMEOUT_SECONDS", raising=False)
    reloaded_config = importlib.reload(config_module)
    monkeypatch.setattr("finwall.cli.settings", reloaded_config.Settings())
    monkeypatch.setattr("finwall.cli.build_market_data_provider", fake_build_provider)

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
    assert provider_args == {
        "provider_name": "yfinance",
        "timeout_seconds": 5.0,
    }


def test_live_price_help_describes_default_provider(capsys) -> None:
    with pytest.raises(SystemExit) as exc_info:
        run(["snapshot", "--help"])
    assert exc_info.value.code == 0
    snapshot_help = capsys.readouterr().out
    assert "Fetch prices from the default live provider unless" in snapshot_help
    assert "overridden." in snapshot_help

    with pytest.raises(SystemExit) as exc_info:
        run(["report", "--help"])
    assert exc_info.value.code == 0
    report_help = capsys.readouterr().out
    assert "Use configured/default live provider" in report_help
    assert "manual --price" in report_help
    assert "overrides fetched values" in report_help

    with pytest.raises(SystemExit) as exc_info:
        run(["market-data-check", "--help"])
    assert exc_info.value.code == 0
    diagnostics_help = capsys.readouterr().out
    assert "Check default or overridden market-data provider." in diagnostics_help


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


def test_recommendations_text_output(tmp_path, capsys) -> None:
    database = tmp_path / "finwall.db"
    run(["--database", str(database), "add-holding", "NVDA", "1", "100"])

    run(["--database", str(database), "recommendations", "--price", "NVDA=120"])

    out = capsys.readouterr().out
    assert "Deterministic recommendations" in out
    assert "Holding: NVDA" in out


def test_recommendations_json_output(tmp_path, capsys) -> None:
    database = tmp_path / "finwall.db"
    run(["--database", str(database), "add-holding", "NVDA", "1", "100"])

    run(
        [
            "--database",
            str(database),
            "recommendations",
            "--price",
            "NVDA=120",
            "--json",
        ]
    )

    out = capsys.readouterr().out
    assert '"holdings": [' in out
    assert '"cash_deployment": {' in out


def test_recommendations_live_prices(tmp_path, monkeypatch, capsys) -> None:
    database = tmp_path / "finwall.db"
    run(["--database", str(database), "add-holding", "NVDA", "1", "100"])

    provider = StaticMarketDataProvider(
        prices={
            "NVDA": MarketPrice("NVDA", Decimal("120"), "USD", "static", True),
        }
    )
    monkeypatch.setattr("finwall.cli.build_market_data_provider", lambda *_: provider)

    run(["--database", str(database), "recommendations", "--live-prices", "--json"])

    out = capsys.readouterr().out
    assert '"ticker": "NVDA"' in out


def test_recommendations_missing_prices_and_empty_portfolio(tmp_path, capsys) -> None:
    database = tmp_path / "finwall.db"
    run(["--database", str(database), "add-holding", "NVDA", "1", "100"])
    run(["--database", str(database), "recommendations"])
    out = capsys.readouterr().out
    assert "Holding: NVDA" in out

    empty_db = tmp_path / "empty.db"
    run(["--database", str(empty_db), "recommendations"])
    out2 = capsys.readouterr().out
    assert "Holdings: none" in out2


def test_fundamentals_summary_text_output(tmp_path, capsys) -> None:
    database = tmp_path / "finwall.db"
    run(["--database", str(database), "add-holding", "NVDA", "1", "100"])
    run(["--database", str(database), "add-watchlist", "AAPL"])
    run(["--database", str(database), "fundamentals-summary"])
    out = capsys.readouterr().out
    assert "Fundamental summaries" in out
    assert "risk_level=" in out
    assert "Limitations:" in out


def test_fundamentals_summary_json_and_empty_portfolio(tmp_path, capsys) -> None:
    database = tmp_path / "empty.db"
    run(["--database", str(database), "fundamentals-summary", "--json"])
    out = capsys.readouterr().out
    assert '"holdings": []' in out
    assert '"watchlist": []' in out


def test_report_prints_markdown_by_default(tmp_path, capsys) -> None:
    database = tmp_path / "finwall.db"
    run(["--database", str(database), "add-holding", "NVDA", "1", "100"])
    run(["--database", str(database), "report", "--price", "NVDA=120"])
    out = capsys.readouterr().out
    assert "# Finwall Decision-Support Report" in out


def test_report_json_output(tmp_path, capsys) -> None:
    database = tmp_path / "finwall.db"
    run(["--database", str(database), "add-holding", "NVDA", "1", "100"])
    run(["--database", str(database), "report", "--price", "NVDA=120", "--json"])
    out = capsys.readouterr().out
    assert '"portfolio_snapshot": {' in out
    assert '"holding_recommendations": [' in out


def test_report_live_prices_and_market_index(tmp_path, monkeypatch, capsys) -> None:
    import finwall.config as config_module

    database = tmp_path / "finwall.db"
    run(["--database", str(database), "add-holding", "NVDA", "1", "100"])
    provider = StaticMarketDataProvider(
        prices={"NVDA": MarketPrice("NVDA", Decimal("120"), "USD", "static", True)},
        index_quotes={"SP500": IndexQuote("SP500", Decimal("5050.50"), "static", True)},
    )
    provider_args = {}

    def fake_build_provider(provider_name, timeout_seconds):
        provider_args["provider_name"] = provider_name
        provider_args["timeout_seconds"] = timeout_seconds
        return provider

    monkeypatch.delenv("FINWALL_MARKET_DATA_PROVIDER", raising=False)
    monkeypatch.delenv("FINWALL_MARKET_DATA_TIMEOUT_SECONDS", raising=False)
    reloaded_config = importlib.reload(config_module)
    monkeypatch.setattr("finwall.cli.settings", reloaded_config.Settings())
    monkeypatch.setattr(
        "finwall.report_pipeline.build_market_data_provider",
        fake_build_provider,
    )
    run(
        [
            "--database",
            str(database),
            "report",
            "--live-prices",
            "--market-index",
            "SP500",
            "--json",
        ]
    )
    out = capsys.readouterr().out
    assert '"status": "insufficient_data"' in out
    assert provider_args == {
        "provider_name": "yfinance",
        "timeout_seconds": 5.0,
    }


def test_report_market_condition_uses_extended_lookback(tmp_path, monkeypatch) -> None:
    database = tmp_path / "finwall.db"
    run(["--database", str(database), "add-holding", "NVDA", "1", "100"])

    provider = StaticMarketDataProvider(
        prices={"NVDA": MarketPrice("NVDA", Decimal("120"), "USD", "static", True)},
        index_quotes={"SP500": IndexQuote("SP500", Decimal("5050.50"), "static", True)},
    )
    monkeypatch.setattr("finwall.cli.build_market_data_provider", lambda *_: provider)

    seen = {}
    from finwall import cli as cli_module

    original = cli_module.classify_market_condition

    def fake_classify_market_condition(
        *, provider, primary_symbol, include_nasdaq, days
    ):
        seen["days"] = days
        return original(
            provider=provider,
            primary_symbol=primary_symbol,
            include_nasdaq=include_nasdaq,
            days=days,
        )

    monkeypatch.setattr(
        "finwall.report_pipeline.classify_market_condition",
        fake_classify_market_condition,
    )

    run(
        [
            "--database",
            str(database),
            "report",
            "--live-prices",
            "--market-index",
            "SP500",
        ]
    )

    assert seen["days"] == 400


def test_report_handles_empty_portfolio(tmp_path, capsys) -> None:
    database = tmp_path / "finwall.db"
    run(["--database", str(database), "report"])
    out = capsys.readouterr().out
    assert "# Finwall Decision-Support Report" in out


def test_technicals_text_output(tmp_path, monkeypatch, capsys) -> None:
    database = tmp_path / "finwall.db"
    run(["--database", str(database), "add-holding", "NVDA", "1", "100"])
    run(["--database", str(database), "add-watchlist", "MSFT"])

    from finwall.market_data import HistoricalPriceBar

    provider = StaticMarketDataProvider(
        historical_prices={
            "NVDA": tuple(
                HistoricalPriceBar(
                    "NVDA",
                    f"2025-01-{day:02d}",
                    Decimal("100") + day,
                    1000 + day,
                    "static",
                )
                for day in range(1, 29)
            ),
            "MSFT": (),
        }
    )
    monkeypatch.setattr("finwall.cli.build_market_data_provider", lambda *_: provider)

    run(["--database", str(database), "technicals"])
    out = capsys.readouterr().out
    assert "Holdings:" in out
    assert "Watchlist:" in out
    assert "NVDA" in out


def test_technicals_json_and_filters(tmp_path, monkeypatch, capsys) -> None:
    database = tmp_path / "finwall.db"
    run(["--database", str(database), "add-holding", "NVDA", "1", "100"])
    run(["--database", str(database), "add-watchlist", "MSFT"])

    from finwall.market_data import HistoricalPriceBar

    provider = StaticMarketDataProvider(
        historical_prices={
            "NVDA": (
                HistoricalPriceBar(
                    "NVDA", "2025-01-01", Decimal("100"), 1000, "static"
                ),
            ),
            "MSFT": (
                HistoricalPriceBar(
                    "MSFT", "2025-01-01", Decimal("200"), None, "static"
                ),
            ),
        }
    )
    monkeypatch.setattr("finwall.cli.build_market_data_provider", lambda *_: provider)

    run(["--database", str(database), "technicals", "--json", "--holdings-only"])
    out = capsys.readouterr().out
    assert '"holdings": [' in out

    run(["--database", str(database), "technicals", "--json", "--watchlist-only"])
    out = capsys.readouterr().out
    assert '"watchlist": [' in out


def test_fundamentals_text_output(tmp_path, capsys) -> None:
    database = tmp_path / "finwall.db"
    run(["--database", str(database), "add-holding", "NVDA", "1", "100"])
    run(["--database", str(database), "add-watchlist", "AAPL"])

    run(["--database", str(database), "fundamentals"])
    out = capsys.readouterr().out
    assert "Holdings:" in out
    assert "Watchlist:" in out


def test_fundamentals_json_and_filters(tmp_path, capsys) -> None:
    database = tmp_path / "finwall.db"
    run(["--database", str(database), "add-watchlist", "AAPL"])
    run(["--database", str(database), "fundamentals", "--json"])
    assert '"watchlist": [' in capsys.readouterr().out

    run(["--database", str(database), "fundamentals", "--holdings-only"])
    out = capsys.readouterr().out
    assert "Watchlist:" not in out

    run(["--database", str(database), "fundamentals", "--watchlist-only"])
    out = capsys.readouterr().out
    assert "Holdings:" not in out


def test_news_text_and_json_and_filters(tmp_path, monkeypatch, capsys) -> None:
    from finwall.news import (
        NewsArticle,
        NewsProviderResult,
        NewsTopicType,
        StaticNewsDataProvider,
    )

    database = tmp_path / "finwall.db"
    run(
        [
            "--database",
            str(database),
            "add-holding",
            "NVDA",
            "1",
            "100",
            "--sector",
            "Technology",
        ]
    )
    run(["--database", str(database), "add-watchlist", "AAPL"])

    provider = StaticNewsDataProvider(
        company_news={
            "NVDA": NewsProviderResult(
                NewsTopicType.TICKER,
                "NVDA",
                (
                    NewsArticle(
                        "H",
                        "Reuters",
                        "u",
                        None,
                        NewsTopicType.TICKER,
                        "NVDA",
                        "NVDA",
                        None,
                    ),
                ),
                "static",
                True,
            ),
            "AAPL": NewsProviderResult(
                NewsTopicType.TICKER, "AAPL", (), "static", False, "none"
            ),
        },
        market_news={
            "market": NewsProviderResult(
                NewsTopicType.MARKET, "market", (), "static", True
            )
        },
        sector_news={
            "technology": NewsProviderResult(
                NewsTopicType.SECTOR, "Technology", (), "static", True
            )
        },
    )
    monkeypatch.setattr("finwall.cli.build_news_data_provider", lambda *_: provider)

    run(["--database", str(database), "news", "--include-market", "--include-sectors"])
    out = capsys.readouterr().out
    assert "Holdings:" in out
    assert "Watchlist:" in out

    run(["--database", str(database), "news", "--json"])
    out = capsys.readouterr().out
    assert '"holdings"' in out

    run(["--database", str(database), "news", "--holdings-only"])
    out = capsys.readouterr().out
    assert "Watchlist:" not in out

    run(["--database", str(database), "news", "--watchlist-only"])
    out = capsys.readouterr().out
    assert "Holdings:" not in out


def test_news_empty_portfolio_and_unavailable_provider(
    tmp_path, monkeypatch, capsys
) -> None:
    from finwall.news import StaticNewsDataProvider

    database = tmp_path / "finwall.db"
    monkeypatch.setattr(
        "finwall.cli.build_news_data_provider", lambda *_: StaticNewsDataProvider()
    )
    run(["--database", str(database), "news"])
    assert "News topics:" in capsys.readouterr().out


def test_news_summary_text_json_and_filters(tmp_path, monkeypatch, capsys) -> None:
    from finwall.news import (
        NewsArticle,
        NewsProviderResult,
        NewsTopicType,
        StaticNewsDataProvider,
    )

    database = tmp_path / "finwall.db"
    run(
        [
            "--database",
            str(database),
            "add-holding",
            "NVDA",
            "1",
            "100",
            "--sector",
            "Technology",
        ]
    )
    run(["--database", str(database), "add-watchlist", "AAPL"])
    provider = StaticNewsDataProvider(
        company_news={
            "NVDA": NewsProviderResult(
                NewsTopicType.TICKER,
                "NVDA",
                (
                    NewsArticle(
                        "NVDA reports earnings",
                        "Reuters",
                        "u",
                        None,
                        NewsTopicType.TICKER,
                        "NVDA",
                        "NVDA",
                        None,
                    ),
                ),
                "static",
                True,
            ),
            "AAPL": NewsProviderResult(
                NewsTopicType.TICKER, "AAPL", (), "static", False, "none"
            ),
        }
    )
    monkeypatch.setattr("finwall.cli.build_news_data_provider", lambda *_: provider)
    run(["--database", str(database), "news-summary"])
    assert "Confirmed facts" in capsys.readouterr().out
    run(["--database", str(database), "news-summary", "--json"])
    assert '"holdings"' in capsys.readouterr().out
    run(["--database", str(database), "news-summary", "--holdings-only"])
    assert "Watchlist:" not in capsys.readouterr().out
    run(["--database", str(database), "news-summary", "--watchlist-only"])
    assert "Holdings:" not in capsys.readouterr().out


def test_news_summary_warns_on_unsupported_provider(
    tmp_path, monkeypatch, capsys
) -> None:
    from dataclasses import replace

    from finwall.cli import settings
    from finwall.news import StaticNewsDataProvider

    database = tmp_path / "finwall.db"
    monkeypatch.setattr(
        "finwall.cli.build_news_data_provider", lambda *_: StaticNewsDataProvider()
    )
    monkeypatch.setattr(
        "finwall.cli.settings",
        replace(settings, news_provider="custom-provider"),
    )

    run(["--database", str(database), "news-summary"])
    out = capsys.readouterr().out
    assert "unsupported news provider 'custom-provider'" in out

    run(["--database", str(database), "news-summary", "--json"])
    out = capsys.readouterr().out
    assert "unsupported news provider 'custom-provider'" in out


def test_report_json_shape_stable_with_optional_narrative(tmp_path, capsys) -> None:
    database = tmp_path / "finwall.db"
    run(["--database", str(database), "add-holding", "NVDA", "1", "100"])

    run(["--database", str(database), "report", "--price", "NVDA=120", "--json"])
    base = json.loads(capsys.readouterr().out)

    run(
        [
            "--database",
            str(database),
            "report",
            "--price",
            "NVDA=120",
            "--narrative",
            "--json",
        ]
    )
    with_narrative = json.loads(capsys.readouterr().out)

    assert "narrative" in with_narrative
    assert set(base.keys()) == set(with_narrative.keys()) - {"narrative"}


def test_report_narrative_fallback_preserves_recommendation_statuses(
    tmp_path, monkeypatch, capsys
) -> None:
    database = tmp_path / "finwall.db"
    run(["--database", str(database), "add-holding", "NVDA", "1", "100"])

    run(["--database", str(database), "report", "--price", "NVDA=120", "--json"])
    deterministic = json.loads(capsys.readouterr().out)

    monkeypatch.setenv("FINWALL_NARRATIVE_PROVIDER", "disabled")
    run(
        [
            "--database",
            str(database),
            "report",
            "--price",
            "NVDA=120",
            "--narrative",
            "--json",
        ]
    )
    with_narrative = json.loads(capsys.readouterr().out)

    assert (
        with_narrative["holding_recommendations"]
        == deterministic["holding_recommendations"]
    )


def test_report_narrative_markdown_and_json(tmp_path, monkeypatch, capsys) -> None:
    database = tmp_path / "finwall.db"
    run(["--database", str(database), "add-holding", "NVDA", "1", "100"])

    run(["--database", str(database), "report", "--price", "NVDA=120", "--narrative"])
    out = capsys.readouterr().out
    assert "## Narrative Summary" in out

    run(
        [
            "--database",
            str(database),
            "report",
            "--price",
            "NVDA=120",
            "--narrative",
            "--json",
        ]
    )
    out = capsys.readouterr().out
    assert '"narrative": {' in out


def test_report_narrative_uses_fallback_on_invalid_provider_response(
    tmp_path, monkeypatch, capsys
) -> None:
    from finwall.narrative import NarrativeResponse, NarrativeSection

    database = tmp_path / "finwall.db"
    run(["--database", str(database), "add-holding", "NVDA", "1", "100"])

    monkeypatch.setattr(
        "finwall.cli.generate_narrative",
        lambda *args, **kwargs: NarrativeResponse(
            available=False,
            provider="fake",
            sections=(
                NarrativeSection(
                    section="portfolio_overview",
                    text="Fallback deterministic explanation.",
                    evidence_keys_used=("portfolio_snapshot",),
                ),
            ),
            warnings=("invalid provider payload",),
            fallback_used=True,
            error="invalid provider payload",
        ),
    )

    run(["--database", str(database), "report", "--price", "NVDA=120", "--narrative"])
    out = capsys.readouterr().out
    assert "Fallback deterministic explanation." in out
    assert "# Finwall Decision-Support Report" in out


def test_report_narrative_json_marks_fallback_used(
    tmp_path, monkeypatch, capsys
) -> None:
    from finwall.narrative import NarrativeResponse, NarrativeSection

    database = tmp_path / "finwall.db"
    run(["--database", str(database), "add-holding", "NVDA", "1", "100"])

    monkeypatch.setattr(
        "finwall.cli.generate_narrative",
        lambda *args, **kwargs: NarrativeResponse(
            available=False,
            provider="ollama",
            sections=(
                NarrativeSection(
                    section="portfolio_overview",
                    text="Fallback deterministic explanation.",
                    evidence_keys_used=("portfolio_snapshot",),
                ),
            ),
            warnings=("provider error: provider call failed",),
            fallback_used=True,
            error="provider error: provider call failed",
        ),
    )
    run(
        [
            "--database",
            str(database),
            "report",
            "--price",
            "NVDA=120",
            "--narrative",
            "--json",
        ]
    )
    payload = json.loads(capsys.readouterr().out)
    assert payload["narrative"]["fallback_used"] is True


def test_report_save_run_persists_history(tmp_path, capsys) -> None:
    database = tmp_path / "finwall.db"
    run(["--database", str(database), "add-holding", "NVDA", "1", "100"])

    run(["--database", str(database), "report", "--price", "NVDA=120", "--save-run"])

    out = capsys.readouterr().out
    assert "Saved report run id=" in out

    store = SQLitePortfolioStore(database)
    latest = store.get_latest_report_run("Primary")
    assert latest is not None
    assert latest.id is not None
    assert store.list_report_recommendation_statuses(latest.id)


def test_report_compare_without_save(tmp_path, capsys) -> None:
    database = tmp_path / "finwall.db"
    run(["--database", str(database), "add-holding", "NVDA", "1", "100"])
    run(["--database", str(database), "report", "--price", "NVDA=100", "--save-run"])
    capsys.readouterr()

    run(["--database", str(database), "report", "--price", "NVDA=105", "--compare"])

    out = capsys.readouterr().out
    assert "## Recommendation Changes" in out
    assert "Current run was not saved." in out


def test_report_save_run_compare_json(tmp_path, capsys) -> None:
    database = tmp_path / "finwall.db"
    run(["--database", str(database), "add-holding", "NVDA", "1", "100"])
    run(["--database", str(database), "report", "--price", "NVDA=100", "--save-run"])
    capsys.readouterr()

    run(
        [
            "--database",
            str(database),
            "report",
            "--price",
            "NVDA=95",
            "--save-run",
            "--compare",
            "--json",
        ]
    )
    out = capsys.readouterr().out
    assert '"portfolio_snapshot": {' in out
    assert '"saved_run": {' in out
    assert '"comparison": {' in out


def test_run_scheduled_report_skips_weekend(tmp_path, capsys) -> None:
    database = tmp_path / "finwall.db"
    run(
        [
            "--database",
            str(database),
            "run-scheduled-report",
            "--run-date",
            "2026-05-23",
        ]
    )
    out = capsys.readouterr().out
    assert "Skipped scheduled report" in out


def test_run_scheduled_report_force_generates(tmp_path, capsys) -> None:
    database = tmp_path / "finwall.db"
    run(["--database", str(database), "add-holding", "NVDA", "1", "100"])
    capsys.readouterr()
    run(
        [
            "--database",
            str(database),
            "run-scheduled-report",
            "--run-date",
            "2026-05-23",
            "--force",
            "--price",
            "NVDA=120",
        ]
    )
    out = capsys.readouterr().out
    assert "# Finwall Decision-Support Report" in out


def test_run_scheduled_report_json_save_compare(tmp_path, capsys) -> None:
    database = tmp_path / "finwall.db"
    run(["--database", str(database), "add-holding", "NVDA", "1", "100"])
    capsys.readouterr()
    run(
        [
            "--database",
            str(database),
            "run-scheduled-report",
            "--run-date",
            "2026-05-20",
            "--price",
            "NVDA=100",
            "--save-run",
            "--json",
        ]
    )
    first = capsys.readouterr().out
    assert '"status": "generated"' in first
    run(
        [
            "--database",
            str(database),
            "run-scheduled-report",
            "--run-date",
            "2026-05-21",
            "--price",
            "NVDA=105",
            "--save-run",
            "--compare",
            "--json",
        ]
    )
    out = capsys.readouterr().out
    assert '"status": "generated"' in out
    assert '"comparison": {' in out


def test_run_scheduled_report_json_keeps_stdout_as_json_with_live_price_warnings(
    tmp_path, monkeypatch, capsys
) -> None:
    database = tmp_path / "finwall.db"
    run(["--database", str(database), "add-holding", "NVDA", "1", "100"])
    capsys.readouterr()

    monkeypatch.setattr(
        "finwall.report_pipeline.fetch_portfolio_latest_prices",
        lambda *args, **kwargs: ({}, ("NVDA",)),
    )
    run(
        [
            "--database",
            str(database),
            "run-scheduled-report",
            "--run-date",
            "2026-05-20",
            "--live-prices",
            "--json",
        ]
    )

    out = capsys.readouterr().out
    payload = json.loads(out)
    assert payload["status"] == "generated"
    assert payload["warnings"] == ["unable to fetch price for NVDA"]


class _FakeEmailProvider:
    def __init__(self, result):
        self.result = result
        self.messages = []

    def send(self, message):
        self.messages.append(message)
        return self.result


def test_run_scheduled_report_email_success_notification(
    tmp_path, monkeypatch, capsys
) -> None:
    from finwall.email_notifications import EmailSendResult

    database = tmp_path / "finwall.db"
    run(["--database", str(database), "add-holding", "NVDA", "1", "100"])
    capsys.readouterr()
    fake = _FakeEmailProvider(
        EmailSendResult(attempted=True, sent=True, provider="smtp")
    )
    monkeypatch.setattr(
        "finwall.cli.build_email_provider", lambda *args, **kwargs: fake
    )

    run(
        [
            "--database",
            str(database),
            "run-scheduled-report",
            "--run-date",
            "2026-05-20",
            "--price",
            "NVDA=120",
            "--email",
            "--json",
        ]
    )
    payload = json.loads(capsys.readouterr().out)
    assert payload["status"] == "generated"
    assert payload["notification"]["attempted"] is True
    assert len(fake.messages) == 1


def test_run_scheduled_report_email_failure_notification_on_exception(
    tmp_path, monkeypatch, capsys
) -> None:
    from finwall.email_notifications import EmailSendResult

    database = tmp_path / "finwall.db"
    fake = _FakeEmailProvider(
        EmailSendResult(attempted=True, sent=True, provider="smtp")
    )
    monkeypatch.setattr(
        "finwall.cli.build_email_provider", lambda *args, **kwargs: fake
    )
    monkeypatch.setattr(
        "finwall.cli.build_report_payload",
        lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("boom")),
    )

    code = run(
        [
            "--database",
            str(database),
            "run-scheduled-report",
            "--run-date",
            "2026-05-20",
            "--email-on-failure",
            "--json",
        ]
    )
    payload = json.loads(capsys.readouterr().out)
    assert code == 1
    assert payload["status"] == "failed"
    assert payload["notification"]["attempted"] is True


def test_scheduled_report_email_send_failure_does_not_fail_run(
    tmp_path, monkeypatch, capsys
) -> None:
    from finwall.email_notifications import EmailSendResult

    database = tmp_path / "finwall.db"
    run(["--database", str(database), "add-holding", "NVDA", "1", "100"])
    capsys.readouterr()
    fake = _FakeEmailProvider(
        EmailSendResult(
            attempted=True,
            sent=False,
            provider="smtp",
            warnings=("smtp warning",),
            error="unable to send email notification via SMTP",
        )
    )
    monkeypatch.setattr(
        "finwall.cli.build_email_provider", lambda *args, **kwargs: fake
    )

    code = run(
        [
            "--database",
            str(database),
            "run-scheduled-report",
            "--run-date",
            "2026-05-20",
            "--price",
            "NVDA=120",
            "--email",
            "--json",
        ]
    )
    payload = json.loads(capsys.readouterr().out)
    assert code == 0
    assert payload["status"] == "generated"
    assert payload["notification"]["sent"] is False


def test_scheduled_report_skip_does_not_send_email(
    tmp_path, monkeypatch, capsys
) -> None:
    database = tmp_path / "finwall.db"
    fake = _FakeEmailProvider(None)
    monkeypatch.setattr(
        "finwall.cli.build_email_provider", lambda *args, **kwargs: fake
    )

    run(
        [
            "--database",
            str(database),
            "run-scheduled-report",
            "--run-date",
            "2026-05-23",
            "--email",
            "--json",
        ]
    )
    payload = json.loads(capsys.readouterr().out)
    assert payload["status"] == "skipped"
    assert fake.messages == []


def test_run_scheduled_report_duplicate_suppressed(
    tmp_path, monkeypatch, capsys
) -> None:
    database = tmp_path / "finwall.db"
    run(["--database", str(database), "add-holding", "NVDA", "1", "100"])
    capsys.readouterr()
    fake = _FakeEmailProvider(None)
    monkeypatch.setattr(
        "finwall.cli.build_email_provider", lambda *args, **kwargs: fake
    )

    run(
        [
            "--database",
            str(database),
            "run-scheduled-report",
            "--run-date",
            "2026-05-20",
            "--price",
            "NVDA=120",
            "--email",
            "--json",
        ]
    )
    capsys.readouterr()
    code = run(
        [
            "--database",
            str(database),
            "run-scheduled-report",
            "--run-date",
            "2026-05-20",
            "--price",
            "NVDA=120",
            "--email",
            "--json",
        ]
    )
    payload = json.loads(capsys.readouterr().out)
    assert code == 0
    assert payload["status"] == "duplicate"
    assert payload["scheduled_run"]["status"] == "generated"
    assert fake.messages


def test_run_scheduled_report_suppresses_started_duplicate(tmp_path, capsys) -> None:
    database = tmp_path / "finwall.db"
    run(["--database", str(database), "add-holding", "NVDA", "1", "100"])
    capsys.readouterr()
    run(
        [
            "--database",
            str(database),
            "run-scheduled-report",
            "--run-date",
            "2026-05-20",
            "--price",
            "NVDA=120",
            "--json",
        ]
    )
    capsys.readouterr()
    store = SQLitePortfolioStore(database)
    store.start_scheduled_run("Primary", "2026-05-20", "daily")

    code = run(
        [
            "--database",
            str(database),
            "run-scheduled-report",
            "--run-date",
            "2026-05-20",
            "--price",
            "NVDA=120",
            "--json",
        ]
    )
    payload = json.loads(capsys.readouterr().out)
    assert code == 0
    assert payload["status"] == "duplicate"
    assert payload["scheduled_run"]["status"] == "generated"


def test_run_scheduled_report_handles_start_storage_failures(
    tmp_path, monkeypatch, capsys
) -> None:
    database = tmp_path / "finwall.db"
    run(["--database", str(database), "add-holding", "NVDA", "1", "100"])
    capsys.readouterr()

    def _raise_start_error(*args, **kwargs):
        raise sqlite3.OperationalError("database is locked")

    monkeypatch.setattr(SQLitePortfolioStore, "start_scheduled_run", _raise_start_error)
    code = run(
        [
            "--database",
            str(database),
            "run-scheduled-report",
            "--run-date",
            "2026-05-20",
            "--price",
            "NVDA=120",
            "--json",
        ]
    )
    payload = json.loads(capsys.readouterr().out)
    assert code == 1
    assert payload["status"] == "failed"


def test_scheduled_runs_command_json(tmp_path, capsys) -> None:
    database = tmp_path / "finwall.db"
    run(
        [
            "--database",
            str(database),
            "run-scheduled-report",
            "--run-date",
            "2026-05-23",
            "--json",
        ]
    )
    capsys.readouterr()
    run(["--database", str(database), "scheduled-runs", "--json"])
    payload = json.loads(capsys.readouterr().out)
    assert payload["scheduled_runs"]


def test_security_check_ok(tmp_path, capsys, monkeypatch) -> None:
    monkeypatch.setattr(
        "finwall.cli.settings", __import__("finwall.config").config.Settings()
    )
    code = run(["--database", str(tmp_path / "x.db"), "security-check"])
    assert code == 0
    assert "passed" in capsys.readouterr().out.lower()


def test_security_check_json_warns(tmp_path, capsys, monkeypatch) -> None:
    from finwall.config import Settings

    monkeypatch.setattr(
        "finwall.cli.settings", Settings(api_enabled=True, api_token="")
    )
    code = run(["--database", str(tmp_path / "x.db"), "security-check", "--json"])
    out = capsys.readouterr().out
    assert code == 1
    assert '"ok": false' in out.lower()
    assert "FINWALL_API_TOKEN" in out


def test_security_check_does_not_initialize_store(
    tmp_path, monkeypatch, capsys
) -> None:
    from finwall.config import Settings

    monkeypatch.setattr(
        "finwall.cli.settings",
        Settings(
            storage_backend="postgres", database_url="", api_enabled=True, api_token=""
        ),
    )

    code = run(["--database", str(tmp_path / "x.db"), "security-check", "--json"])
    out = capsys.readouterr().out

    assert code == 1
    assert '"ok": false' in out.lower()
    assert "FINWALL_DATABASE_URL" in out


def test_market_data_check_text_output_with_mock_provider(
    tmp_path, monkeypatch, capsys
) -> None:
    from finwall.config import Settings

    provider = StaticMarketDataProvider(
        prices={
            "MSFT": MarketPrice("MSFT", Decimal("420.50"), "USD", "static", True),
        },
        historical_prices={
            "MSFT": (
                HistoricalPriceBar("MSFT", "2026-01-01", Decimal("410"), 100, "static"),
            ),
        },
    )
    monkeypatch.setattr(
        "finwall.market_data_diagnostics.build_market_data_provider",
        lambda *_: provider,
    )
    monkeypatch.setattr(
        "finwall.cli.settings",
        Settings(market_data_provider="yahoo", market_data_timeout_seconds=1.5),
    )

    code = run(
        [
            "--database",
            str(tmp_path / "unused.db"),
            "market-data-check",
            "--ticker",
            "msft",
            "--historical-days",
            "1",
        ]
    )
    out = capsys.readouterr().out

    assert code == 0
    assert "Market data diagnostics" in out
    assert "Provider: yahoo" in out
    assert "Effective provider: yahoo" in out
    assert "Timeout: 1.5s" in out
    assert "[ok] Latest quote: MSFT price available from static" in out
    assert "[ok] Historical prices: 1 bars returned" in out


def test_market_data_check_uses_default_yfinance_provider(
    tmp_path, monkeypatch, capsys
) -> None:
    import finwall.config as config_module

    provider = StaticMarketDataProvider(
        prices={
            "AAPL": MarketPrice("AAPL", Decimal("190.10"), "USD", "static", True),
        },
        historical_prices={
            "AAPL": (
                HistoricalPriceBar("AAPL", "2026-01-01", Decimal("188"), 100, "static"),
            ),
        },
    )
    provider_args = {}

    def fake_build_provider(provider_name, timeout_seconds):
        provider_args["provider_name"] = provider_name
        provider_args["timeout_seconds"] = timeout_seconds
        return provider

    monkeypatch.setattr(
        "finwall.market_data_diagnostics.build_market_data_provider",
        fake_build_provider,
    )
    monkeypatch.setattr(
        "finwall.market_data_diagnostics._is_yfinance_available",
        lambda: True,
    )
    monkeypatch.delenv("FINWALL_MARKET_DATA_PROVIDER", raising=False)
    monkeypatch.delenv("FINWALL_MARKET_DATA_TIMEOUT_SECONDS", raising=False)
    reloaded_config = importlib.reload(config_module)
    monkeypatch.setattr("finwall.cli.settings", reloaded_config.Settings())

    code = run(
        [
            "--database",
            str(tmp_path / "unused.db"),
            "market-data-check",
            "--json",
        ]
    )
    payload = json.loads(capsys.readouterr().out)

    assert code == 0
    assert payload["provider"] == "yfinance"
    assert payload["effective_provider"] == "yfinance"
    assert payload["checks"][1]["name"] == "yfinance_availability"
    assert payload["checks"][1]["details"]["required"] is True
    assert provider_args == {
        "provider_name": "yfinance",
        "timeout_seconds": 5.0,
    }


def test_market_data_check_json_output_reports_failures(
    tmp_path, monkeypatch, capsys
) -> None:
    from finwall.config import Settings

    monkeypatch.setattr(
        "finwall.market_data_diagnostics.build_market_data_provider",
        lambda *_: StaticMarketDataProvider(),
    )
    monkeypatch.setattr(
        "finwall.cli.settings",
        Settings(market_data_provider="static", market_data_timeout_seconds=5.0),
    )

    code = run(
        [
            "--database",
            str(tmp_path / "unused.db"),
            "market-data-check",
            "--json",
        ]
    )
    payload = json.loads(capsys.readouterr().out)

    assert code == 1
    assert payload["ok"] is False
    assert payload["provider"] == "static"
    assert payload["effective_provider"] == "static"
    assert payload["sample_ticker"] == "AAPL"
    assert payload["checks"][2]["name"] == "latest_quote"
    assert payload["checks"][2]["details"]["safe_error"] == "price not configured"
    assert (
        payload["checks"][3]["details"]["safe_message"] == "no historical bars returned"
    )


def test_market_data_check_does_not_initialize_store(
    tmp_path, monkeypatch, capsys
) -> None:
    from finwall.config import Settings

    provider = StaticMarketDataProvider(
        prices={
            "AAPL": MarketPrice("AAPL", Decimal("190.10"), "USD", "static", True),
        },
        historical_prices={
            "AAPL": (
                HistoricalPriceBar("AAPL", "2026-01-01", Decimal("188"), 100, "static"),
            ),
        },
    )
    monkeypatch.setattr(
        "finwall.market_data_diagnostics.build_market_data_provider",
        lambda *_: provider,
    )
    monkeypatch.setattr(
        "finwall.cli.settings",
        Settings(
            market_data_provider="static",
            storage_backend="postgres",
            database_url="",
        ),
    )

    code = run(
        [
            "--database",
            str(tmp_path / "unused.db"),
            "market-data-check",
            "--json",
        ]
    )
    payload = json.loads(capsys.readouterr().out)

    assert code == 0
    assert payload["ok"] is True


def test_fundamentals_json_uses_live_provider_when_configured(
    tmp_path, monkeypatch, capsys
) -> None:
    from finwall.fundamentals import (
        CompanyProfile,
        FundamentalMetric,
        FundamentalSnapshot,
    )

    database = tmp_path / "finwall.db"
    run(["--database", str(database), "add-watchlist", "LIVE"])

    class LiveProvider:
        def get_fundamentals(self, ticker: str):
            return FundamentalSnapshot(
                ticker=ticker,
                source="yfinance",
                data_status="partial",
                profile=CompanyProfile(
                    ticker, "Live Corp", None, None, None, None, "yfinance", True
                ),
                revenue_growth=FundamentalMetric(
                    "revenue_growth", "10%", True, "yfinance"
                ),
                earnings_growth=FundamentalMetric(
                    "earnings_growth", None, False, "yfinance"
                ),
                profitability=(),
                debt=(),
                valuation=(),
                warnings=(),
            )

    seen = {}

    def fake_builder(provider_name, timeout_seconds):
        seen["provider_name"] = provider_name
        return LiveProvider()

    monkeypatch.setattr("finwall.cli.build_fundamental_data_provider", fake_builder)

    run(["--database", str(database), "fundamentals", "--json"])
    out = capsys.readouterr().out

    assert seen["provider_name"] == "yfinance"
    assert '"source": "yfinance"' in out
    assert '"company_name": "Live Corp"' in out


def test_fundamentals_summary_json_handles_partial_live_snapshot(
    tmp_path, monkeypatch, capsys
) -> None:
    from finwall.fundamentals import (
        CompanyProfile,
        FundamentalMetric,
        FundamentalSnapshot,
    )

    database = tmp_path / "finwall.db"
    run(["--database", str(database), "add-watchlist", "PART"])

    class PartialProvider:
        def get_fundamentals(self, ticker: str):
            return FundamentalSnapshot(
                ticker=ticker,
                source="yfinance",
                data_status="partial",
                profile=CompanyProfile(
                    ticker, "Partial Corp", None, None, None, None, "yfinance", True
                ),
                revenue_growth=FundamentalMetric(
                    "revenue_growth", None, False, "yfinance"
                ),
                earnings_growth=FundamentalMetric(
                    "earnings_growth", None, False, "yfinance"
                ),
                profitability=(),
                debt=(),
                valuation=(),
                warnings=("partial live fundamentals",),
            )

    monkeypatch.setattr(
        "finwall.cli.build_fundamental_data_provider", lambda *_: PartialProvider()
    )

    run(["--database", str(database), "fundamentals-summary", "--json"])
    out = capsys.readouterr().out

    assert '"ticker": "PART"' in out
    assert '"data_status": "partial"' in out
    assert "revenue_growth" in out
