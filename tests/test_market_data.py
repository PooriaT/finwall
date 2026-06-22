from decimal import Decimal
from urllib.error import HTTPError, URLError

from finwall.market_data import (
    FallbackMarketDataProvider,
    HistoricalPriceBar,
    IndexQuote,
    MarketPrice,
    StaticMarketDataProvider,
    YahooMarketDataProvider,
    build_market_data_provider,
    fetch_portfolio_latest_prices,
)
from finwall.market_data_diagnostics import run_market_data_diagnostics
from finwall.market_data_yfinance import YFinanceMarketDataProvider
from finwall.models import Holding, Portfolio


class _FakeMarketDataProvider:
    def __init__(
        self,
        *,
        source: str,
        prices: dict[str, MarketPrice] | None = None,
        index_quotes: dict[str, IndexQuote] | None = None,
        historical_prices: dict[str, tuple[HistoricalPriceBar, ...]] | None = None,
        latest_error: Exception | None = None,
        index_error: Exception | None = None,
        historical_error: Exception | None = None,
    ) -> None:
        self.source = source
        self.prices = prices or {}
        self.index_quotes = index_quotes or {}
        self.historical_prices = historical_prices or {}
        self.latest_error = latest_error
        self.index_error = index_error
        self.historical_error = historical_error
        self.latest_calls: list[tuple[str, ...]] = []
        self.index_calls: list[str] = []
        self.historical_calls: list[tuple[str, int]] = []

    def get_latest_prices(self, tickers):
        normalized = tuple(sorted(ticker.upper() for ticker in tickers))
        self.latest_calls.append(normalized)
        if self.latest_error is not None:
            raise self.latest_error
        return {
            ticker: self.prices[ticker]
            for ticker in normalized
            if ticker in self.prices
        }

    def get_index_quote(self, symbol):
        normalized = symbol.upper()
        self.index_calls.append(normalized)
        if self.index_error is not None:
            raise self.index_error
        return self.index_quotes.get(
            normalized,
            IndexQuote(normalized, None, self.source, False, "index missing"),
        )

    def get_historical_prices(self, ticker: str, days: int = 250):
        normalized = ticker.upper()
        self.historical_calls.append((normalized, days))
        if self.historical_error is not None:
            raise self.historical_error
        return self.historical_prices.get(normalized, ())


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


def test_fetch_portfolio_latest_prices_reports_fallback_success() -> None:
    portfolio = Portfolio(
        name="Primary",
        holdings=(Holding("NVDA", Decimal("2"), Decimal("800")),),
    )
    provider = FallbackMarketDataProvider(
        _FakeMarketDataProvider(
            source="primary",
            latest_error=RuntimeError("raw https://provider/private"),
        ),
        _FakeMarketDataProvider(
            source="fallback",
            prices={
                "NVDA": MarketPrice("NVDA", Decimal("900"), "USD", "fallback", True),
            },
        ),
    )

    latest_prices, warnings = fetch_portfolio_latest_prices(portfolio, provider)

    assert latest_prices == {"NVDA": Decimal("900")}
    assert warnings == [
        "market data fallback used: primary primary unavailable; "
        "fallback fallback succeeded"
    ]


def test_fetch_portfolio_latest_prices_reports_partial_fallback() -> None:
    portfolio = Portfolio(
        name="Primary",
        holdings=(
            Holding("AAPL", Decimal("2"), Decimal("180")),
            Holding("MSFT", Decimal("1"), Decimal("400")),
        ),
    )
    provider = FallbackMarketDataProvider(
        _FakeMarketDataProvider(
            source="primary",
            latest_error=RuntimeError("primary failed"),
        ),
        _FakeMarketDataProvider(
            source="fallback",
            prices={
                "AAPL": MarketPrice("AAPL", Decimal("190"), "USD", "fallback", True),
            },
        ),
    )

    latest_prices, warnings = fetch_portfolio_latest_prices(portfolio, provider)

    assert latest_prices == {"AAPL": Decimal("190")}
    assert warnings[:2] == [
        "market data fallback used: primary primary unavailable; "
        "fallback fallback succeeded",
        "market data fallback returned partial prices: unavailable MSFT",
    ]
    assert warnings[2].startswith("MSFT: primary primary:")


def test_fetch_portfolio_latest_prices_reports_unknown_provider_config() -> None:
    portfolio = Portfolio(
        name="Primary",
        holdings=(Holding("NVDA", Decimal("2"), Decimal("800")),),
    )
    provider = build_market_data_provider("not-real", 1.0)

    _latest_prices, warnings = fetch_portfolio_latest_prices(portfolio, provider)

    assert (
        warnings[0] == "unknown market data provider 'not-real'; using static provider"
    )


