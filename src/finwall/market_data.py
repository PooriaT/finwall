from __future__ import annotations

import json
import logging
import math
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from enum import StrEnum
from typing import Iterable, Protocol
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import urlopen

from finwall.models import Portfolio

logger = logging.getLogger(__name__)

INDEX_SYMBOL_MAP = {
    "SP500": "^GSPC",
    "NASDAQ": "^IXIC",
}


class MarketDataOperation(StrEnum):
    LATEST_PRICES = "latest_prices"
    INDEX_QUOTE = "index_quote"
    HISTORICAL_PRICES = "historical_prices"


class MarketDataErrorCode(StrEnum):
    INVALID_INPUT = "invalid_input"
    TIMEOUT = "timeout"
    HTTP_ERROR = "http_error"
    RATE_LIMITED = "rate_limited"
    NETWORK_ERROR = "network_error"
    MALFORMED_RESPONSE = "malformed_response"
    MISSING_SYMBOL = "missing_symbol"
    MISSING_PRICE = "missing_price"
    MISSING_HISTORICAL_DATA = "missing_historical_data"
    UNSUPPORTED_PROVIDER = "unsupported_provider"
    UNKNOWN = "unknown"


class MarketDataSeverity(StrEnum):
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"


@dataclass(frozen=True)
class MarketDataDiagnostic:
    provider: str
    operation: str
    symbol: str | None
    code: str
    severity: str
    user_message: str
    debug_message: str | None = None
    http_status: int | None = None
    retryable: bool = False

    def as_dict(self) -> dict[str, object]:
        return {
            "provider": self.provider,
            "operation": self.operation,
            "symbol": self.symbol,
            "code": self.code,
            "severity": self.severity,
            "user_message": self.user_message,
            "debug_message": self.debug_message,
            "http_status": self.http_status,
            "retryable": self.retryable,
        }


@dataclass(frozen=True)
class MarketPrice:
    ticker: str
    price: Decimal | None
    currency: str | None
    source: str
    available: bool
    error: str | None = None
    error_code: str | None = None
    diagnostic: MarketDataDiagnostic | None = None


@dataclass(frozen=True)
class IndexQuote:
    symbol: str
    price: Decimal | None
    source: str
    available: bool
    error: str | None = None
    error_code: str | None = None
    diagnostic: MarketDataDiagnostic | None = None


@dataclass(frozen=True)
class HistoricalPriceBar:
    ticker: str
    date: str
    close: Decimal | None
    volume: int | None
    source: str


@dataclass(frozen=True)
class HistoricalPriceResult:
    ticker: str
    bars: tuple[HistoricalPriceBar, ...]
    source: str
    available: bool
    error: str | None = None
    error_code: str | None = None
    diagnostics: tuple[MarketDataDiagnostic, ...] = ()

    def as_dict(self) -> dict[str, object]:
        return {
            "ticker": self.ticker,
            "bars": [
                {
                    "ticker": bar.ticker,
                    "date": bar.date,
                    "close": str(bar.close) if bar.close is not None else None,
                    "volume": bar.volume,
                    "source": bar.source,
                }
                for bar in self.bars
            ],
            "source": self.source,
            "available": self.available,
            "error": self.error,
            "error_code": self.error_code,
            "diagnostics": [item.as_dict() for item in self.diagnostics],
        }


class MarketDataProvider(Protocol):
    def get_latest_prices(self, tickers: Iterable[str]) -> dict[str, MarketPrice]: ...

    def get_index_quote(self, symbol: str) -> IndexQuote: ...

    def get_historical_prices(
        self,
        ticker: str,
        days: int = 250,
    ) -> tuple[HistoricalPriceBar, ...]: ...


