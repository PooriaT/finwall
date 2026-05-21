"""Deterministic report composition pipeline.

This module is the source of truth for deterministic report artifacts.
It intentionally excludes narrative provider orchestration.
"""

from __future__ import annotations

from dataclasses import dataclass

from finwall.market_condition import MarketConditionReport, classify_market_condition
from finwall.market_data import (
    IndexQuote,
    build_market_data_provider,
    fetch_portfolio_latest_prices,
)
from finwall.models import Portfolio
from finwall.recommendations import RecommendationReport, build_recommendation_report
from finwall.reports import DecisionSupportReport, build_decision_support_report
from finwall.risk import RiskAssessment, assess_portfolio_risk
from finwall.snapshot import PortfolioSnapshot, generate_snapshot


@dataclass(frozen=True)
class DeterministicReportArtifacts:
    payload: dict[str, object]
    report: DecisionSupportReport
    snapshot: PortfolioSnapshot
    risk_assessment: RiskAssessment
    recommendation_report: RecommendationReport
    market_index_quote: IndexQuote | None
    market_condition_report: MarketConditionReport | None
    live_price_warnings: tuple[str, ...]


def build_deterministic_report_artifacts(
    *, args, portfolio: Portfolio, settings, print_live_price_warnings: bool = True
) -> DeterministicReportArtifacts:
    latest_prices = dict(_parse_price(item) for item in args.price)
    market_index_quote = None
    market_condition_report = None
    live_price_warnings: list[str] = []
    if args.live_prices or args.market_index:
        provider = build_market_data_provider(
            settings.market_data_provider,
            settings.market_data_timeout_seconds,
        )
        if args.live_prices:
            fetched_prices, warnings = fetch_portfolio_latest_prices(
                portfolio, provider
            )
            latest_prices = {**fetched_prices, **latest_prices}
            for warning in warnings:
                warning_message = f"unable to fetch price for {warning}"
                live_price_warnings.append(warning_message)
                if print_live_price_warnings:
                    print(f"Warning: {warning_message}")
        if args.market_index:
            market_index_quote = provider.get_index_quote(args.market_index)
            market_condition_report = classify_market_condition(
                provider=provider,
                primary_symbol=args.market_index,
                include_nasdaq=args.include_nasdaq,
                days=args.market_condition_days,
            )

    snapshot = generate_snapshot(portfolio, latest_prices)
    risk_assessment = assess_portfolio_risk(portfolio, snapshot)
    recommendation_report = build_recommendation_report(
        portfolio, snapshot, risk_assessment
    )
    report = build_decision_support_report(
        portfolio,
        snapshot,
        risk_assessment,
        recommendation_report,
        market_index_quote,
        market_condition_report,
    )

    return DeterministicReportArtifacts(
        payload=report.as_dict(),
        report=report,
        snapshot=snapshot,
        risk_assessment=risk_assessment,
        recommendation_report=recommendation_report,
        market_index_quote=market_index_quote,
        market_condition_report=market_condition_report,
        live_price_warnings=tuple(live_price_warnings),
    )


def _parse_price(value: str) -> tuple[str, object]:
    ticker, price = value.split("=", maxsplit=1)
    from decimal import Decimal

    return ticker.upper(), Decimal(price)