def test_market_data_diagnostics_pass_with_mock_provider() -> None:
    provider = StaticMarketDataProvider(
        prices={
            "AAPL": MarketPrice("AAPL", Decimal("190.10"), "USD", "static", True),
        },
        historical_prices={
            "AAPL": (
                HistoricalPriceBar("AAPL", "2026-01-01", Decimal("188"), 100, "static"),
                HistoricalPriceBar("AAPL", "2026-01-02", Decimal("190"), 200, "static"),
            ),
        },
    )

    result = run_market_data_diagnostics(
        provider_name=" static ",
        timeout_seconds=2.5,
        sample_ticker="aapl",
        historical_days=30,
        provider=provider,
    )

    assert result.ok is True
    assert result.provider == "static"
    assert result.effective_provider == "static"
    assert result.sample_ticker == "AAPL"
    assert [check.name for check in result.checks] == [
        "provider_configuration",
        "yfinance_availability",
        "latest_quote",
        "historical_prices",
    ]
    assert result.checks[1].details["required"] is False
    assert result.checks[2].details["price"] == "190.10"
    assert result.checks[3].details["returned_bars"] == 2


def test_market_data_diagnostics_reports_unknown_provider_safe_static_behavior() -> (
    None
):
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

    result = run_market_data_diagnostics(
        provider_name="custom",
        timeout_seconds=5.0,
        sample_ticker="AAPL",
        historical_days=30,
        provider=provider,
    )

    assert result.ok is False
    provider_check = result.checks[0]
    assert provider_check.ok is False
    assert provider_check.details["recognized"] is False
    assert provider_check.details["effective_provider"] == "static"
    assert result.effective_provider == "static"


class _ExplodingMarketDataProvider:
    def get_latest_prices(self, tickers):
        raise RuntimeError("full url https://query1.finance.yahoo.com/private")

    def get_index_quote(self, symbol):
        raise RuntimeError("not used")

    def get_historical_prices(self, ticker: str, days: int = 250):
        raise RuntimeError("raw traceback details")


def test_market_data_diagnostics_uses_safe_errors_for_provider_exceptions() -> None:
    result = run_market_data_diagnostics(
        provider_name="yahoo",
        timeout_seconds=5.0,
        sample_ticker="AAPL",
        historical_days=30,
        provider=_ExplodingMarketDataProvider(),
    )

    assert result.ok is False
    assert result.checks[2].details["safe_error"] == "latest quote check failed"
    assert result.checks[3].details["safe_error"] == "historical price check failed"
    payload = result.as_dict()
    assert "query1.finance.yahoo.com" not in str(payload)


def test_build_market_data_provider_supports_static_yahoo_and_yfinance_chain() -> None:
    assert isinstance(
        build_market_data_provider("static", 1.0), StaticMarketDataProvider
    )
    assert isinstance(build_market_data_provider("yahoo", 1.0), YahooMarketDataProvider)
    provider = build_market_data_provider("yfinance", 1.0)
    assert isinstance(provider, FallbackMarketDataProvider)
    assert isinstance(provider.primary, YFinanceMarketDataProvider)
    assert isinstance(provider.fallback, YahooMarketDataProvider)


def test_build_market_data_provider_normalizes_names_and_falls_back_to_static() -> None:
    assert isinstance(
        build_market_data_provider(" Yahoo ", 1.0), YahooMarketDataProvider
    )
    assert isinstance(
        build_market_data_provider(" YFINANCE ", 1.0), FallbackMarketDataProvider
    )
    assert isinstance(
        build_market_data_provider("STATIC", 1.0), StaticMarketDataProvider
    )
    assert isinstance(
        build_market_data_provider("unknown", 1.0), StaticMarketDataProvider
    )


def test_yahoo_and_static_are_not_automatic_fallback_chains() -> None:
    assert not isinstance(
        build_market_data_provider("yahoo", 1.0), FallbackMarketDataProvider
    )
    assert not isinstance(
        build_market_data_provider("static", 1.0), FallbackMarketDataProvider
    )


def test_fallback_latest_prices_uses_primary_success_without_fallback() -> None:
    primary = _FakeMarketDataProvider(
        source="primary",
        prices={
            "AAPL": MarketPrice("AAPL", Decimal("190"), "USD", "primary", True),
        },
    )
    fallback = _FakeMarketDataProvider(
        source="fallback",
        prices={
            "AAPL": MarketPrice("AAPL", Decimal("191"), "USD", "fallback", True),
        },
    )
    provider = FallbackMarketDataProvider(primary, fallback)

    prices = provider.get_latest_prices(["aapl"])

    assert prices["AAPL"].price == Decimal("190")
    assert prices["AAPL"].source == "primary"
    assert fallback.latest_calls == []
    assert provider.latest_status is not None
    assert provider.latest_status.fallback_attempted is False


