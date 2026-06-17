from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from finwall.market_data import (
    MarketDataProvider,
    build_market_data_provider,
)

RECOGNIZED_MARKET_DATA_PROVIDERS = {"static", "yahoo", "yfinance"}


@dataclass(frozen=True)
class MarketDataDiagnosticCheck:
    name: str
    ok: bool
    summary: str
    details: dict[str, object]

    def as_dict(self) -> dict[str, object]:
        return {
            "name": self.name,
            "ok": self.ok,
            "summary": self.summary,
            "details": self.details,
        }


@dataclass(frozen=True)
class MarketDataDiagnosticResult:
    ok: bool
    provider: str
    timeout_seconds: float
    sample_ticker: str
    historical_days: int
    checks: tuple[MarketDataDiagnosticCheck, ...]

    def as_dict(self) -> dict[str, object]:
        return {
            "ok": self.ok,
            "provider": self.provider,
            "timeout_seconds": self.timeout_seconds,
            "sample_ticker": self.sample_ticker,
            "historical_days": self.historical_days,
            "checks": [check.as_dict() for check in self.checks],
        }


def run_market_data_diagnostics(
    *,
    provider_name: str,
    timeout_seconds: float,
    sample_ticker: str,
    historical_days: int,
    provider: MarketDataProvider | None = None,
) -> MarketDataDiagnosticResult:
    normalized_provider = provider_name.strip().lower()
    effective_provider = (
        normalized_provider
        if normalized_provider in RECOGNIZED_MARKET_DATA_PROVIDERS
        else "static"
    )
    ticker = sample_ticker.strip().upper()
    provider_instance = provider or build_market_data_provider(
        provider_name,
        timeout_seconds,
    )

    checks = (
        _check_provider_configuration(
            configured_provider=provider_name,
            normalized_provider=normalized_provider,
            effective_provider=effective_provider,
            timeout_seconds=timeout_seconds,
        ),
        _check_latest_quote(provider_instance, ticker),
        _check_historical_prices(provider_instance, ticker, historical_days),
    )
    return MarketDataDiagnosticResult(
        ok=all(check.ok for check in checks),
        provider=normalized_provider,
        timeout_seconds=timeout_seconds,
        sample_ticker=ticker,
        historical_days=historical_days,
        checks=checks,
    )


def _check_provider_configuration(
    *,
    configured_provider: str,
    normalized_provider: str,
    effective_provider: str,
    timeout_seconds: float,
) -> MarketDataDiagnosticCheck:
    recognized = normalized_provider in RECOGNIZED_MARKET_DATA_PROVIDERS
    if recognized:
        summary = f"provider {normalized_provider} configured"
    else:
        summary = (
            f"provider {normalized_provider or '<empty>'} is not recognized; "
            "using static fallback"
        )
    return MarketDataDiagnosticCheck(
        name="provider_configuration",
        ok=recognized,
        summary=summary,
        details={
            "configured_provider": configured_provider,
            "provider": normalized_provider,
            "effective_provider": effective_provider,
            "recognized": recognized,
            "timeout_seconds": timeout_seconds,
        },
    )


def _check_latest_quote(
    provider: MarketDataProvider,
    ticker: str,
) -> MarketDataDiagnosticCheck:
    try:
        prices = provider.get_latest_prices([ticker])
    except Exception:
        return MarketDataDiagnosticCheck(
            name="latest_quote",
            ok=False,
            summary=f"{ticker} unavailable: latest quote check failed",
            details={
                "ticker": ticker,
                "safe_error": "latest quote check failed",
            },
        )

    quote = prices.get(ticker)
    if quote is not None and quote.available and quote.price is not None:
        return MarketDataDiagnosticCheck(
            name="latest_quote",
            ok=True,
            summary=f"{ticker} price available from {quote.source}",
            details={
                "ticker": ticker,
                "source": quote.source,
                "currency": quote.currency,
                "price": _decimal_as_string(quote.price),
            },
        )

    safe_error = (
        quote.error
        if quote is not None and quote.error
        else "missing provider response"
    )
    source = quote.source if quote is not None else None
    return MarketDataDiagnosticCheck(
        name="latest_quote",
        ok=False,
        summary=f"{ticker} unavailable: {safe_error}",
        details={
            "ticker": ticker,
            "source": source,
            "safe_error": safe_error,
        },
    )


def _check_historical_prices(
    provider: MarketDataProvider,
    ticker: str,
    days: int,
) -> MarketDataDiagnosticCheck:
    try:
        bars = provider.get_historical_prices(ticker, days=days)
    except Exception:
        return MarketDataDiagnosticCheck(
            name="historical_prices",
            ok=False,
            summary="historical prices unavailable: historical price check failed",
            details={
                "ticker": ticker,
                "requested_days": days,
                "safe_error": "historical price check failed",
            },
        )

    if bars:
        return MarketDataDiagnosticCheck(
            name="historical_prices",
            ok=True,
            summary=f"{len(bars)} bars returned",
            details={
                "ticker": ticker,
                "source": bars[-1].source,
                "requested_days": days,
                "returned_bars": len(bars),
                "first_date": bars[0].date,
                "last_date": bars[-1].date,
            },
        )

    safe_message = "no historical bars returned"
    return MarketDataDiagnosticCheck(
        name="historical_prices",
        ok=False,
        summary=safe_message,
        details={
            "ticker": ticker,
            "requested_days": days,
            "returned_bars": 0,
            "safe_message": safe_message,
        },
    )


def _decimal_as_string(value: Decimal) -> str:
    return str(value)
