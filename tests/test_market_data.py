from decimal import Decimal
from urllib.error import HTTPError, URLError

import pytest

from finwall.market_data import (
    HistoricalPriceResult,
    IndexQuote,
    MarketDataErrorCode,
    MarketDataOperation,
    MarketPrice,
    StaticMarketDataProvider,
    YahooMarketDataProvider,
    fetch_portfolio_latest_prices,
)
from finwall.models import Holding, Portfolio


def test_market_diagnostic_dict_and_quote_fields() -> None:
    provider = StaticMarketDataProvider()
    price = provider.get_latest_prices(["AAPL"])["AAPL"]
    assert price.error_code == MarketDataErrorCode.MISSING_PRICE
    assert price.diagnostic is not None
    payload = price.diagnostic.as_dict()
    assert payload["operation"] == MarketDataOperation.LATEST_PRICES


def test_static_provider_missing_historical_result() -> None:
    provider = StaticMarketDataProvider()
    result = provider.get_historical_price_result("NVDA", 20)
    assert isinstance(result, HistoricalPriceResult)
    assert result.available is False
    assert result.error_code == MarketDataErrorCode.MISSING_HISTORICAL_DATA
    assert provider.get_historical_prices("NVDA", 20) == ()


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
            "PLTR": MarketPrice(
                "PLTR",
                None,
                "USD",
                "static",
                False,
                "latest price missing from provider response",
            ),
        }
    )

    latest_prices, warnings = fetch_portfolio_latest_prices(portfolio, provider)

    assert latest_prices == {"NVDA": Decimal("900")}
    assert warnings == ["PLTR: latest price missing from provider response"]


@pytest.mark.parametrize(
    ("exc", "code"),
    [
        (TimeoutError("x"), MarketDataErrorCode.TIMEOUT),
        (URLError("x"), MarketDataErrorCode.NETWORK_ERROR),
        (ValueError("x"), MarketDataErrorCode.MALFORMED_RESPONSE),
        (HTTPError("http://x", 429, "", None, None), MarketDataErrorCode.RATE_LIMITED),
    ],
)
def test_yahoo_latest_classifies_failures(monkeypatch, exc, code) -> None:
    provider = YahooMarketDataProvider(timeout_seconds=1.0)
    monkeypatch.setattr(
        provider, "_fetch_json", lambda _url: (_ for _ in ()).throw(exc)
    )
    price = provider.get_latest_prices(["NVDA"])["NVDA"]
    assert price.available is False
    assert price.error_code == code


def test_yahoo_latest_response_classification(monkeypatch) -> None:
    provider = YahooMarketDataProvider(timeout_seconds=1.0)
    monkeypatch.setattr(
        provider,
        "_fetch_json",
        lambda _url: {"quoteResponse": {"result": [{"symbol": "NVDA"}]}},
    )
    assert (
        provider.get_latest_prices(["NVDA"])["NVDA"].error_code
        == MarketDataErrorCode.MISSING_PRICE
    )
    assert (
        provider.get_latest_prices(["AAPL"])["AAPL"].error_code
        == MarketDataErrorCode.MISSING_SYMBOL
    )


def test_yahoo_historical_malformed_and_valid(monkeypatch) -> None:
    provider = YahooMarketDataProvider(timeout_seconds=1.0)
    monkeypatch.setattr(provider, "_fetch_json", lambda _url: {"chart": {"result": []}})
    result = provider.get_historical_price_result("AAPL", 5)
    assert result.available is False
    assert result.error_code == MarketDataErrorCode.MALFORMED_RESPONSE

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


def test_static_provider_returns_configured_prices_and_index_quote() -> None:
    provider = StaticMarketDataProvider(
        prices={"NVDA": MarketPrice("NVDA", Decimal("950.10"), "USD", "static", True)},
        index_quotes={"SP500": IndexQuote("SP500", Decimal("5000.00"), "static", True)},
    )
    prices = provider.get_latest_prices(["NVDA", "AAPL"])
    assert prices["NVDA"].available is True
    assert prices["AAPL"].available is False