def test_fallback_latest_prices_uses_fallback_when_primary_fails() -> None:
    provider = FallbackMarketDataProvider(
        _FakeMarketDataProvider(
            source="primary",
            latest_error=RuntimeError("raw https://provider/private"),
        ),
        _FakeMarketDataProvider(
            source="fallback",
            prices={
                "AAPL": MarketPrice("AAPL", Decimal("191"), "USD", "fallback", True),
            },
        ),
    )

    prices = provider.get_latest_prices(["AAPL"])

    assert prices["AAPL"].available is True
    assert prices["AAPL"].price == Decimal("191")
    assert prices["AAPL"].source == "fallback:primary->fallback"
    assert provider.latest_status is not None
    assert provider.latest_status.primary_failed is True
    assert provider.latest_status.fallback_succeeded is True


def test_fallback_latest_prices_fills_only_missing_tickers() -> None:
    primary = _FakeMarketDataProvider(
        source="primary",
        prices={
            "AAPL": MarketPrice("AAPL", Decimal("190"), "USD", "primary", True),
            "MSFT": MarketPrice("MSFT", None, None, "primary", False, "missing"),
        },
    )
    fallback = _FakeMarketDataProvider(
        source="fallback",
        prices={
            "MSFT": MarketPrice("MSFT", Decimal("420"), "USD", "fallback", True),
        },
    )
    provider = FallbackMarketDataProvider(primary, fallback)

    prices = provider.get_latest_prices(["MSFT", "AAPL"])

    assert prices["AAPL"].source == "primary"
    assert prices["MSFT"].price == Decimal("420")
    assert prices["MSFT"].source == "fallback:primary->fallback"
    assert fallback.latest_calls == [("MSFT",)]
    assert provider.latest_status is not None
    assert provider.latest_status.fulfilled_by_primary == ("AAPL",)
    assert provider.latest_status.fulfilled_by_fallback == ("MSFT",)


def test_fallback_latest_prices_returns_safe_unavailable_when_both_fail() -> None:
    provider = FallbackMarketDataProvider(
        _FakeMarketDataProvider(
            source="primary",
            latest_error=RuntimeError("secret https://primary/private"),
        ),
        _FakeMarketDataProvider(
            source="fallback",
            latest_error=RuntimeError("secret https://fallback/private"),
        ),
    )

    prices = provider.get_latest_prices(["AAPL"])

    assert prices["AAPL"].available is False
    assert prices["AAPL"].source == "fallback:primary->fallback"
    assert prices["AAPL"].error == (
        "primary primary: primary provider latest quote request failed; "
        "fallback fallback: fallback provider latest quote request failed"
    )
    assert "https://" not in str(prices)


def test_fallback_index_quote_uses_primary_success_without_fallback() -> None:
    primary = _FakeMarketDataProvider(
        source="primary",
        index_quotes={
            "SP500": IndexQuote("SP500", Decimal("5000"), "primary", True),
        },
    )
    fallback = _FakeMarketDataProvider(
        source="fallback",
        index_quotes={
            "SP500": IndexQuote("SP500", Decimal("5100"), "fallback", True),
        },
    )
    provider = FallbackMarketDataProvider(primary, fallback)

    quote = provider.get_index_quote("SP500")

    assert quote.price == Decimal("5000")
    assert quote.source == "primary"
    assert fallback.index_calls == []


def test_fallback_index_quote_uses_fallback_when_primary_unavailable() -> None:
    provider = FallbackMarketDataProvider(
        _FakeMarketDataProvider(source="primary"),
        _FakeMarketDataProvider(
            source="fallback",
            index_quotes={
                "SP500": IndexQuote("SP500", Decimal("5100"), "fallback", True),
            },
        ),
    )

    quote = provider.get_index_quote("SP500")

    assert quote.available is True
    assert quote.price == Decimal("5100")
    assert quote.source == "fallback:primary->fallback"


def test_fallback_historical_prices_uses_primary_success_without_fallback() -> None:
    bars = (HistoricalPriceBar("AAPL", "2026-01-01", Decimal("190"), 1, "primary"),)
    primary = _FakeMarketDataProvider(
        source="primary",
        historical_prices={"AAPL": bars},
    )
    fallback = _FakeMarketDataProvider(source="fallback")
    provider = FallbackMarketDataProvider(primary, fallback)

    result = provider.get_historical_prices("AAPL", days=5)

    assert result == bars
    assert fallback.historical_calls == []


