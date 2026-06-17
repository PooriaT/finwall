from __future__ import annotations

from dataclasses import asdict, dataclass, field
from decimal import Decimal

from finwall.config import Settings
from finwall.market_data import (
    build_market_data_provider,
    fetch_portfolio_latest_prices,
)
from finwall.models import Portfolio
from finwall.risk import assess_portfolio_risk
from finwall.snapshot import HoldingSnapshot, generate_snapshot
from finwall.storage_interface import PortfolioStore


@dataclass(frozen=True)
class ChartPoint:
    key: str
    label: str
    value: str | None
    percent: str | None = None
    status: str = "available"
    metadata: dict[str, object] = field(default_factory=dict)

    def as_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True)
class ChartSeries:
    key: str
    title: str
    points: tuple[ChartPoint, ...]
    warnings: tuple[str, ...] = ()

    def as_dict(self) -> dict[str, object]:
        return {
            "key": self.key,
            "title": self.title,
            "points": [point.as_dict() for point in self.points],
            "warnings": list(self.warnings),
        }


@dataclass(frozen=True)
class PortfolioChartData:
    portfolio_name: str
    allocation_by_holding: ChartSeries
    allocation_by_sector: ChartSeries
    cash_vs_invested: ChartSeries
    unrealized_gain_loss_by_holding: ChartSeries
    risk_warnings_by_severity: ChartSeries
    report_history_summary: ChartSeries
    valuation_status: str
    price_completeness_status: str
    data_warnings: tuple[str, ...]

    def as_dict(self) -> dict[str, object]:
        return {
            "portfolio_name": self.portfolio_name,
            "valuation_status": self.valuation_status,
            "price_completeness_status": self.price_completeness_status,
            "data_warnings": list(self.data_warnings),
            "charts": {
                "allocation_by_holding": self.allocation_by_holding.as_dict(),
                "allocation_by_sector": self.allocation_by_sector.as_dict(),
                "cash_vs_invested": self.cash_vs_invested.as_dict(),
                "unrealized_gain_loss_by_holding": self.unrealized_gain_loss_by_holding.as_dict(),
                "risk_warnings_by_severity": self.risk_warnings_by_severity.as_dict(),
                "report_history_summary": self.report_history_summary.as_dict(),
            },
        }


def build_portfolio_chart_data(
    portfolio: Portfolio,
    store: PortfolioStore,
    settings: Settings,
    *,
    report_history_limit: int = 10,
) -> PortfolioChartData:
    provider = build_market_data_provider(
        settings.market_data_provider, settings.market_data_timeout_seconds
    )
    latest_prices, provider_warnings = fetch_portfolio_latest_prices(
        portfolio, provider
    )
    snapshot = generate_snapshot(portfolio, latest_prices)
    risk = assess_portfolio_risk(portfolio, snapshot)
    bounded_limit = max(0, min(report_history_limit, 50))
    reports = store.list_report_runs(portfolio.name, bounded_limit)
    return PortfolioChartData(
        portfolio_name=portfolio.name,
        allocation_by_holding=_allocation_by_holding(snapshot.holdings),
        allocation_by_sector=_allocation_by_sector(portfolio, snapshot.holdings),
        cash_vs_invested=ChartSeries(
            key="cash_vs_invested",
            title="Cash vs invested",
            points=(
                ChartPoint(
                    key="cash",
                    label="Cash",
                    value=snapshot.cash_balance,
                    percent=snapshot.cash_allocation_percent,
                    metadata={
                        "valuation_status": snapshot.valuation_status,
                        "valuation_currency": snapshot.valuation_currency,
                        "cash_allocation_percent": snapshot.cash_allocation_percent,
                        "invested_allocation_percent": snapshot.invested_allocation_percent,
                        "price_completeness_status": snapshot.price_completeness_status,
                    },
                ),
                ChartPoint(
                    key="invested",
                    label="Invested",
                    value=snapshot.invested_value,
                    percent=snapshot.invested_allocation_percent,
                    metadata={
                        "valuation_status": snapshot.valuation_status,
                        "valuation_currency": snapshot.valuation_currency,
                        "cash_allocation_percent": snapshot.cash_allocation_percent,
                        "invested_allocation_percent": snapshot.invested_allocation_percent,
                        "price_completeness_status": snapshot.price_completeness_status,
                    },
                ),
            ),
            warnings=tuple(provider_warnings),
        ),
        unrealized_gain_loss_by_holding=_unrealized(snapshot.holdings),
        risk_warnings_by_severity=_risk_warnings(risk.warnings),
        report_history_summary=ChartSeries(
            key="report_history_summary",
            title="Report history summary",
            points=tuple(
                ChartPoint(
                    key=str(report.id),
                    label=report.created_at or report.command_context,
                    value=str(index + 1),
                    metadata={
                        "report_id": report.id,
                        "created_at": report.created_at,
                        "command_context": report.command_context,
                        "price_completeness_status": report.price_completeness_status,
                        "valuation_status": report.valuation_status,
                        "recommendation_summary": report.recommendation_summary,
                        "report_summary": report.report_summary,
                    },
                )
                for index, report in enumerate(reports)
            ),
        ),
        valuation_status=snapshot.valuation_status,
        price_completeness_status=snapshot.price_completeness_status,
        data_warnings=tuple(provider_warnings),
    )


