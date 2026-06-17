from __future__ import annotations

import json
import math
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from typing import Iterable, Protocol
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import urlopen

from finwall.models import Portfolio

INDEX_SYMBOL_MAP = {
    "SP500": "^GSPC",
    "NASDAQ": "^IXIC",
}
STALE_QUOTE_SECONDS = 7 * 24 * 60 * 60


@dataclass(frozen=True)
class MarketPrice:
    ticker: str
    price: Decimal | None
    currency: str | None
    source: str
    available: bool
    error: str | None = None


@dataclass(frozen=True)
class IndexQuote:
    symbol: str
    price: Decimal | None
    source: str
    available: bool
    error: str | None = None


@dataclass(frozen=True)
class HistoricalPriceBar:
    ticker: str
    date: str
    close: Decimal | None
    volume: int | None
    source: str


class MarketDataProvider(Protocol):
    def get_latest_prices(self, tickers: Iterable[str]) -> dict[str, MarketPrice]: ...

    def get_index_quote(self, symbol: str) -> IndexQuote: ...

    def get_historical_prices(
        self,
        ticker: str,
        days: int = 250,
    ) -> tuple[HistoricalPriceBar, ...]: ...


class StaticMarketDataProvider:
    def __init__(
        self,
        prices: dict[str, MarketPrice] | None = None,
        index_quotes: dict[str, IndexQuote] | None = None,
        historical_prices: dict[str, tuple[HistoricalPriceBar, ...]] | None = None,
    ) -> None:
        self._prices = {
            ticker.upper(): value for ticker, value in (prices or {}).items()
        }
        self._index_quotes = {
            symbol.upper(): value for symbol, value in (index_quotes or {}).items()
        }
        self._historical_prices = {
            ticker.upper(): tuple(bars)
            for ticker, bars in (historical_prices or {}).items()
        }

    def get_latest_prices(self, tickers: Iterable[str]) -> dict[str, MarketPrice]:
        results: dict[str, MarketPrice] = {}
        for raw_ticker in tickers:
            ticker = raw_ticker.upper()
            fallback = MarketPrice(
                ticker=ticker,
                price=None,
                currency=None,
                source="static",
                available=False,
                error="price not configured",
            )
            results[ticker] = self._prices.get(ticker, fallback)
        return results

    def get_index_quote(self, symbol: str) -> IndexQuote:
        key = symbol.upper()
        return self._index_quotes.get(
            key,
            IndexQuote(
                symbol=key,
                price=None,
                source="static",
                available=False,
                error="index quote not configured",
            ),
        )

    def get_historical_prices(
        self,
        ticker: str,
        days: int = 250,
    ) -> tuple[HistoricalPriceBar, ...]:
        normalized = ticker.upper()
        bars = self._historical_prices.get(normalized, ())
        if days <= 0:
            return ()
        return bars[-days:]