def test_fallback_historical_prices_uses_fallback_when_primary_empty() -> None:
    bars = (HistoricalPriceBar("AAPL", "2026-01-01", Decimal("190"), 1, "fallback"),)
    provider = FallbackMarketDataProvider(
        _FakeMarketDataProvider(source="primary"),
        _FakeMarketDataProvider(
            source="fallback",
            historical_prices={"AAPL": bars},
        ),
    )

    result = provider.get_historical_prices("AAPL", days=5)

    assert len(result) == 1
    assert result[0].source == "fallback:primary->fallback"
    assert provider.historical_status is not None
    assert provider.historical_status.fallback_succeeded is True


def test_fallback_historical_prices_returns_empty_when_both_fail() -> None:
    provider = FallbackMarketDataProvider(
        _FakeMarketDataProvider(
            source="primary",
            historical_error=RuntimeError("raw https://primary/private"),
        ),
        _FakeMarketDataProvider(
            source="fallback",
            historical_error=RuntimeError("raw https://fallback/private"),
        ),
    )

    result = provider.get_historical_prices("AAPL", days=5)

    assert result == ()
    assert provider.historical_status is not None
    assert provider.historical_status.fallback_attempted is True
    assert "https://" not in str(provider.historical_status.as_dict())


def test_market_data_diagnostics_exposes_fallback_attempt_and_source(
    monkeypatch,
) -> None:
    provider = FallbackMarketDataProvider(
        _FakeMarketDataProvider(source="primary"),
        _FakeMarketDataProvider(
            source="fallback",
            prices={
                "AAPL": MarketPrice("AAPL", Decimal("191"), "USD", "fallback", True),
            },
            historical_prices={
                "AAPL": (
                    HistoricalPriceBar(
                        "AAPL", "2026-01-01", Decimal("190"), 1, "fallback"
                    ),
                ),
            },
        ),
    )
    monkeypatch.setattr(
        "finwall.market_data_diagnostics._is_yfinance_available",
        lambda: True,
    )

    result = run_market_data_diagnostics(
        provider_name="yfinance",
        timeout_seconds=1.0,
        sample_ticker="AAPL",
        historical_days=5,
        provider=provider,
    )

    assert result.primary_provider == "primary"
    assert result.fallback_provider == "fallback"
    latest_fallback = result.checks[2].details["fallback"]
    historical_fallback = result.checks[3].details["fallback"]
    assert latest_fallback["fallback_attempted"] is True
    assert latest_fallback["fallback_succeeded"] is True
    assert result.checks[2].details["source"] == "fallback:primary->fallback"
    assert historical_fallback["fallback_attempted"] is True


def test_yahoo_latest_prices_returns_price_and_currency(monkeypatch) -> None:
    provider = YahooMarketDataProvider(timeout_seconds=1.0)

    monkeypatch.setattr(
        provider,
        "_fetch_json",
        lambda _url: {
            "quoteResponse": {
                "result": [
                    {
                        "symbol": "AAPL",
                        "regularMarketPrice": 190.1,
                        "currency": "USD",
                    }
                ]
            }
        },
    )

    prices = provider.get_latest_prices(["AAPL"])

    assert prices["AAPL"].available is True
    assert prices["AAPL"].price == Decimal("190.1")
    assert prices["AAPL"].currency == "USD"
    assert prices["AAPL"].source == "yahoo-finance-public"


def test_yahoo_latest_prices_normalizes_duplicate_and_lowercase_tickers(
    monkeypatch,
) -> None:
    provider = YahooMarketDataProvider(timeout_seconds=1.0)
    urls: list[str] = []

    def fetch_json(url: str) -> dict:
        urls.append(url)
        return {
            "quoteResponse": {
                "result": [
                    {
                        "symbol": "AAPL",
                        "regularMarketPrice": 190.1,
                        "currency": "USD",
                    },
                    {
                        "symbol": "MSFT",
                        "regularMarketPrice": 420.2,
                        "currency": "USD",
                    },
                ]
            }
        }

    monkeypatch.setattr(provider, "_fetch_json", fetch_json)

    prices = provider.get_latest_prices([" aapl ", "AAPL", "msft"])

    assert list(prices) == ["AAPL", "MSFT"]
    assert len(urls) == 1
    assert "symbols=AAPL,MSFT" in urls[0]


def test_yahoo_latest_prices_empty_input_returns_empty_result(monkeypatch) -> None:
    provider = YahooMarketDataProvider(timeout_seconds=1.0)

    def fetch_json(_url: str) -> dict:
        raise AssertionError("empty input should not call Yahoo")

    monkeypatch.setattr(provider, "_fetch_json", fetch_json)

    assert provider.get_latest_prices([" ", ""]) == {}


