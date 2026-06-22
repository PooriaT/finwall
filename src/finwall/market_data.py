from __future__ import annotations

import json
import math
from dataclasses import dataclass, replace
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


@dataclass(frozen=True)
class FallbackProviderStatus:
    operation: str
    primary_provider: str
    fallback_provider: str
    fallback_attempted: bool
    fallback_succeeded: bool
    primary_failed: bool
    requested: tuple[str, ...]
    fulfilled_by_primary: tuple[str, ...]
    fulfilled_by_fallback: tuple[str, ...]
    unavailable: tuple[str, ...]
    safe_error: str | None = None

    def as_dict(self) -> dict[str, object]:
        return {
            "operation": self.operation,
            "primary_provider": self.primary_provider,
            "fallback_provider": self.fallback_provider,
            "fallback_attempted": self.fallback_attempted,
            "fallback_succeeded": self.fallback_succeeded,
            "primary_failed": self.primary_failed,
            "requested": list(self.requested),
            "fulfilled_by_primary": list(self.fulfilled_by_primary),
            "fulfilled_by_fallback": list(self.fulfilled_by_fallback),
            "unavailable": list(self.unavailable),
            "safe_error": self.safe_error,
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
    def __init__(
        self,
        prices: dict[str, MarketPrice] | None = None,
        index_quotes: dict[str, IndexQuote] | None = None,
        historical_prices: dict[str, tuple[HistoricalPriceBar, ...]] | None = None,
        configuration_warning: str | None = None,
    ) -> None:
        self.source = "static"
        self.configuration_warning = configuration_warning
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


class FallbackMarketDataProvider:
    def __init__(
        self,
        primary: MarketDataProvider,
        fallback: MarketDataProvider,
        *,
        source: str | None = None,
    ) -> None:
        self.primary = primary
        self.fallback = fallback
        self.primary_source = _provider_source(primary)
        self.fallback_source = _provider_source(fallback)
        self.source = (
            source
            if source is not None
            else f"fallback:{self.primary_source}->{self.fallback_source}"
        )
        self.latest_status: FallbackProviderStatus | None = None
        self.index_status: FallbackProviderStatus | None = None
        self.historical_status: FallbackProviderStatus | None = None

    def get_latest_prices(self, tickers: Iterable[str]) -> dict[str, MarketPrice]:
        normalized = _normalize_tickers(tickers)
        if not normalized:
            self.latest_status = _fallback_status(
                operation="latest_prices",
                primary_provider=self.primary_source,
                fallback_provider=self.fallback_source,
                requested=(),
            )
            return {}

        primary_error: str | None = None
        try:
            primary_prices = self.primary.get_latest_prices(normalized)
        except Exception:
            primary_prices = {}
            primary_error = "primary provider latest quote request failed"

        results: dict[str, MarketPrice] = {}
        missing: list[str] = []
        fulfilled_by_primary: list[str] = []
        for ticker in normalized:
            item = primary_prices.get(ticker)
            if _available_price(item):
                results[ticker] = item
                fulfilled_by_primary.append(ticker)
            else:
                missing.append(ticker)

        fallback_prices: dict[str, MarketPrice] = {}
        fallback_error: str | None = None
        if missing:
            try:
                fallback_prices = self.fallback.get_latest_prices(missing)
            except Exception:
                fallback_error = "fallback provider latest quote request failed"

        fulfilled_by_fallback: list[str] = []
        unavailable: list[str] = []
        for ticker in missing:
            fallback_item = fallback_prices.get(ticker)
            if _available_price(fallback_item):
                results[ticker] = replace(fallback_item, source=self.source)
                fulfilled_by_fallback.append(ticker)
                continue

            primary_item = primary_prices.get(ticker)
            error = _combined_provider_error(
                primary_provider=self.primary_source,
                primary_error=primary_error
                or _market_price_error(
                    primary_item, "missing primary provider response"
                ),
                fallback_provider=self.fallback_source,
                fallback_error=fallback_error
                or _market_price_error(
                    fallback_item, "missing fallback provider response"
                ),
            )
            results[ticker] = MarketPrice(
                ticker=ticker,
                price=None,
                currency=None,
                source=self.source,
                available=False,
                error=error,
            )
            unavailable.append(ticker)

        self.latest_status = _fallback_status(
            operation="latest_prices",
            primary_provider=self.primary_source,
            fallback_provider=self.fallback_source,
            requested=tuple(normalized),
            fallback_attempted=bool(missing),
            fallback_succeeded=bool(fulfilled_by_fallback),
            primary_failed=primary_error is not None
            or (bool(missing) and not fulfilled_by_primary),
            fulfilled_by_primary=tuple(fulfilled_by_primary),
            fulfilled_by_fallback=tuple(fulfilled_by_fallback),
            unavailable=tuple(unavailable),
            safe_error=(
                "latest prices unavailable from primary and fallback providers"
                if unavailable
                else None
            ),
        )
        return results

    def get_index_quote(self, symbol: str) -> IndexQuote:
        normalized = symbol.upper()
        primary_error: str | None = None
        try:
            primary_quote = self.primary.get_index_quote(symbol)
        except Exception:
            primary_quote = None
            primary_error = "primary provider index quote request failed"

        if _available_index_quote(primary_quote):
            self.index_status = _fallback_status(
                operation="index_quote",
                primary_provider=self.primary_source,
                fallback_provider=self.fallback_source,
                requested=(normalized,),
                fulfilled_by_primary=(normalized,),
            )
            return primary_quote

        fallback_error: str | None = None
        try:
            fallback_quote = self.fallback.get_index_quote(symbol)
        except Exception:
            fallback_quote = None
            fallback_error = "fallback provider index quote request failed"

        if _available_index_quote(fallback_quote):
            self.index_status = _fallback_status(
                operation="index_quote",
                primary_provider=self.primary_source,
                fallback_provider=self.fallback_source,
                requested=(normalized,),
                fallback_attempted=True,
                fallback_succeeded=True,
                primary_failed=primary_error is not None,
                fulfilled_by_fallback=(normalized,),
            )
            return replace(fallback_quote, source=self.source)

        error = _combined_provider_error(
            primary_provider=self.primary_source,
            primary_error=primary_error
            or _index_quote_error(primary_quote, "missing primary provider response"),
            fallback_provider=self.fallback_source,
            fallback_error=fallback_error
            or _index_quote_error(fallback_quote, "missing fallback provider response"),
        )
        self.index_status = _fallback_status(
            operation="index_quote",
            primary_provider=self.primary_source,
            fallback_provider=self.fallback_source,
            requested=(normalized,),
            fallback_attempted=True,
            primary_failed=primary_error is not None or primary_quote is None,
            unavailable=(normalized,),
            safe_error="index quote unavailable from primary and fallback providers",
        )
        return IndexQuote(
            symbol=normalized,
            price=None,
            source=self.source,
            available=False,
            error=error,
        )

    def get_historical_prices(
        self,
        ticker: str,
        days: int = 250,
    ) -> tuple[HistoricalPriceBar, ...]:
        normalized = ticker.upper().strip()
        if not normalized or days <= 0:
            self.historical_status = _fallback_status(
                operation="historical_prices",
                primary_provider=self.primary_source,
                fallback_provider=self.fallback_source,
                requested=tuple(filter(None, (normalized,))),
            )
            return ()

        primary_error: str | None = None
        try:
            primary_bars = self.primary.get_historical_prices(normalized, days=days)
        except Exception:
            primary_bars = ()
            primary_error = "primary provider historical price request failed"

        if primary_bars:
            self.historical_status = _fallback_status(
                operation="historical_prices",
                primary_provider=self.primary_source,
                fallback_provider=self.fallback_source,
                requested=(normalized,),
                fulfilled_by_primary=(normalized,),
            )
            return primary_bars

        fallback_error: str | None = None
        try:
            fallback_bars = self.fallback.get_historical_prices(normalized, days=days)
        except Exception:
            fallback_bars = ()
            fallback_error = "fallback provider historical price request failed"

        if fallback_bars:
            self.historical_status = _fallback_status(
                operation="historical_prices",
                primary_provider=self.primary_source,
                fallback_provider=self.fallback_source,
                requested=(normalized,),
                fallback_attempted=True,
                fallback_succeeded=True,
                primary_failed=primary_error is not None,
                fulfilled_by_fallback=(normalized,),
            )
            return tuple(replace(bar, source=self.source) for bar in fallback_bars)

        self.historical_status = _fallback_status(
            operation="historical_prices",
            primary_provider=self.primary_source,
            fallback_provider=self.fallback_source,
            requested=(normalized,),
            fallback_attempted=True,
            primary_failed=primary_error is not None,
            unavailable=(normalized,),
            safe_error=(
                fallback_error
                or "historical prices unavailable from primary and fallback providers"
            ),
        )
        return ()


def _normalize_tickers(tickers: Iterable[str]) -> list[str]:
    return sorted({ticker.strip().upper() for ticker in tickers if ticker.strip()})


def _provider_source(provider: object) -> str:
    source = getattr(provider, "source", None)
    if isinstance(source, str) and source.strip():
        return source.strip()
    return provider.__class__.__name__


def _available_price(item: MarketPrice | None) -> bool:
    return item is not None and item.available and item.price is not None


def _available_index_quote(item: IndexQuote | None) -> bool:
    return item is not None and item.available and item.price is not None


def _market_price_error(item: MarketPrice | None, default: str) -> str:
    return _safe_provider_message(item.error if item is not None else None, default)


def _index_quote_error(item: IndexQuote | None, default: str) -> str:
    return _safe_provider_message(item.error if item is not None else None, default)


def _safe_provider_message(value: str | None, default: str) -> str:
    if value is None or not value.strip():
        return default
    lowered = value.lower()
    if any(marker in lowered for marker in ("http://", "https://", "traceback")):
        return default
    if "\n" in value or "\r" in value:
        return default
    return value


def _combined_provider_error(
    *,
    primary_provider: str,
    primary_error: str,
    fallback_provider: str,
    fallback_error: str,
) -> str:
    return (
        f"primary {primary_provider}: {primary_error}; "
        f"fallback {fallback_provider}: {fallback_error}"
    )


def _fallback_status(
    *,
    operation: str,
    primary_provider: str,
    fallback_provider: str,
    requested: tuple[str, ...],
    fallback_attempted: bool = False,
    fallback_succeeded: bool = False,
    primary_failed: bool = False,
    fulfilled_by_primary: tuple[str, ...] = (),
    fulfilled_by_fallback: tuple[str, ...] = (),
    unavailable: tuple[str, ...] = (),
    safe_error: str | None = None,
) -> FallbackProviderStatus:
    return FallbackProviderStatus(
        operation=operation,
        primary_provider=primary_provider,
        fallback_provider=fallback_provider,
        fallback_attempted=fallback_attempted,
        fallback_succeeded=fallback_succeeded,
        primary_failed=primary_failed,
        requested=requested,
        fulfilled_by_primary=fulfilled_by_primary,
        fulfilled_by_fallback=fulfilled_by_fallback,
        unavailable=unavailable,
        safe_error=safe_error,
    )


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
    if normalized_provider == "yfinance":
        from finwall.market_data_yfinance import YFinanceMarketDataProvider

        primary = YFinanceMarketDataProvider(timeout_seconds=timeout_seconds)
        fallback = YahooMarketDataProvider(timeout_seconds=timeout_seconds)
        return FallbackMarketDataProvider(primary, fallback)
    if normalized_provider == "static":
        return StaticMarketDataProvider()
    provider = provider_name.strip() or "<empty>"
    return StaticMarketDataProvider(
        configuration_warning=(
            f"unknown market data provider {provider!r}; using static provider"
        )
    )


def fetch_portfolio_latest_prices(
    portfolio: Portfolio,
    provider: MarketDataProvider,
) -> tuple[dict[str, Decimal], list[str]]:
    tickers = sorted({holding.ticker.upper() for holding in portfolio.holdings})
    if not tickers:
        return {}, []

    warnings: list[str] = []
    configuration_warning = getattr(provider, "configuration_warning", None)
    if isinstance(configuration_warning, str) and configuration_warning.strip():
        warnings.append(configuration_warning.strip())

    try:
        prices = provider.get_latest_prices(tickers)
    except Exception:
        return {}, [
            *warnings,
            "market data provider failed while fetching latest prices",
            *[
                f"{ticker}: market data provider latest quote request failed"
                for ticker in tickers
            ],
        ]

    available: dict[str, Decimal] = {}
    status = getattr(provider, "latest_status", None)
    if isinstance(status, FallbackProviderStatus):
        warnings.extend(_fallback_warnings(status))

    for ticker in tickers:
        item = prices.get(ticker)
        if item is None or not item.available or item.price is None:
            error = item.error if item is not None else "missing provider response"
            warnings.append(f"{ticker}: {error}")
            continue
        available[ticker] = item.price

    return available, warnings


def _fallback_warnings(status: FallbackProviderStatus) -> list[str]:
    if not status.fallback_attempted:
        return []

    warnings: list[str] = []
    if status.fallback_succeeded:
        tickers = ", ".join(status.fulfilled_by_fallback)
        if status.primary_failed:
            warnings.append(
                "market data fallback used: "
                f"primary {status.primary_provider} unavailable; "
                f"fallback {status.fallback_provider} succeeded"
            )
        else:
            warnings.append(
                "market data fallback used for "
                f"{tickers}: primary {status.primary_provider} returned partial prices; "
                f"fallback {status.fallback_provider} filled missing prices"
            )
    else:
        warnings.append(
            "market data fallback failed: "
            f"primary {status.primary_provider} and fallback "
            f"{status.fallback_provider} unavailable"
        )

    if status.unavailable:
        warnings.append(
            "market data fallback returned partial prices: unavailable "
            + ", ".join(status.unavailable)
        )
    return warnings
