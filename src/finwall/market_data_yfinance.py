from __future__ import annotations

import importlib
from datetime import date, datetime
from decimal import Decimal
from typing import Iterable

from finwall.market_data import (
    INDEX_SYMBOL_MAP,
    HistoricalPriceBar,
    IndexQuote,
    MarketPrice,
    _normalize_tickers,
    _to_decimal,
    _to_int,
)


class YFinanceMarketDataProvider:
    def __init__(self, timeout_seconds: float = 5.0) -> None:
        self.timeout_seconds = timeout_seconds
        self.source = "yfinance"

    def get_latest_prices(self, tickers: Iterable[str]) -> dict[str, MarketPrice]:
        normalized = _normalize_tickers(tickers)
        if not normalized:
            return {}

        yfinance, import_error = _load_yfinance()
        if yfinance is None:
            return {
                ticker: _unavailable_price(ticker, self.source, import_error)
                for ticker in normalized
            }

        results: dict[str, MarketPrice] = {}
        for ticker in normalized:
            try:
                ticker_data = yfinance.Ticker(ticker)
                quote = _extract_latest_quote(ticker_data, self.timeout_seconds)
            except Exception:
                results[ticker] = _unavailable_price(
                    ticker, self.source, "yfinance latest quote request failed"
                )
                continue

            if quote.price is None:
                results[ticker] = _unavailable_price(
                    ticker, self.source, "price missing in yfinance response"
                )
                continue
            results[ticker] = MarketPrice(
                ticker=ticker,
                price=quote.price,
                currency=quote.currency,
                source=self.source,
                available=True,
                error=None,
            )
        return results

    def get_index_quote(self, symbol: str) -> IndexQuote:
        normalized_symbol = symbol.upper()
        provider_symbol = INDEX_SYMBOL_MAP.get(normalized_symbol, symbol)
        quotes = self.get_latest_prices([provider_symbol])
        quote = quotes.get(provider_symbol.upper())
        if quote is None:
            return IndexQuote(
                symbol=normalized_symbol,
                price=None,
                source=self.source,
                available=False,
                error="missing provider response",
            )
        return IndexQuote(
            symbol=normalized_symbol,
            price=quote.price,
            source=quote.source,
            available=quote.available,
            error=quote.error,
        )

    def get_historical_prices(
        self,
        ticker: str,
        days: int = 250,
    ) -> tuple[HistoricalPriceBar, ...]:
        normalized = ticker.upper().strip()
        if not normalized or days <= 0:
            return ()

        yfinance, _import_error = _load_yfinance()
        if yfinance is None:
            return ()

        try:
            ticker_data = yfinance.Ticker(normalized)
            history = ticker_data.history(
                period=f"{days}d",
                interval="1d",
                auto_adjust=False,
                timeout=self.timeout_seconds,
            )
        except Exception:
            return ()

        return _history_to_bars(normalized, history, self.source)


class _LatestQuote:
    def __init__(self, price: Decimal | None, currency: str | None) -> None:
        self.price = price
        self.currency = currency


def _load_yfinance() -> tuple[object | None, str | None]:
    try:
        return importlib.import_module("yfinance"), None
    except ImportError:
        return (
            None,
            "yfinance is not installed; install the optional yfinance extra",
        )


def _unavailable_price(ticker: str, source: str, error: str | None) -> MarketPrice:
    return MarketPrice(
        ticker=ticker,
        price=None,
        currency=None,
        source=source,
        available=False,
        error=error or "yfinance provider unavailable",
    )


def _extract_latest_quote(ticker_data: object, timeout_seconds: float) -> _LatestQuote:
    history = ticker_data.history(
        period="5d",
        interval="1d",
        auto_adjust=False,
        timeout=timeout_seconds,
    )
    bars = _history_to_bars("", history, "")
    if not bars:
        return _LatestQuote(None, _history_currency(history))
    return _LatestQuote(bars[-1].close, _history_currency(history))


def _first_string(container: object, keys: tuple[str, ...]) -> str | None:
    for key in keys:
        value = _get_value(container, key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def _history_currency(history: object) -> str | None:
    attrs = getattr(history, "attrs", None)
    currency = _first_string(attrs, ("currency", "Currency"))
    if currency is not None:
        return currency
    metadata = getattr(history, "metadata", None)
    return _first_string(metadata, ("currency", "Currency"))


def _get_value(container: object, key: str) -> object:
    if container is None:
        return None
    if isinstance(container, dict):
        return container.get(key)
    try:
        return container[key]  # type: ignore[index]
    except (KeyError, TypeError, AttributeError):
        return getattr(container, key, None)


def _history_to_bars(
    ticker: str,
    history: object,
    source: str,
) -> tuple[HistoricalPriceBar, ...]:
    if getattr(history, "empty", False):
        return ()
    iterrows = getattr(history, "iterrows", None)
    if not callable(iterrows):
        return ()

    bars: list[HistoricalPriceBar] = []
    try:
        rows = iterrows()
    except Exception:
        return ()

    for row_date, row in rows:
        close = _to_decimal(_get_value(row, "Close"))
        if close is None:
            continue
        bar_date = _format_history_date(row_date)
        if bar_date is None:
            continue
        bars.append(
            HistoricalPriceBar(
                ticker=ticker,
                date=bar_date,
                close=close,
                volume=_to_int(_get_value(row, "Volume")),
                source=source,
            )
        )
    return tuple(bars)


def _format_history_date(value: object) -> str | None:
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, date):
        return value.isoformat()

    date_method = getattr(value, "date", None)
    if callable(date_method):
        try:
            parsed = date_method()
        except Exception:
            parsed = None
        if isinstance(parsed, date):
            return parsed.isoformat()

    if isinstance(value, str):
        stripped = value.strip()
        if stripped:
            return stripped[:10]
    return None