def test_yahoo_latest_prices_returns_unavailable_for_malformed_quote_response(
    monkeypatch,
) -> None:
    provider = YahooMarketDataProvider(timeout_seconds=1.0)
    monkeypatch.setattr(provider, "_fetch_json", lambda _url: {"bad": "payload"})

    prices = provider.get_latest_prices(["AAPL"])

    assert prices["AAPL"].available is False
    assert prices["AAPL"].error == "malformed Yahoo quote response"


def test_yahoo_latest_prices_returns_unavailable_for_missing_quote_result(
    monkeypatch,
) -> None:
    provider = YahooMarketDataProvider(timeout_seconds=1.0)
    monkeypatch.setattr(provider, "_fetch_json", lambda _url: {"quoteResponse": {}})

    prices = provider.get_latest_prices(["AAPL"])

    assert prices["AAPL"].available is False
    assert prices["AAPL"].error == "malformed Yahoo quote response: result missing"


def test_yahoo_latest_prices_returns_unavailable_for_unexpected_payload(
    monkeypatch,
) -> None:
    provider = YahooMarketDataProvider(timeout_seconds=1.0)
    monkeypatch.setattr(provider, "_fetch_json", lambda _url: None)

    prices = provider.get_latest_prices(["AAPL"])

    assert prices["AAPL"].available is False
    assert prices["AAPL"].error == "unexpected Yahoo quote response"


def test_yahoo_latest_prices_returns_unavailable_for_non_list_quote_result(
    monkeypatch,
) -> None:
    provider = YahooMarketDataProvider(timeout_seconds=1.0)
    monkeypatch.setattr(
        provider,
        "_fetch_json",
        lambda _url: {"quoteResponse": {"result": {"symbol": "AAPL"}}},
    )

    prices = provider.get_latest_prices(["AAPL"])

    assert prices["AAPL"].available is False
    assert (
        prices["AAPL"].error == "malformed Yahoo quote response: result is not a list"
    )


def test_yahoo_latest_prices_marks_missing_ticker_unavailable(monkeypatch) -> None:
    provider = YahooMarketDataProvider(timeout_seconds=1.0)
    monkeypatch.setattr(
        provider,
        "_fetch_json",
        lambda _url: {"quoteResponse": {"result": []}},
    )

    prices = provider.get_latest_prices(["AAPL"])

    assert prices["AAPL"].available is False
    assert prices["AAPL"].error == "ticker not found in Yahoo response"


def test_yahoo_latest_prices_marks_missing_price_unavailable(monkeypatch) -> None:
    provider = YahooMarketDataProvider(timeout_seconds=1.0)
    monkeypatch.setattr(
        provider,
        "_fetch_json",
        lambda _url: {
            "quoteResponse": {"result": [{"symbol": "AAPL", "currency": "USD"}]}
        },
    )

    prices = provider.get_latest_prices(["AAPL"])

    assert prices["AAPL"].available is False
    assert prices["AAPL"].error == "price missing in Yahoo response"


def test_yahoo_latest_prices_marks_invalid_price_unavailable(monkeypatch) -> None:
    provider = YahooMarketDataProvider(timeout_seconds=1.0)
    monkeypatch.setattr(
        provider,
        "_fetch_json",
        lambda _url: {
            "quoteResponse": {
                "result": [
                    {
                        "symbol": "AAPL",
                        "regularMarketPrice": float("nan"),
                        "currency": "USD",
                    }
                ]
            }
        },
    )

    prices = provider.get_latest_prices(["AAPL"])

    assert prices["AAPL"].available is False
    assert prices["AAPL"].price is None
    assert prices["AAPL"].error == "price invalid in Yahoo response"


def test_yahoo_latest_prices_marks_missing_currency_unavailable(monkeypatch) -> None:
    provider = YahooMarketDataProvider(timeout_seconds=1.0)
    monkeypatch.setattr(
        provider,
        "_fetch_json",
        lambda _url: {
            "quoteResponse": {
                "result": [{"symbol": "AAPL", "regularMarketPrice": 190.1}]
            }
        },
    )

    prices = provider.get_latest_prices(["AAPL"])

    assert prices["AAPL"].available is False
    assert prices["AAPL"].error == "currency missing in Yahoo response"


def test_yahoo_latest_prices_marks_stale_quote_unavailable(monkeypatch) -> None:
    provider = YahooMarketDataProvider(timeout_seconds=1.0)
    monkeypatch.setattr(
        provider,
        "_fetch_json",
        lambda _url: {
            "quoteResponse": {
                "result": [
                    {
                        "symbol": "AAPL",
                        "regularMarketPrice": 190.1,
                        "currency": "USD",
                        "regularMarketTime": 946684800,
                    }
                ]
            }
        },
    )

    prices = provider.get_latest_prices(["AAPL"])

    assert prices["AAPL"].available is False
    assert prices["AAPL"].error == "quote may be stale; last market time was 2000-01-01"


