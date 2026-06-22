from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import StrEnum
from typing import Iterable

from finwall.fundamentals import FundamentalAnalysisReport
from finwall.market_condition import MarketConditionReport
from finwall.market_data_diagnostics import MarketDataDiagnosticResult
from finwall.news import NewsReport
from finwall.snapshot import PortfolioSnapshot


class LiveDataDomain(StrEnum):
    MARKET_PRICES = "market_prices"
    MARKET_INDEXES = "market_indexes"
    TECHNICALS = "technicals"
    FUNDAMENTALS = "fundamentals"
    NEWS = "news"
    MARKET_CONDITION = "market_condition"


class LiveDataAvailability(StrEnum):
    LIVE = "live"
    PARTIAL = "partial"
    UNAVAILABLE = "unavailable"
    STATIC = "static"
    MANUAL = "manual"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class LiveDataStatus:
    domain: str
    provider: str
    source: str
    availability: str
    last_attempted_at: str
    fallback_used: bool = False
    fallback_provider: str | None = None
    warnings: tuple[str, ...] = ()
    safe_error_messages: tuple[str, ...] = ()
    metadata: dict[str, object] = field(default_factory=dict)

    def as_dict(self) -> dict[str, object]:
        return {
            "domain": self.domain,
            "provider": self.provider,
            "source": self.source,
            "availability": self.availability,
            "last_attempted_at": self.last_attempted_at,
            "fallback_used": self.fallback_used,
            "fallback_provider": self.fallback_provider,
            "warnings": list(self.warnings),
            "safe_error_messages": list(self.safe_error_messages),
            "metadata": _json_safe_dict(self.metadata),
        }


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def configured_status(
    *,
    domain: LiveDataDomain,
    provider: str,
    source: str | None = None,
    last_attempted_at: str | None = None,
) -> LiveDataStatus:
    normalized = provider.strip().lower() or "unknown"
    availability = LiveDataAvailability.UNKNOWN
    if normalized == "static":
        availability = LiveDataAvailability.STATIC
    return LiveDataStatus(
        domain=domain.value,
        provider=normalized,
        source=source or normalized,
        availability=availability.value,
        last_attempted_at=last_attempted_at or utc_now_iso(),
        metadata={"configured_only": True},
    )


def market_price_status_from_snapshot(
    *,
    snapshot: PortfolioSnapshot,
    provider: str,
    source: str,
    warnings: Iterable[str] = (),
    fallback_provider: str | None = None,
    last_attempted_at: str | None = None,
) -> LiveDataStatus:
    normalized_provider = provider.strip().lower() or "unknown"
    warning_tuple = tuple(dict.fromkeys(str(w) for w in warnings if str(w).strip()))
    if normalized_provider == "static":
        availability = LiveDataAvailability.STATIC
    elif snapshot.holdings and all(not h.price_available for h in snapshot.holdings):
        availability = LiveDataAvailability.UNAVAILABLE
    elif snapshot.price_completeness_status == "complete":
        availability = LiveDataAvailability.LIVE
    elif snapshot.price_completeness_status == "partial":
        availability = LiveDataAvailability.PARTIAL
    elif not snapshot.holdings:
        availability = LiveDataAvailability.UNKNOWN
    else:
        availability = LiveDataAvailability.UNAVAILABLE
    fallback_used = any("fallback used" in w for w in warning_tuple)
    return LiveDataStatus(
        domain=LiveDataDomain.MARKET_PRICES.value,
        provider=normalized_provider,
        source=source,
        availability=availability.value,
        last_attempted_at=last_attempted_at or utc_now_iso(),
        fallback_used=fallback_used,
        fallback_provider=fallback_provider,
        warnings=warning_tuple,
        safe_error_messages=tuple(w for w in warning_tuple if "failed" in w.lower()),
        metadata={
            "valuation_status": snapshot.valuation_status,
            "price_completeness_status": snapshot.price_completeness_status,
            "priced_holdings": sum(1 for h in snapshot.holdings if h.price_available),
            "total_holdings": len(snapshot.holdings),
        },
    )