class YahooMarketDataProvider:
    def __init__(self, timeout_seconds: float = 5.0) -> None:
        self.timeout_seconds = timeout_seconds
        self.source = "yahoo-finance-public"

    def get_latest_prices(self, tickers: Iterable[str]) -> dict[str, MarketPrice]:
        normalized = _normalize_tickers(tickers)
        if not normalized:
            return {}

        url = self._build_url(normalized)
        try:
            payload = self._fetch_json(url)
        except (TimeoutError, HTTPError, URLError, ValueError) as exc:
            error = _format_provider_error(exc)
            return {
                ticker: MarketPrice(
                    ticker=ticker,
                    price=None,
                    currency=None,
                    source=self.source,
                    available=False,
                    error=error,
                )
                for ticker in normalized
            }

        quotes, response_error = _extract_yahoo_quote_results(payload)
        if response_error is not None:
            return {
                ticker: MarketPrice(
                    ticker=ticker,
                    price=None,
                    currency=None,
                    source=self.source,
                    available=False,
                    error=response_error,
                )
                for ticker in normalized
            }
        by_symbol = {
            item.get("symbol", "").upper(): item
            for item in quotes
            if isinstance(item, dict)
        }

        results: dict[str, MarketPrice] = {}
        for ticker in normalized:
            quote = by_symbol.get(ticker)
            if quote is None:
                results[ticker] = MarketPrice(
                    ticker=ticker,
                    price=None,
                    currency=None,
                    source=self.source,
                    available=False,
                    error="ticker not found in Yahoo response",
                )
                continue
            raw_price = quote.get("regularMarketPrice")
            price = _to_decimal(raw_price)
            currency = quote.get("currency")
            error = _quote_error(quote, price, currency)
            results[ticker] = MarketPrice(
                ticker=ticker,
                price=price if error is None else None,
                currency=currency if isinstance(currency, str) and currency else None,
                source=self.source,
                available=error is None,
                error=error,
            )
        return results

    def get_index_quote(self, symbol: str) -> IndexQuote:
        normalized_symbol = symbol.upper()
        provider_symbol = INDEX_SYMBOL_MAP.get(normalized_symbol, symbol)
        quotes = self.get_latest_prices([provider_symbol])
        quote = quotes[provider_symbol.upper()]
        return IndexQuote(
            symbol=normalized_symbol,
            price=quote.price,
            source=quote.source,
            available=quote.available,
            error=quote.error,
        )

    def _build_url(self, tickers: list[str]) -> str:
        encoded_symbols = quote(",".join(tickers), safe=",^")
        return f"https://query1.finance.yahoo.com/v7/finance/quote?symbols={encoded_symbols}"

    def _fetch_json(self, url: str) -> dict:
        try:
            with urlopen(url, timeout=self.timeout_seconds) as response:
                return json.loads(response.read().decode("utf-8"))
        except TimeoutError as exc:
            raise TimeoutError("market data request timed out") from exc

    def get_historical_prices(
        self,
        ticker: str,
        days: int = 250,
    ) -> tuple[HistoricalPriceBar, ...]:
        normalized = ticker.upper().strip()
        if not normalized or days <= 0:
            return ()
        url = (
            "https://query1.finance.yahoo.com/v8/finance/chart/"
            f"{quote(normalized, safe='^')}?range={days}d&interval=1d"
        )
        try:
            payload = self._fetch_json(url)
        except (TimeoutError, HTTPError, URLError, ValueError):
            return ()

        if not isinstance(payload, dict):
            return ()
        chart = payload.get("chart")
        if not isinstance(chart, dict):
            return ()
        result = chart.get("result", [])
        if not isinstance(result, list) or not result:
            return ()
        item = result[0]
        if not isinstance(item, dict):
            return ()
        timestamps = item.get("timestamp", [])
        if not isinstance(timestamps, list):
            return ()
        indicators = item.get("indicators")
        if not isinstance(indicators, dict):
            return ()
        quote_indicators = indicators.get("quote", [])
        if not isinstance(quote_indicators, list) or not quote_indicators:
            return ()
        quote_data = quote_indicators[0]
        if not isinstance(quote_data, dict):
            return ()
        closes = quote_data.get("close", [])
        volumes = quote_data.get("volume", [])
        if not isinstance(closes, list):
            return ()
        if not isinstance(volumes, list):
            volumes = []

        bars: list[HistoricalPriceBar] = []
        for index, timestamp in enumerate(timestamps):
            timestamp_value = _to_epoch_seconds(timestamp)
            if timestamp_value is None:
                continue

            close = _to_decimal(closes[index]) if index < len(closes) else None
            if close is None:
                continue
            raw_volume = volumes[index] if index < len(volumes) else None
            volume = _to_int(raw_volume)
            try:
                bar_date = datetime.fromtimestamp(
                    timestamp_value, tz=timezone.utc
                ).date()
            except (OverflowError, OSError, ValueError):
                continue
            bars.append(
                HistoricalPriceBar(
                    ticker=normalized,
                    date=bar_date.isoformat(),
                    close=close,
                    volume=volume,
                    source=self.source,
                )
            )
        return tuple(bars)