def test_yahoo_latest_prices_timeout_returns_safe_error(monkeypatch) -> None:
    provider = YahooMarketDataProvider(timeout_seconds=1.0)

    def fetch_json(_url: str) -> dict:
        raise TimeoutError("raw timeout details")

    monkeypatch.setattr(provider, "_fetch_json", fetch_json)

    prices = provider.get_latest_prices(["AAPL"])

    assert prices["AAPL"].available is False
    assert prices["AAPL"].error == "market data request timed out"


def test_yahoo_latest_prices_http_and_url_errors_return_safe_errors(
    monkeypatch,
) -> None:
    provider = YahooMarketDataProvider(timeout_seconds=1.0)

    def raise_http_error(_url: str) -> dict:
        raise HTTPError(
            "https://query1.finance.yahoo.com/v7/finance/quote?symbols=AAPL",
            429,
            "Too Many Requests",
            {},
            None,
        )

    monkeypatch.setattr(provider, "_fetch_json", raise_http_error)
    http_prices = provider.get_latest_prices(["AAPL"])
    assert http_prices["AAPL"].error == "Yahoo market data request failed with HTTP 429"

    def raise_url_error(_url: str) -> dict:
        raise URLError("https://query1.finance.yahoo.com/full-url")

    monkeypatch.setattr(provider, "_fetch_json", raise_url_error)
    url_prices = provider.get_latest_prices(["AAPL"])
    assert (
        url_prices["AAPL"].error
        == "Yahoo market data request failed due to a network error"
    )


def test_yahoo_latest_prices_invalid_json_returns_safe_error(monkeypatch) -> None:
    provider = YahooMarketDataProvider(timeout_seconds=1.0)

    def fetch_json(_url: str) -> dict:
        raise ValueError("raw decoder details")

    monkeypatch.setattr(provider, "_fetch_json", fetch_json)

    prices = provider.get_latest_prices(["AAPL"])

    assert prices["AAPL"].available is False
    assert prices["AAPL"].error == "Yahoo market data response was invalid JSON"


def test_yahoo_historical_prices_skips_invalid_timestamp_and_nan_volume(
    monkeypatch,
) -> None:
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
    provider = YahooMarketDataProvider(timeout_seconds=1.0)

    monkeypatch.setattr(
        provider,
        "_fetch_json",
        lambda _url: {
            "quoteResponse": {
                "result": [
                    None,
                    "bad-item",
                    {
                        "symbol": "AAPL",
                        "regularMarketPrice": 190.1,
                        "currency": "USD",
                    },
                ]
            }
        },
    )

    prices = provider.get_latest_prices(["AAPL", "MSFT"])

    assert prices["AAPL"].available is True
    assert prices["AAPL"].price == Decimal("190.1")
    assert prices["MSFT"].available is False
    assert prices["MSFT"].error == "ticker not found in Yahoo response"


def test_yahoo_historical_prices_returns_empty_for_non_list_result(monkeypatch) -> None:
    provider = YahooMarketDataProvider(timeout_seconds=1.0)

    monkeypatch.setattr(
        provider,
        "_fetch_json",
        lambda _url: {"chart": {"result": {"timestamp": [1715731200]}}},
    )

    assert provider.get_historical_prices("aapl", days=5) == ()


def test_yahoo_historical_prices_returns_ordered_bars(monkeypatch) -> None:
    provider = YahooMarketDataProvider(timeout_seconds=1.0)
    monkeypatch.setattr(
        provider,
        "_fetch_json",
        lambda _url: {
            "chart": {
                "result": [
                    {
                        "timestamp": [1715644800, 1715731200],
                        "indicators": {
                            "quote": [
                                {
                                    "close": [100.5, 101.5],
                                    "volume": [1000, 2000],
                                }
                            ]
                        },
                    }
                ]
            }
        },
    )

    bars = provider.get_historical_prices("aapl", days=5)

    assert [bar.date for bar in bars] == ["2024-05-14", "2024-05-15"]
    assert [bar.close for bar in bars] == [Decimal("100.5"), Decimal("101.5")]
    assert [bar.volume for bar in bars] == [1000, 2000]


def test_yahoo_historical_prices_missing_close_values_do_not_crash(
    monkeypatch,
) -> None:
    provider = YahooMarketDataProvider(timeout_seconds=1.0)
    monkeypatch.setattr(
        provider,
        "_fetch_json",
        lambda _url: {
            "chart": {
                "result": [
                    {
                        "timestamp": [1715644800, 1715731200],
                        "indicators": {
                            "quote": [{"close": [100.5], "volume": [1000, 2000]}]
                        },
                    }
                ]
            }
        },
    )

    bars = provider.get_historical_prices("aapl", days=5)

    assert len(bars) == 1
    assert bars[0].close == Decimal("100.5")


