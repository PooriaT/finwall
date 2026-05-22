from decimal import Decimal

from finwall.market_data import (
    IndexQuote,
    MarketPrice,
    StaticMarketDataProvider,
    fetch_portfolio_latest_prices,
)
from finwall.models import Holding, Portfolio


def test_static_provider_returns_configured_prices_and_index_quote() -> None:
    provider = StaticMarketDataProvider(
        prices={"NVDA": MarketPrice("NVDA", Decimal("950.10"), "USD", "static", True)},
        index_quotes={"SP500": IndexQuote("SP500", Decimal("5000.00"), "static", True)},
    )

    prices = provider.get_latest_prices(["NVDA", "AAPL"])
    assert prices["NVDA"].available is True
    assert prices["NVDA"].price == Decimal("950.10")
    assert prices["AAPL"].available is False

    quote = provider.get_index_quote("SP500")
    assert quote.available is True
    assert quote.price == Decimal("5000.00")


def test_fetch_portfolio_latest_prices_skips_missing_and_collects_warnings() -> None:
    portfolio = Portfolio(
        name="Primary",
        holdings=(
            Holding("NVDA", Decimal("2"), Decimal("800")),
            Holding("PLTR", Decimal("3"), Decimal("20")),
        ),
    )
    provider = StaticMarketDataProvider(
        prices={
            "NVDA": MarketPrice("NVDA", Decimal("900"), "USD", "static", True),
            "PLTR": MarketPrice("PLTR", None, "USD", "static", False, "missing"),
        }
    )

    latest_prices, warnings = fetch_portfolio_latest_prices(portfolio, provider)

    assert latest_prices == {"NVDA": Decimal("900")}
    assert warnings == ["PLTR: missing"]


def test_yahoo_historical_prices_skips_invalid_timestamp_and_nan_volume(
    monkeypatch,
) -> None:
    from finwall.market_data import YahooMarketDataProvider

    provider = YahooMarketDataProvider(timeout_seconds=1.0)

    monkeypatch.setattr(
        provider,
        "_fetch_json",
        lambda _url: {
            "chart": {
                "result": [
                    {
                        "timestamp": [None, 1715731200],
                        "indicators": {
                            "quote": [
                                {
                                    "close": [100.5, 101.5],
                                    "volume": [float("nan"), float("nan")],
                                }
                            ]
                        },
                    }
                ]
            }
        },
    )

    bars = provider.get_historical_prices("aapl", days=5)

    assert len(bars) == 1
    assert bars[0].ticker == "AAPL"
    assert bars[0].close == Decimal("101.5")
    assert bars[0].volume is None


def test_yahoo_latest_prices_ignores_non_dict_quote_entries(monkeypatch) -> None:
    from finwall.market_data import YahooMarketDataProvider

    provider = YahooMarketDataProvider(timeout_seconds=1.0)

    monkeypatch.setattr(
        provider,
        "_fetch_json",
        lambda _url: {
            "quoteResponse": {
                "result": [None, "bad-item", {"symbol": "AAPL", "regularMarketPrice": 190.1, "currency": "USD"}]
            }
        },
    )

    prices = provider.get_latest_prices(["AAPL", "MSFT"])

    assert prices["AAPL"].available is True
    assert prices["AAPL"].price == Decimal("190.1")
    assert prices["MSFT"].available is False
    assert prices["MSFT"].error == "ticker not found in response"


def test_yahoo_historical_prices_returns_empty_for_non_list_result(monkeypatch) -> None:
    from finwall.market_data import YahooMarketDataProvider

    provider = YahooMarketDataProvider(timeout_seconds=1.0)

    monkeypatch.setattr(
        provider,
        "_fetch_json",
        lambda _url: {"chart": {"result": {"timestamp": [1715731200]}}},
    )

    assert provider.get_historical_prices("aapl", days=5) == ()