def _allocation_by_holding(holdings: tuple[HoldingSnapshot, ...]) -> ChartSeries:
    return ChartSeries(
        key="allocation_by_holding",
        title="Allocation by holding",
        points=tuple(
            ChartPoint(
                key=h.ticker,
                label=h.ticker,
                value=h.estimated_value,
                percent=h.allocation_in_total_percent
                or h.allocation_in_invested_percent,
                status="available" if h.price_available else "missing_price",
                metadata={
                    "share_count": h.share_count,
                    "current_price": h.current_price,
                    "price_status": h.price_status,
                    "missing_price_message": h.missing_price_message,
                },
            )
            for h in holdings
        ),
    )


def _allocation_by_sector(
    portfolio: Portfolio, holdings: tuple[HoldingSnapshot, ...]
) -> ChartSeries:
    sectors: dict[str, dict[str, object]] = {}
    by_ticker = {holding.ticker.upper(): holding for holding in holdings}
    missing: list[str] = []
    for holding in portfolio.holdings:
        sector = holding.sector or "Uncategorized"
        snapshot = by_ticker[holding.ticker.upper()]
        entry = sectors.setdefault(
            sector,
            {
                "value": Decimal("0"),
                "tickers": [],
                "priced_tickers": [],
                "missing_tickers": [],
            },
        )
        entry["tickers"].append(holding.ticker)
        if snapshot.estimated_value is None:
            entry["missing_tickers"].append(holding.ticker)
            missing.append(holding.ticker)
            continue
        entry["priced_tickers"].append(holding.ticker)
        entry["value"] = entry["value"] + Decimal(snapshot.estimated_value)
    invested = sum((entry["value"] for entry in sectors.values()), Decimal("0"))
    points = []
    for sector in sorted(sectors):
        value = sectors[sector]["value"]
        priced_tickers = sectors[sector]["priced_tickers"]
        missing_tickers = sectors[sector]["missing_tickers"]
        status = "available" if priced_tickers else "missing_price"
        percent = (
            str((value / invested * Decimal("100")).quantize(Decimal("0.01")))
            if invested and priced_tickers
            else None
        )
        points.append(
            ChartPoint(
                sector,
                sector,
                str(value) if priced_tickers else None,
                percent,
                status=status,
                metadata={
                    "tickers": sectors[sector]["tickers"],
                    "priced_tickers": priced_tickers,
                    "missing_tickers": missing_tickers,
                },
            )
        )
    warnings = (
        (
            "Sector allocation excludes holdings with missing prices: "
            f"{', '.join(sorted(missing))}",
        )
        if missing
        else ()
    )
    return ChartSeries(
        "allocation_by_sector", "Allocation by sector", tuple(points), warnings
    )


def _unrealized(holdings: tuple[HoldingSnapshot, ...]) -> ChartSeries:
    points = []
    for h in holdings:
        percent = None
        if h.unrealized_gain_loss is not None and Decimal(h.average_purchase_price) > 0:
            cost = Decimal(h.average_purchase_price) * Decimal(h.share_count)
            percent = str(
                (Decimal(h.unrealized_gain_loss) / cost * Decimal("100")).quantize(
                    Decimal("0.01")
                )
            )
        points.append(
            ChartPoint(
                h.ticker,
                h.ticker,
                h.unrealized_gain_loss,
                percent,
                "available" if h.price_available else "missing_price",
                {
                    "current_price": h.current_price,
                    "average_purchase_price": h.average_purchase_price,
                    "estimated_value": h.estimated_value,
                    "missing_price_message": h.missing_price_message,
                },
            )
        )
    return ChartSeries(
        "unrealized_gain_loss_by_holding",
        "Unrealized gain/loss by holding",
        tuple(points),
    )


def _risk_warnings(warnings) -> ChartSeries:
    order = ("high", "medium", "low", "other")
    grouped = {key: [] for key in order}
    for warning in warnings:
        grouped[warning.severity if warning.severity in grouped else "other"].append(
            warning
        )
    return ChartSeries(
        "risk_warnings_by_severity",
        "Risk warnings by severity",
        tuple(
            ChartPoint(
                severity,
                severity,
                str(len(items)),
                metadata={
                    "warning_codes": [item.code for item in items],
                    "affected_tickers": [item.ticker for item in items if item.ticker],
                    "messages": [item.message for item in items],
                    "warnings": [asdict(item) for item in items],
                },
            )
            for severity, items in grouped.items()
            if items
        ),
    )