def test_yahoo_historical_prices_invalid_close_values_are_skipped(
    monkeypatch,
) -> None:
    provider = YahooMarketDataProvider(timeout_seconds=1.0)
    monkeypatch.setattr(
        provider,
        "_fetch_json",
        lambda _url: {
            "chart": {
                "result": [
                    {
                        "timestamp": [1715644800, 1715731200],
                        "indicators": {
                            "quote": [
                                {
                                    "close": [float("nan"), 101.5],
                                    "volume": [1000, 2000],
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
    assert bars[0].close == Decimal("101.5")


def test_yahoo_historical_prices_mismatched_lengths_do_not_crash(
    monkeypatch,
) -> None:
    provider = YahooMarketDataProvider(timeout_seconds=1.0)
    monkeypatch.setattr(
        provider,
        "_fetch_json",
        lambda _url: {
            "chart": {
                "result": [
                    {
                        "timestamp": [1715644800, 1715731200, 1715817600],
                        "indicators": {
                            "quote": [{"close": [100.5, 101.5], "volume": [1000]}]
                        },
                    }
                ]
            }
        },
    )

    bars = provider.get_historical_prices("aapl", days=5)

    assert len(bars) == 2
    assert bars[0].volume == 1000
    assert bars[1].volume is None


def test_yahoo_historical_prices_returns_empty_for_errors_and_invalid_json(
    monkeypatch,
) -> None:
    provider = YahooMarketDataProvider(timeout_seconds=1.0)

    def raise_timeout(_url: str) -> dict:
        raise TimeoutError("timeout")

    monkeypatch.setattr(provider, "_fetch_json", raise_timeout)
    assert provider.get_historical_prices("aapl", days=5) == ()

    def raise_json_error(_url: str) -> dict:
        raise ValueError("bad json")

    monkeypatch.setattr(provider, "_fetch_json", raise_json_error)
    assert provider.get_historical_prices("aapl", days=5) == ()


def test_yahoo_historical_prices_returns_empty_for_empty_ticker_or_non_positive_days(
    monkeypatch,
) -> None:
    provider = YahooMarketDataProvider(timeout_seconds=1.0)

    def fetch_json(_url: str) -> dict:
        raise AssertionError("invalid request should not call Yahoo")

    monkeypatch.setattr(provider, "_fetch_json", fetch_json)

    assert provider.get_historical_prices("", days=5) == ()
    assert provider.get_historical_prices("AAPL", days=0) == ()


class _FakeYFinanceModule:
    def __init__(self, ticker_class):
        self.Ticker = ticker_class


def _install_fake_yfinance(monkeypatch, ticker_class) -> None:
    import finwall.market_data_yfinance as market_data_yfinance

    fake_module = _FakeYFinanceModule(ticker_class)
    monkeypatch.setattr(
        market_data_yfinance.importlib,
        "import_module",
        lambda name: fake_module
        if name == "yfinance"
        else (_ for _ in ()).throw(ImportError(name)),
    )


class _FakeHistory:
    def __init__(self, rows, *, empty: bool = False, attrs=None) -> None:
        self._rows = rows
        self.empty = empty
        self.attrs = attrs or {}

    def iterrows(self):
        return iter(self._rows)


def test_yfinance_missing_dependency_returns_safe_unavailable_prices(
    monkeypatch,
) -> None:
    import finwall.market_data_yfinance as market_data_yfinance

    def raise_import_error(_name: str):
        raise ImportError("No module named yfinance")

    monkeypatch.setattr(
        market_data_yfinance.importlib,
        "import_module",
        raise_import_error,
    )
    provider = YFinanceMarketDataProvider(timeout_seconds=1.0)

    prices = provider.get_latest_prices(["AAPL"])

    assert prices["AAPL"].available is False
    assert prices["AAPL"].source == "yfinance"
    assert "install project dependencies" in prices["AAPL"].error
    assert provider.get_historical_prices("AAPL", days=5) == ()


def test_yfinance_latest_prices_success_with_fake_module(monkeypatch) -> None:
    class FakeTicker:
        def __init__(self, symbol: str) -> None:
            self.symbol = symbol

        def history(self, **kwargs):
            assert kwargs == {
                "period": "5d",
                "interval": "1d",
                "auto_adjust": False,
                "timeout": 1.0,
            }
            return _FakeHistory(
                [
                    ("2026-01-01", {"Close": 188.5, "Volume": 1000}),
                    ("2026-01-02", {"Close": 190.25, "Volume": 2000}),
                ],
                attrs={"currency": "USD"},
            )

    _install_fake_yfinance(monkeypatch, FakeTicker)
    provider = YFinanceMarketDataProvider(timeout_seconds=1.0)

    prices = provider.get_latest_prices([" aapl ", "AAPL"])

    assert list(prices) == ["AAPL"]
    assert prices["AAPL"].available is True
    assert prices["AAPL"].price == Decimal("190.25")
    assert prices["AAPL"].currency == "USD"
    assert prices["AAPL"].source == "yfinance"


def test_yfinance_latest_prices_missing_price_is_unavailable(monkeypatch) -> None:
    class FakeTicker:
        def __init__(self, _symbol: str) -> None:
            pass

        def history(self, **kwargs):
            assert kwargs["timeout"] == 1.0
            return _FakeHistory([], empty=True)

    _install_fake_yfinance(monkeypatch, FakeTicker)
    provider = YFinanceMarketDataProvider(timeout_seconds=1.0)

    prices = provider.get_latest_prices(["AAPL"])

    assert prices["AAPL"].available is False
    assert prices["AAPL"].price is None
    assert prices["AAPL"].error == "price missing in yfinance response"


def test_yfinance_latest_prices_provider_exception_is_safe(monkeypatch) -> None:
    class FakeTicker:
        def __init__(self, _symbol: str) -> None:
            raise RuntimeError("raw provider details")

    _install_fake_yfinance(monkeypatch, FakeTicker)
    provider = YFinanceMarketDataProvider(timeout_seconds=1.0)

    prices = provider.get_latest_prices(["AAPL"])

    assert prices["AAPL"].available is False
    assert prices["AAPL"].error == "yfinance latest quote request failed"


def test_yfinance_historical_prices_success_with_fake_data(monkeypatch) -> None:
    class FakeTicker:
        def __init__(self, _symbol: str) -> None:
            pass

        def history(self, **kwargs):
            assert kwargs["period"] == "5d"
            assert kwargs["interval"] == "1d"
            assert kwargs["timeout"] == 1.0
            return _FakeHistory(
                [
                    ("2026-01-01", {"Close": 100.5, "Volume": 1000}),
                    ("2026-01-02", {"Close": 101.5, "Volume": None}),
                ]
            )

    _install_fake_yfinance(monkeypatch, FakeTicker)
    provider = YFinanceMarketDataProvider(timeout_seconds=1.0)

    bars = provider.get_historical_prices("aapl", days=5)

    assert [bar.date for bar in bars] == ["2026-01-01", "2026-01-02"]
    assert [bar.close for bar in bars] == [Decimal("100.5"), Decimal("101.5")]
    assert [bar.volume for bar in bars] == [1000, None]
    assert {bar.source for bar in bars} == {"yfinance"}


def test_yfinance_historical_prices_empty_and_malformed_responses(
    monkeypatch,
) -> None:
    class EmptyTicker:
        def __init__(self, _symbol: str) -> None:
            pass

        def history(self, **_kwargs):
            return _FakeHistory([], empty=True)

    _install_fake_yfinance(monkeypatch, EmptyTicker)
    provider = YFinanceMarketDataProvider(timeout_seconds=1.0)
    assert provider.get_historical_prices("AAPL", days=5) == ()

    class MalformedTicker:
        def __init__(self, _symbol: str) -> None:
            pass

        def history(self, **_kwargs):
            return object()

    _install_fake_yfinance(monkeypatch, MalformedTicker)
    assert provider.get_historical_prices("AAPL", days=5) == ()


def test_yfinance_index_quote_uses_existing_index_symbol_mapping(
    monkeypatch,
) -> None:
    requested_symbols: list[str] = []

    class FakeTicker:
        def __init__(self, symbol: str) -> None:
            requested_symbols.append(symbol)

        def history(self, **kwargs):
            assert kwargs["timeout"] == 1.0
            return _FakeHistory(
                [("2026-01-02", {"Close": 5100.5, "Volume": 1000})],
                attrs={"currency": "USD"},
            )

    _install_fake_yfinance(monkeypatch, FakeTicker)
    provider = YFinanceMarketDataProvider(timeout_seconds=1.0)

    quote = provider.get_index_quote("sp500")

    assert requested_symbols == ["^GSPC"]
    assert quote.symbol == "SP500"
    assert quote.available is True
    assert quote.price == Decimal("5100.5")
    assert quote.source == "yfinance"


def test_yfinance_historical_provider_exception_returns_empty(
    monkeypatch,
) -> None:
    class FakeTicker:
        def __init__(self, _symbol: str) -> None:
            pass

        def history(self, **_kwargs):
            raise RuntimeError("raw provider details")

    _install_fake_yfinance(monkeypatch, FakeTicker)
    provider = YFinanceMarketDataProvider(timeout_seconds=1.0)

    assert provider.get_historical_prices("AAPL", days=5) == ()
