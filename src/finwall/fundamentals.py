from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from typing import Protocol

from finwall.models import Portfolio


@dataclass(frozen=True)
class CompanyProfile:
    ticker: str
    company_name: str | None
    sector: str | None
    industry: str | None
    country: str | None
    website: str | None
    source: str
    available: bool
    error: str | None = None


@dataclass(frozen=True)
class FundamentalMetric:
    name: str
    value: str | None
    available: bool
    source: str
    error: str | None = None


@dataclass(frozen=True)
class FundamentalSnapshot:
    ticker: str
    source: str
    data_status: str
    profile: CompanyProfile
    revenue_growth: FundamentalMetric
    earnings_growth: FundamentalMetric
    profitability: tuple[FundamentalMetric, ...]
    debt: tuple[FundamentalMetric, ...]
    valuation: tuple[FundamentalMetric, ...]
    warnings: tuple[str, ...]


@dataclass(frozen=True)
class FundamentalAnalysisReport:
    holdings: tuple[FundamentalSnapshot, ...]
    watchlist: tuple[FundamentalSnapshot, ...]
    summary: str
    limitations: tuple[str, ...]

    def as_dict(self) -> dict[str, object]:
        return asdict(self)

    def to_json(self) -> str:
        return json.dumps(self.as_dict(), indent=2)


class FundamentalDataProvider(Protocol):
    def get_fundamentals(self, ticker: str) -> FundamentalSnapshot: ...


def unavailable_snapshot(
    ticker: str,
    source: str = "static",
    error: str | None = None,
) -> FundamentalSnapshot:
    return FundamentalSnapshot(
        ticker=ticker,
        source=source,
        data_status="missing_data",
        profile=CompanyProfile(
            ticker=ticker,
            company_name=None,
            sector=None,
            industry=None,
            country=None,
            website=None,
            source=source,
            available=False,
            error=error,
        ),
        revenue_growth=FundamentalMetric("revenue_growth", None, False, source, error),
        earnings_growth=FundamentalMetric(
            "earnings_growth", None, False, source, error
        ),
        profitability=(),
        debt=(),
        valuation=(),
        warnings=("provider request failed",) if error else (),
    )


class StaticFundamentalDataProvider:
    def __init__(self, snapshots: dict[str, FundamentalSnapshot] | None = None) -> None:
        self.snapshots = snapshots or {}

    def get_fundamentals(self, ticker: str) -> FundamentalSnapshot:
        return self.snapshots.get(ticker, unavailable_snapshot(ticker, source="static"))


def build_fundamental_data_provider(
    provider_name: str, timeout_seconds: float
) -> FundamentalDataProvider:
    del timeout_seconds
    if provider_name.strip().lower() != "static":
        return StaticFundamentalDataProvider()
    return StaticFundamentalDataProvider()


def _normalize_snapshot(snapshot: FundamentalSnapshot) -> FundamentalSnapshot:
    warnings = list(snapshot.warnings)
    if not snapshot.profile.available:
        warnings.append("company profile unavailable")
    if not snapshot.revenue_growth.available:
        warnings.append("revenue growth unavailable")
    if not snapshot.earnings_growth.available:
        warnings.append("earnings growth unavailable")
    profitability_available = any(m.available for m in snapshot.profitability)
    debt_available = any(m.available for m in snapshot.debt)
    valuation_available = any(m.available for m in snapshot.valuation)

    if not profitability_available:
        warnings.append("profitability metrics unavailable")
    if not debt_available:
        warnings.append("debt metrics unavailable")
    if not valuation_available:
        warnings.append("valuation metrics unavailable")

    unique_warnings = tuple(dict.fromkeys(warnings))

    available_flags = [
        snapshot.profile.available,
        snapshot.revenue_growth.available,
        snapshot.earnings_growth.available,
        profitability_available,
        debt_available,
        valuation_available,
    ]
    if all(available_flags):
        status = "available"
    elif any(available_flags):
        status = "partial"
    else:
        status = "missing_data"

    return FundamentalSnapshot(
        ticker=snapshot.ticker,
        source=snapshot.source,
        data_status=status,
        profile=snapshot.profile,
        revenue_growth=snapshot.revenue_growth,
        earnings_growth=snapshot.earnings_growth,
        profitability=snapshot.profitability,
        debt=snapshot.debt,
        valuation=snapshot.valuation,
        warnings=unique_warnings,
    )


def build_fundamental_analysis_report(
    portfolio: Portfolio,
    provider: FundamentalDataProvider,
) -> FundamentalAnalysisReport:
    holding_tickers = [h.ticker for h in portfolio.holdings]
    watchlist_tickers = [w.ticker for w in portfolio.watchlist]
    all_tickers = list(dict.fromkeys(holding_tickers + watchlist_tickers))
    fetched = {
        ticker: _normalize_snapshot(provider.get_fundamentals(ticker))
        for ticker in all_tickers
    }
    holdings = tuple(fetched[t] for t in holding_tickers)
    watchlist = tuple(fetched[t] for t in watchlist_tickers)
    summary = (
        f"Fundamental snapshots: {len(holdings)} holding ticker(s), "
        f"{len(watchlist)} watchlist ticker(s)."
    )
    limitations = (
        "Fundamental metrics are raw decision-support inputs only and not financial advice.",
        "Fundamentals are not yet integrated into recommendation logic.",
    )
    return FundamentalAnalysisReport(holdings, watchlist, summary, limitations)