class StaticMarketDataProvider:
    def __init__(self, prices=None, index_quotes=None, historical_prices=None) -> None:
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
        self.source = "static"

    def get_latest_prices(self, tickers: Iterable[str]) -> dict[str, MarketPrice]:
        results = {}
        for raw_ticker in tickers:
            ticker = raw_ticker.upper()
            results[ticker] = self._prices.get(ticker) or self._missing_price(ticker)
        return results

    def get_index_quote(self, symbol: str) -> IndexQuote:
        key = symbol.upper()
        return self._index_quotes.get(key) or self._missing_index(key)

    def get_historical_price_result(
        self, ticker: str, days: int = 250
    ) -> HistoricalPriceResult:
        normalized = ticker.upper().strip()
        if not normalized or days <= 0:
            diagnostic = self._diagnostic(
                MarketDataOperation.HISTORICAL_PRICES,
                normalized or None,
                MarketDataErrorCode.INVALID_INPUT,
                "invalid historical price input",
            )
            return HistoricalPriceResult(
                normalized,
                (),
                self.source,
                False,
                diagnostic.user_message,
                diagnostic.code,
                (diagnostic,),
            )
        bars = self._historical_prices.get(normalized)
        if bars is None:
            diagnostic = self._diagnostic(
                MarketDataOperation.HISTORICAL_PRICES,
                normalized,
                MarketDataErrorCode.MISSING_HISTORICAL_DATA,
                "historical prices not configured",
            )
            return HistoricalPriceResult(
                normalized,
                (),
                self.source,
                False,
                diagnostic.user_message,
                diagnostic.code,
                (diagnostic,),
            )
        trimmed = bars[-days:]
        return HistoricalPriceResult(
            normalized, trimmed, self.source, bool(trimmed), None, None, ()
        )

    def get_historical_prices(
        self, ticker: str, days: int = 250
    ) -> tuple[HistoricalPriceBar, ...]:
        return self.get_historical_price_result(ticker, days).bars

    def _diagnostic(self, operation, symbol, code, msg):
        return MarketDataDiagnostic(
            self.source, operation, symbol, code, MarketDataSeverity.WARNING, msg
        )

    def _missing_price(self, ticker: str) -> MarketPrice:
        d = self._diagnostic(
            MarketDataOperation.LATEST_PRICES,
            ticker,
            MarketDataErrorCode.MISSING_PRICE,
            "latest price not configured",
        )
        return MarketPrice(
            ticker, None, None, self.source, False, d.user_message, d.code, d
        )

    def _missing_index(self, symbol: str) -> IndexQuote:
        d = self._diagnostic(
            MarketDataOperation.INDEX_QUOTE,
            symbol,
            MarketDataErrorCode.MISSING_SYMBOL,
            "index quote not configured",
        )
        return IndexQuote(symbol, None, self.source, False, d.user_message, d.code, d)


