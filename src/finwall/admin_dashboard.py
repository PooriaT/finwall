from dataclasses import asdict, dataclass
from decimal import Decimal

from finwall.chart_data import build_portfolio_chart_data
from finwall.config import Settings
from finwall.market_data import (
    build_market_data_provider,
    fetch_portfolio_latest_prices,
)
from finwall.models import Portfolio
from finwall.risk import assess_portfolio_risk
from finwall.snapshot import generate_snapshot
from finwall.storage_interface import PortfolioStore


@dataclass(frozen=True)
class DashboardView:
    portfolio_name: str
    cash_balances: tuple[dict[str, object], ...]
    holdings: tuple[dict[str, object], ...]
    active_orders: tuple[dict[str, object], ...]
    watchlist: tuple[dict[str, object], ...]
    goal: dict[str, object] | None
    risk_profile: dict[str, object] | None
    valuation: dict[str, object]
    live_data: dict[str, object]
    latest_report: dict[str, object] | None
    latest_audit_events: tuple[dict[str, object], ...]
    warnings: tuple[str, ...]
    charts: dict[str, object]


def build_dashboard_view(
    portfolio: Portfolio,
    store: PortfolioStore,
    settings: Settings,
) -> DashboardView:
    provider = build_market_data_provider(
        settings.market_data_provider,
        settings.market_data_timeout_seconds,
    )
    latest_prices, provider_warnings = fetch_portfolio_latest_prices(
        portfolio, provider
    )
    snapshot = generate_snapshot(portfolio, latest_prices)
    risk_assessment = assess_portfolio_risk(portfolio, snapshot)
    latest_report = store.get_latest_report_run(portfolio.name)
    latest_audit_events = store.list_portfolio_audit_events(portfolio.name, 5)
    chart_data = build_portfolio_chart_data(portfolio, store, settings).as_dict()[
        "charts"
    ]

    live_price_rows = tuple(
        {
            "ticker": holding.ticker,
            "available": holding.ticker.upper() in latest_prices,
            "price": _format_decimal(latest_prices.get(holding.ticker.upper())),
            "status": "available"
            if holding.ticker.upper() in latest_prices
            else "missing",
        }
        for holding in portfolio.holdings
    )

    goal = portfolio.goals[-1] if portfolio.goals else None
    return DashboardView(
        portfolio_name=portfolio.name,
        cash_balances=tuple(
            {"currency": currency, "amount": amount}
            for currency, amount in snapshot.cash_balances.items()
        ),
        holdings=tuple(asdict(item) for item in snapshot.holdings),
        active_orders=tuple(asdict(item) for item in snapshot.active_orders),
        watchlist=tuple(asdict(item) for item in portfolio.watchlist),
        goal=_goal_payload(goal),
        risk_profile=asdict(portfolio.risk_profile) if portfolio.risk_profile else None,
        valuation={
            "total_portfolio_value": snapshot.total_portfolio_value,
            "invested_value": snapshot.invested_value,
            "cash_balance": snapshot.cash_balance,
            "valuation_status": snapshot.valuation_status,
            "price_completeness_status": snapshot.price_completeness_status,
            "total_unrealized_gain_loss": snapshot.total_unrealized_gain_loss,
            "total_unrealized_gain_loss_percent": snapshot.total_unrealized_gain_loss_percent,
            "valuation_currency": snapshot.valuation_currency,
            "risk": risk_assessment.as_dict(),
        },
        live_data={
            "provider": settings.market_data_provider,
            "timeout_seconds": settings.market_data_timeout_seconds,
            "source": _provider_source(settings.market_data_provider),
            "prices": live_price_rows,
            "warnings": tuple(provider_warnings),
        },
        latest_report=asdict(latest_report) if latest_report is not None else None,
        latest_audit_events=tuple(event.as_dict() for event in latest_audit_events),
        warnings=tuple(provider_warnings),
        charts=chart_data,
    )


def _goal_payload(goal) -> dict[str, object] | None:
    if goal is None:
        return None
    return {
        "name": goal.name,
        "target_amount": _format_decimal(goal.target_amount),
        "timeline_start_date": goal.timeline.start_date if goal.timeline else None,
        "timeline_target_date": goal.timeline.target_date if goal.timeline else None,
    }


def _format_decimal(value: Decimal | None) -> str | None:
    return None if value is None else str(value)


def _provider_source(provider_name: str) -> str:
    normalized = provider_name.strip().lower()
    if normalized in {"yahoo", "yfinance", "static"}:
        return normalized
    return "static"