def diagnostics_status(result: MarketDataDiagnosticResult) -> LiveDataStatus:
    failed = tuple(check.summary for check in result.checks if not check.ok)
    if result.effective_provider == "static":
        availability = LiveDataAvailability.STATIC
    elif result.ok:
        availability = LiveDataAvailability.LIVE
    elif any(check.ok for check in result.checks):
        availability = LiveDataAvailability.PARTIAL
    else:
        availability = LiveDataAvailability.UNAVAILABLE
    return LiveDataStatus(
        domain=LiveDataDomain.MARKET_PRICES.value,
        provider=result.provider,
        source=result.effective_provider,
        availability=availability.value,
        last_attempted_at=utc_now_iso(),
        fallback_used=result.fallback_provider is not None,
        fallback_provider=result.fallback_provider,
        warnings=failed,
        safe_error_messages=failed,
        metadata={"sample_ticker": result.sample_ticker, "diagnostic_ok": result.ok},
    )


def fundamentals_status(report: FundamentalAnalysisReport) -> LiveDataStatus:
    snapshots = (*report.holdings, *report.watchlist)
    available = sum(1 for item in snapshots if item.data_status != "missing_data")
    return _report_status(
        domain=LiveDataDomain.FUNDAMENTALS,
        provider=_first_source((item.source for item in snapshots), "fundamentals"),
        source=_first_source((item.source for item in snapshots), "fundamentals"),
        available=available,
        total=len(snapshots),
        warnings=(
            *report.limitations,
            *(w for item in snapshots for w in item.warnings),
        ),
    )


def news_status(report: NewsReport) -> LiveDataStatus:
    results = (*report.holdings, *report.watchlist, *report.market, *report.sectors)
    available = sum(1 for item in results if item.available and item.articles)
    return _report_status(
        domain=LiveDataDomain.NEWS,
        provider=_first_source((item.source for item in results), "news"),
        source=_first_source((item.source for item in results), "news"),
        available=available,
        total=len(results),
        warnings=(*report.warnings, *report.limitations),
    )


def market_condition_status(report: MarketConditionReport | None) -> LiveDataStatus:
    if report is None:
        return LiveDataStatus(
            domain=LiveDataDomain.MARKET_CONDITION.value,
            provider="unknown",
            source="unknown",
            availability=LiveDataAvailability.UNKNOWN.value,
            last_attempted_at=utc_now_iso(),
            metadata={"evaluated": False},
        )
    indexes = tuple(
        item
        for item in (report.primary_index, *report.secondary_indexes)
        if item is not None
    )
    available = sum(1 for item in indexes if item.data_status == "available")
    return _report_status(
        domain=LiveDataDomain.MARKET_CONDITION,
        provider=_first_source((item.source for item in indexes), "market_data"),
        source=_first_source((item.source for item in indexes), "market_data"),
        available=available,
        total=len(indexes),
        warnings=(*report.warnings, *report.limitations),
        metadata={"status": report.status.value, "summary": report.summary},
    )


def _report_status(
    *,
    domain: LiveDataDomain,
    provider: str,
    source: str,
    available: int,
    total: int,
    warnings: Iterable[str],
    metadata: dict[str, object] | None = None,
) -> LiveDataStatus:
    if provider == "static":
        availability = LiveDataAvailability.STATIC
    elif total == 0:
        availability = LiveDataAvailability.UNKNOWN
    elif available == total:
        availability = LiveDataAvailability.LIVE
    elif available > 0:
        availability = LiveDataAvailability.PARTIAL
    else:
        availability = LiveDataAvailability.UNAVAILABLE
    return LiveDataStatus(
        domain=domain.value,
        provider=provider,
        source=source,
        availability=availability.value,
        last_attempted_at=utc_now_iso(),
        warnings=tuple(dict.fromkeys(w for w in warnings if w)),
        metadata={
            "available_items": available,
            "total_items": total,
            **(metadata or {}),
        },
    )


def _first_source(values: Iterable[str], default: str) -> str:
    for value in values:
        if value and value.strip():
            return value.strip()
    return default


def _json_safe_dict(value: dict[str, object]) -> dict[str, object]:
    return {str(key): _json_safe(item) for key, item in sorted(value.items())}


def _json_safe(value: object) -> object:
    if isinstance(value, dict):
        return _json_safe_dict(value)  # type: ignore[arg-type]
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)