class YahooMarketDataProvider:
    def __init__(self, timeout_seconds: float = 5.0) -> None:
        self.timeout_seconds = timeout_seconds
        self.source = "yahoo-finance-public"

    def get_latest_prices(self, tickers: Iterable[str]) -> dict[str, MarketPrice]:
        normalized = sorted({ticker.upper() for ticker in tickers if ticker.strip()})
        if not normalized:
            return {}
        try:
            payload = self._fetch_json(self._build_url(normalized))
        except (TimeoutError, HTTPError, URLError, ValueError) as exc:
            d = self._classify_exception(MarketDataOperation.LATEST_PRICES, None, exc)
            return {
                t: MarketPrice(
                    t, None, None, self.source, False, d.user_message, d.code, d
                )
                for t in normalized
            }

        try:
            quotes = payload["quoteResponse"]["result"]
        except (KeyError, TypeError):
            d = self._diagnostic(
                MarketDataOperation.LATEST_PRICES,
                None,
                MarketDataErrorCode.MALFORMED_RESPONSE,
                "provider returned malformed latest price response",
                False,
            )
            return {
                t: MarketPrice(
                    t, None, None, self.source, False, d.user_message, d.code, d
                )
                for t in normalized
            }

        by_symbol = {
            item.get("symbol", "").upper(): item
            for item in quotes
            if isinstance(item, dict)
        }
        results = {}
        for ticker in normalized:
            quote = by_symbol.get(ticker)
            if quote is None:
                d = self._diagnostic(
                    MarketDataOperation.LATEST_PRICES,
                    ticker,
                    MarketDataErrorCode.MISSING_SYMBOL,
                    "ticker not found in provider response",
                    False,
                )
                results[ticker] = MarketPrice(
                    ticker, None, None, self.source, False, d.user_message, d.code, d
                )
                continue
            price = _to_decimal(quote.get("regularMarketPrice"))
            currency = quote.get("currency")
            if price is None:
                d = self._diagnostic(
                    MarketDataOperation.LATEST_PRICES,
                    ticker,
                    MarketDataErrorCode.MISSING_PRICE,
                    "latest price missing from provider response",
                    False,
                )
                results[ticker] = MarketPrice(
                    ticker,
                    None,
                    currency,
                    self.source,
                    False,
                    d.user_message,
                    d.code,
                    d,
                )
                continue
            results[ticker] = MarketPrice(ticker, price, currency, self.source, True)
        return results

    def get_index_quote(self, symbol: str) -> IndexQuote:
        normalized_symbol = symbol.upper()
        provider_symbol = INDEX_SYMBOL_MAP.get(normalized_symbol, symbol)
        quote = self.get_latest_prices([provider_symbol])[provider_symbol.upper()]
        return IndexQuote(
            normalized_symbol,
            quote.price,
            quote.source,
            quote.available,
            quote.error,
            quote.error_code,
            quote.diagnostic,
        )

    def get_historical_price_result(
        self, ticker: str, days: int = 250
    ) -> HistoricalPriceResult:
        normalized = ticker.upper().strip()
        if not normalized or days <= 0:
            d = self._diagnostic(
                MarketDataOperation.HISTORICAL_PRICES,
                normalized or None,
                MarketDataErrorCode.INVALID_INPUT,
                "invalid historical price input",
                False,
            )
            return HistoricalPriceResult(
                normalized, (), self.source, False, d.user_message, d.code, (d,)
            )
        url = (
            "https://query1.finance.yahoo.com/v8/finance/chart/"
            f"{quote(normalized, safe='^')}?range={days}d&interval=1d"
        )
        try:
            payload = self._fetch_json(url)
        except (TimeoutError, HTTPError, URLError, ValueError) as exc:
            d = self._classify_exception(
                MarketDataOperation.HISTORICAL_PRICES, normalized, exc
            )
            return HistoricalPriceResult(
                normalized, (), self.source, False, d.user_message, d.code, (d,)
            )
        result = payload.get("chart", {}).get("result")
        if not result:
            d = self._diagnostic(
                MarketDataOperation.HISTORICAL_PRICES,
                normalized,
                MarketDataErrorCode.MALFORMED_RESPONSE,
                "provider returned no chart result",
                False,
            )
            return HistoricalPriceResult(
                normalized, (), self.source, False, d.user_message, d.code, (d,)
            )
        item = result[0] if isinstance(result, list) else None
        timestamps = (item or {}).get("timestamp")
        indicators = (item or {}).get("indicators", {}).get("quote", [])
        quote_data = indicators[0] if indicators else {}
        closes = quote_data.get("close")
        volumes = quote_data.get("volume")
        if not isinstance(timestamps, list) or not isinstance(closes, list):
            d = self._diagnostic(
                MarketDataOperation.HISTORICAL_PRICES,
                normalized,
                MarketDataErrorCode.MALFORMED_RESPONSE,
                "provider returned malformed historical price response",
                False,
            )
            return HistoricalPriceResult(
                normalized, (), self.source, False, d.user_message, d.code, (d,)
            )
        volumes = volumes if isinstance(volumes, list) else []
        bars = []
        for i, ts in enumerate(timestamps):
            tsv = _to_epoch_seconds(ts)
            if tsv is None:
                continue
            bar_date = (
                __import__("datetime")
                .datetime.fromtimestamp(tsv, tz=__import__("datetime").timezone.utc)
                .date()
                .isoformat()
            )
            bars.append(
                HistoricalPriceBar(
                    normalized,
                    bar_date,
                    _to_decimal(closes[i]) if i < len(closes) else None,
                    _to_int(volumes[i]) if i < len(volumes) else None,
                    self.source,
                )
            )
        if not bars:
            d = self._diagnostic(
                MarketDataOperation.HISTORICAL_PRICES,
                normalized,
                MarketDataErrorCode.MISSING_HISTORICAL_DATA,
                "no valid historical bars in provider response",
                False,
            )
            return HistoricalPriceResult(
                normalized, (), self.source, False, d.user_message, d.code, (d,)
            )
        return HistoricalPriceResult(normalized, tuple(bars), self.source, True)

    def get_historical_prices(
        self, ticker: str, days: int = 250
    ) -> tuple[HistoricalPriceBar, ...]:
        return self.get_historical_price_result(ticker, days).bars

    def _build_url(self, tickers: list[str]) -> str:
        encoded = quote(",".join(tickers), safe=",^")
        return f"https://query1.finance.yahoo.com/v7/finance/quote?symbols={encoded}"

    def _fetch_json(self, url: str) -> dict:
        try:
            with urlopen(url, timeout=self.timeout_seconds) as response:
                return json.loads(response.read().decode("utf-8"))
        except TimeoutError as exc:
            raise TimeoutError("market data request timed out") from exc

    def _diagnostic(
        self,
        operation,
        symbol,
        code,
        user_message,
        retryable,
        http_status=None,
        debug_message=None,
    ):
        d = MarketDataDiagnostic(
            self.source,
            operation,
            symbol,
            code,
            MarketDataSeverity.WARNING,
            user_message,
            debug_message,
            http_status,
            retryable,
        )
        logger.warning(
            "market_data_failure provider=%s operation=%s symbol=%s code=%s retryable=%s",
            d.provider,
            d.operation,
            d.symbol,
            d.code,
            d.retryable,
        )
        return d

    def _classify_exception(self, operation, symbol, exc):
        if isinstance(exc, TimeoutError):
            return self._diagnostic(
                operation,
                symbol,
                MarketDataErrorCode.TIMEOUT,
                "provider timed out while fetching market data",
                True,
            )
        if isinstance(exc, HTTPError):
            if exc.code == 429:
                return self._diagnostic(
                    operation,
                    symbol,
                    MarketDataErrorCode.RATE_LIMITED,
                    "provider rate limited the request",
                    True,
                    exc.code,
                )
            retryable = 500 <= exc.code <= 599
            return self._diagnostic(
                operation,
                symbol,
                MarketDataErrorCode.HTTP_ERROR,
                "provider returned an HTTP error",
                retryable,
                exc.code,
            )
        if isinstance(exc, URLError):
            return self._diagnostic(
                operation,
                symbol,
                MarketDataErrorCode.NETWORK_ERROR,
                "network error while reaching market data provider",
                True,
            )
        return self._diagnostic(
            operation,
            symbol,
            MarketDataErrorCode.MALFORMED_RESPONSE,
            "provider returned malformed response",
            False,
        )


