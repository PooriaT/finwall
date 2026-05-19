from __future__ import annotations

import json
from dataclasses import dataclass
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


class MarketDataProvider(Protocol):
    def get_latest_prices(self, tickers: Iterable[str]) -> dict[str, MarketPrice]: ...

    def get_index_quote(self, symbol: str) -> IndexQuote: ...


class StaticMarketDataProvider:
    def __init__(
        self,
        prices: dict[str, MarketPrice] | None = None,
        index_quotes: dict[str, IndexQuote] | None = None,
    ) -> None:
        self._prices = {
            ticker.upper(): value for ticker, value in (prices or {}).items()
        }
        self._index_quotes = {
            symbol.upper(): value for symbol, value in (index_quotes or {}).items()
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


class YahooMarketDataProvider:
    def __init__(self, timeout_seconds: float = 5.0) -> None:
        self.timeout_seconds = timeout_seconds
        self.source = "yahoo-finance-public"

    def get_latest_prices(self, tickers: Iterable[str]) -> dict[str, MarketPrice]:
        normalized = sorted({ticker.upper() for ticker in tickers if ticker.strip()})
        if not normalized:
            return {}

        url = self._build_url(normalized)
        try:
            payload = self._fetch_json(url)
        except (TimeoutError, HTTPError, URLError, ValueError) as exc:
            return {
                ticker: MarketPrice(
                    ticker=ticker,
                    price=None,
                    currency=None,
                    source=self.source,
                    available=False,
                    error=str(exc),
                )
                for ticker in normalized
            }

        quotes = payload.get("quoteResponse", {}).get("result", [])
        by_symbol = {item.get("symbol", "").upper(): item for item in quotes}

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
                    error="ticker not found in response",
                )
                continue
            price = _to_decimal(quote.get("regularMarketPrice"))
            currency = quote.get("currency")
            results[ticker] = MarketPrice(
                ticker=ticker,
                price=price,
                currency=currency,
                source=self.source,
                available=price is not None,
                error=None if price is not None else "price missing in response",
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
    if provider_name == "static":
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