def _normalize_tickers(tickers: Iterable[str]) -> list[str]:
    return sorted({ticker.strip().upper() for ticker in tickers if ticker.strip()})


def _format_provider_error(exc: Exception) -> str:
    if isinstance(exc, TimeoutError):
        return "market data request timed out"
    if isinstance(exc, HTTPError):
        return f"Yahoo market data request failed with HTTP {exc.code}"
    if isinstance(exc, URLError):
        return "Yahoo market data request failed due to a network error"
    if isinstance(exc, ValueError):
        return "Yahoo market data response was invalid JSON"
    return "Yahoo market data request failed"


def _extract_yahoo_quote_results(payload: object) -> tuple[list[object], str | None]:
    if not isinstance(payload, dict):
        return [], "unexpected Yahoo quote response"
    quote_response = payload.get("quoteResponse")
    if not isinstance(quote_response, dict):
        return [], "malformed Yahoo quote response"
    if "result" not in quote_response:
        return [], "malformed Yahoo quote response: result missing"
    quotes = quote_response.get("result")
    if not isinstance(quotes, list):
        return [], "malformed Yahoo quote response: result is not a list"
    return quotes, None


def _quote_error(
    quote: dict[str, object], price: Decimal | None, currency: object
) -> str | None:
    if "regularMarketPrice" not in quote or quote.get("regularMarketPrice") is None:
        return "price missing in Yahoo response"
    if price is None:
        return "price invalid in Yahoo response"
    if not isinstance(currency, str) or not currency.strip():
        return "currency missing in Yahoo response"
    stale_error = _stale_quote_error(quote)
    if stale_error is not None:
        return stale_error
    return None


def _stale_quote_error(quote: dict[str, object]) -> str | None:
    timestamp = _to_epoch_seconds(quote.get("regularMarketTime"))
    if timestamp is None:
        return None
    now = int(datetime.now(timezone.utc).timestamp())
    if timestamp > now + 60 * 60:
        return "quote freshness timestamp is invalid"
    if now - timestamp <= STALE_QUOTE_SECONDS:
        return None
    date = datetime.fromtimestamp(timestamp, tz=timezone.utc).date().isoformat()
    return f"quote may be stale; last market time was {date}"


def _to_int(value: object) -> int | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return None
    if isinstance(value, float) and not math.isfinite(value):
        return None
    try:
        return int(value)
    except (TypeError, ValueError, OverflowError):
        return None


def _to_epoch_seconds(value: object) -> int | None:
    epoch_seconds = _to_int(value)
    if epoch_seconds is None or epoch_seconds <= 0:
        return None
    return epoch_seconds


def _to_decimal(value: object) -> Decimal | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return None
    if isinstance(value, float) and not math.isfinite(value):
        return None
    try:
        parsed = Decimal(str(value))
    except (InvalidOperation, ValueError):
        return None
    if not parsed.is_finite():
        return None
    return parsed


def build_market_data_provider(
    provider_name: str, timeout_seconds: float
) -> MarketDataProvider:
    normalized_provider = provider_name.strip().lower()
    if normalized_provider == "yahoo":
        return YahooMarketDataProvider(timeout_seconds=timeout_seconds)
    if normalized_provider == "static":
        return StaticMarketDataProvider()
    return StaticMarketDataProvider()


def fetch_portfolio_latest_prices(
    portfolio: Portfolio,
    provider: MarketDataProvider,
) -> tuple[dict[str, Decimal], list[str]]:
    tickers = sorted({holding.ticker.upper() for holding in portfolio.holdings})
    if not tickers:
        return {}, []

    prices = provider.get_latest_prices(tickers)
    available: dict[str, Decimal] = {}
    warnings: list[str] = []

    for ticker in tickers:
        item = prices.get(ticker)
        if item is None or not item.available or item.price is None:
            error = item.error if item is not None else "missing provider response"
            warnings.append(f"{ticker}: {error}")
            continue
        available[ticker] = item.price

    return available, warnings