def _to_int(value: object) -> int | None:
    if (
        value is None
        or isinstance(value, bool)
        or (isinstance(value, float) and not math.isfinite(value))
    ):
        return None
    try:
        return int(value)
    except (TypeError, ValueError, OverflowError):
        return None


def _to_epoch_seconds(value: object) -> int | None:
    return _to_int(value)


def _to_decimal(value: object) -> Decimal | None:
    if value is None:
        return None
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError):
        return None


def build_market_data_provider(
    provider_name: str, timeout_seconds: float
) -> MarketDataProvider:
    if provider_name == "yahoo":
        return YahooMarketDataProvider(timeout_seconds=timeout_seconds)
    return StaticMarketDataProvider()


def fetch_portfolio_latest_prices(
    portfolio: Portfolio, provider: MarketDataProvider
) -> tuple[dict[str, Decimal], list[str]]:
    tickers = sorted({holding.ticker.upper() for holding in portfolio.holdings})
    if not tickers:
        return {}, []
    prices = provider.get_latest_prices(tickers)
    available = {}
    warnings = []
    for ticker in tickers:
        item = prices.get(ticker)
        if item is None or not item.available or item.price is None:
            warnings.append(
                f"{ticker}: {(item.error if item else 'missing provider response')}"
            )
            continue
        available[ticker] = item.price
    return available, warnings
