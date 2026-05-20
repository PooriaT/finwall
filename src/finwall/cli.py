import argparse
import json
import sys
from dataclasses import replace
from datetime import date
from decimal import Decimal

from finwall.config import settings
from finwall.email_notifications import (
    EmailSendResult,
    build_email_provider,
    build_scheduled_failure_email,
    build_scheduled_success_email,
)
from finwall.fundamental_summary import build_fundamental_summary_report
from finwall.fundamentals import (
    build_fundamental_analysis_report,
    build_fundamental_data_provider,
)
from finwall.market_calendar import evaluate_us_trading_day
from finwall.market_condition import classify_market_condition
from finwall.market_data import (
    INDEX_SYMBOL_MAP,
    build_market_data_provider,
    fetch_portfolio_latest_prices,
)
from finwall.models import (
    ActiveOrder,
    CashBalance,
    Holding,
    InvestmentGoal,
    OrderSide,
    OrderType,
    Portfolio,
    RiskLevel,
    RiskProfile,
    Timeline,
    TradeSide,
    TradeTransaction,
    WatchlistItem,
)
from finwall.narrative import (
    NARRATIVE_SECTIONS,
    NarrativeRequest,
    build_narrative_evidence,
    build_narrative_provider,
    format_narrative_markdown,
    generate_narrative,
)
from finwall.news import build_news_data_provider, build_news_report
from finwall.news_summary import build_news_summary_report
from finwall.order_evaluation import ProposedOrder, evaluate_proposed_order
from finwall.recommendations import build_recommendation_report
from finwall.report_history import (
    ReportRunComparison,
    StoredRecommendationStatus,
    compare_recommendation_statuses,
)
from finwall.reports import build_decision_support_report
from finwall.risk import RiskAssessment, assess_portfolio_risk
from finwall.scheduled_report import (
    ScheduledReportResult,
    ScheduledReportStatus,
    ScheduledRunContext,
)
from finwall.snapshot import PortfolioSnapshot, generate_snapshot
from finwall.storage_factory import build_portfolio_store
from finwall.storage_interface import PortfolioStore
from finwall.technical_analysis import (
    TechnicalAnalysisReport,
    build_technical_analysis_report,
)

DEFAULT_PORTFOLIO = "Primary"


def load_portfolio(store: PortfolioStore, name: str) -> Portfolio:
    portfolio = store.get_portfolio(name)
    if portfolio is not None:
        return portfolio
    portfolio = Portfolio(name=name)
    store.save_portfolio(portfolio)
    return portfolio


def upsert_cash(portfolio: Portfolio, currency: str, delta: Decimal) -> Portfolio:
    balances = list(portfolio.cash_balances)
    for index, balance in enumerate(balances):
        if balance.currency == currency:
            amount = balance.amount + delta
            balances[index] = CashBalance(currency=currency, amount=amount)
            return replace(portfolio, cash_balances=tuple(balances))
    return replace(
        portfolio,
        cash_balances=portfolio.cash_balances + (CashBalance(currency, delta),),
    )


def add_holding(
    portfolio: Portfolio,
    ticker: str,
    share_count: Decimal,
    average_price: Decimal,
    sector: str | None = None,
) -> Portfolio:
    holdings = tuple(item for item in portfolio.holdings if item.ticker != ticker)
    holding = Holding(ticker, share_count, average_price, sector)
    return replace(portfolio, holdings=holdings + (holding,))


def record_buy(
    portfolio: Portfolio,
    ticker: str,
    share_count: Decimal,
    price: Decimal,
    currency: str,
    traded_on: date,
) -> Portfolio:
    cost = share_count * price
    portfolio = upsert_cash(portfolio, currency, -cost)
    existing = next(
        (item for item in portfolio.holdings if item.ticker == ticker), None
    )
    if existing is None:
        portfolio = add_holding(portfolio, ticker, share_count, price)
    else:
        total_shares = existing.share_count + share_count
        total_cost = existing.share_count * existing.average_purchase_price + cost
        portfolio = add_holding(
            portfolio,
            ticker,
            total_shares,
            total_cost / total_shares,
            existing.sector,
        )
    transaction = TradeTransaction(ticker, TradeSide.BUY, share_count, price, traded_on)
    return replace(portfolio, transactions=portfolio.transactions + (transaction,))


def record_sell(
    portfolio: Portfolio,
    ticker: str,
    share_count: Decimal,
    price: Decimal,
    currency: str,
    traded_on: date,
) -> Portfolio:
    existing = next(
        (item for item in portfolio.holdings if item.ticker == ticker), None
    )
    if existing is None or existing.share_count < share_count:
        raise ValueError("cannot sell more shares than available")
    portfolio = upsert_cash(portfolio, currency, share_count * price)
    remaining = existing.share_count - share_count
    holdings = tuple(item for item in portfolio.holdings if item.ticker != ticker)
    if remaining > Decimal("0"):
        holding = Holding(
            ticker,
            remaining,
            existing.average_purchase_price,
            existing.sector,
        )
        holdings = holdings + (holding,)
    transaction = TradeTransaction(
        ticker, TradeSide.SELL, share_count, price, traded_on
    )
    return replace(
        portfolio,
        holdings=holdings,
        transactions=portfolio.transactions + (transaction,),
    )


def add_or_update_order(portfolio: Portfolio, order: ActiveOrder) -> Portfolio:
    orders = tuple(
        item for item in portfolio.active_orders if item.ticker != order.ticker
    )
    return replace(portfolio, active_orders=orders + (order,))


def remove_order(portfolio: Portfolio, ticker: str) -> Portfolio:
    orders = tuple(item for item in portfolio.active_orders if item.ticker != ticker)
    return replace(portfolio, active_orders=orders)


def add_watchlist_item(
    portfolio: Portfolio, ticker: str, note: str | None
) -> Portfolio:
    items = tuple(item for item in portfolio.watchlist if item.ticker != ticker)
    return replace(portfolio, watchlist=items + (WatchlistItem(ticker, note),))


def remove_watchlist_item(portfolio: Portfolio, ticker: str) -> Portfolio:
    return replace(
        portfolio,
        watchlist=tuple(item for item in portfolio.watchlist if item.ticker != ticker),
    )


def set_goal(
    portfolio: Portfolio,
    name: str,
    target_amount: Decimal | None,
) -> Portfolio:
    timeline = portfolio.goals[0].timeline if portfolio.goals else None
    return replace(
        portfolio,
        goals=(InvestmentGoal(name, target_amount, timeline),),
    )


def set_timeline(
    portfolio: Portfolio,
    start_date: date,
    target_date: date | None,
) -> Portfolio:
    timeline = Timeline(start_date, target_date)
    goal = portfolio.goals[0] if portfolio.goals else InvestmentGoal("Default goal")
    return replace(portfolio, goals=(replace(goal, timeline=timeline),))


def set_risk_profile(
    portfolio: Portfolio,
    level: RiskLevel,
    notes: str | None,
) -> Portfolio:
    return replace(portfolio, risk_profile=RiskProfile(level, notes))


def parse_decimal(value: str) -> Decimal:
    return Decimal(value)


def parse_date(value: str | None) -> date:
    return date.fromisoformat(value) if value is not None else date.today()


def parse_optional_date(value: str | None) -> date | None:
    return date.fromisoformat(value) if value is not None else None


def parse_price(value: str) -> tuple[str, Decimal]:
    ticker, price = value.split("=", maxsplit=1)
    return ticker.upper(), Decimal(price)


def save_portfolio_update(
    store: PortfolioStore,
    portfolio_name: str,
    portfolio: Portfolio,
    existing_transactions: tuple[TradeTransaction, ...],
) -> None:
    new_transactions = portfolio.transactions[len(existing_transactions) :]
    store.save_portfolio(replace(portfolio, transactions=()))
    for transaction in new_transactions:
        store.add_trade_transaction(portfolio_name, transaction)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="finwall")
    parser.add_argument("--database", default="finwall.db")
    parser.add_argument("--portfolio", default=DEFAULT_PORTFOLIO)
    subparsers = parser.add_subparsers(dest="command", required=True)

    add_cash = subparsers.add_parser("add-cash")
    add_cash.add_argument("currency")
    add_cash.add_argument("amount", type=parse_decimal)

    withdraw_cash = subparsers.add_parser("withdraw-cash")
    withdraw_cash.add_argument("currency")
    withdraw_cash.add_argument("amount", type=parse_decimal)

    holding = subparsers.add_parser("add-holding")
    holding.add_argument("ticker")
    holding.add_argument("shares", type=parse_decimal)
    holding.add_argument("average_price", type=parse_decimal)
    holding.add_argument("--sector")

    buy = subparsers.add_parser("record-buy")
    buy.add_argument("ticker")
    buy.add_argument("shares", type=parse_decimal)
    buy.add_argument("price", type=parse_decimal)
    buy.add_argument("--currency", default="USD")
    buy.add_argument("--date")

    sell = subparsers.add_parser("record-sell")
    sell.add_argument("ticker")
    sell.add_argument("shares", type=parse_decimal)
    sell.add_argument("price", type=parse_decimal)
    sell.add_argument("--currency", default="USD")
    sell.add_argument("--date")

    order = subparsers.add_parser("add-order")
    add_order_arguments(order)

    update_order = subparsers.add_parser("update-order")
    add_order_arguments(update_order)

    remove_order_parser = subparsers.add_parser("remove-order")
    remove_order_parser.add_argument("ticker")

    watch = subparsers.add_parser("add-watchlist")
    watch.add_argument("ticker")
    watch.add_argument("--note")

    remove_watch = subparsers.add_parser("remove-watchlist")
    remove_watch.add_argument("ticker")

    goal = subparsers.add_parser("set-goal")
    goal.add_argument("name")
    goal.add_argument("--target-amount", type=parse_decimal)

    timeline = subparsers.add_parser("set-timeline")
    timeline.add_argument("start_date")
    timeline.add_argument("--target-date")

    risk = subparsers.add_parser("set-risk")
    risk.add_argument("level", choices=[item.value for item in RiskLevel])
    risk.add_argument("--notes")

    snapshot = subparsers.add_parser("snapshot")
    snapshot.add_argument(
        "--price",
        action="append",
        default=[],
        help="Manual price in the format TICKER=PRICE",
    )
    snapshot.add_argument("--json", action="store_true")
    snapshot.add_argument("--live-prices", action="store_true")
    snapshot.add_argument("--risk", action="store_true")

    recommendations = subparsers.add_parser("recommendations")
    recommendations.add_argument(
        "--price",
        action="append",
        default=[],
        help="Manual price in the format TICKER=PRICE",
    )
    recommendations.add_argument("--live-prices", action="store_true")
    recommendations.add_argument("--json", action="store_true")

    evaluate_order = subparsers.add_parser("evaluate-order")
    evaluate_order.add_argument("ticker")
    evaluate_order.add_argument("side", choices=[item.value for item in OrderSide])
    evaluate_order.add_argument(
        "order_type", choices=[item.value for item in OrderType]
    )
    evaluate_order.add_argument("--entry-price", required=True, type=parse_decimal)
    evaluate_order.add_argument("--shares", type=parse_decimal)
    evaluate_order.add_argument("--limit-price", type=parse_decimal)
    evaluate_order.add_argument("--stop-price", type=parse_decimal)
    evaluate_order.add_argument("--target-price", type=parse_decimal)
    evaluate_order.add_argument("--currency", default="USD")
    evaluate_order.add_argument("--price", action="append", default=[])
    evaluate_order.add_argument("--live-prices", action="store_true")
    evaluate_order.add_argument("--json", action="store_true")

    market_index = subparsers.add_parser("market-index")
    market_index.add_argument("symbol", choices=sorted(INDEX_SYMBOL_MAP.keys()))

    technicals = subparsers.add_parser("technicals")
    technicals.add_argument("--days", type=int, default=250)
    technicals.add_argument("--json", action="store_true")
    technicals.add_argument("--holdings-only", action="store_true")
    technicals.add_argument("--watchlist-only", action="store_true")

    report = subparsers.add_parser("report")
    report.add_argument(
        "--price",
        action="append",
        default=[],
        help="Manual price in the format TICKER=PRICE",
    )
    report.add_argument("--live-prices", action="store_true")
    report.add_argument("--market-index", choices=sorted(INDEX_SYMBOL_MAP.keys()))
    report.add_argument("--include-nasdaq", action="store_true")
    report.add_argument("--market-condition-days", type=int, default=400)
    report.add_argument("--json", action="store_true")
    report.add_argument("--markdown", action="store_true")
    report.add_argument("--narrative", action="store_true")
    report.add_argument("--save-run", action="store_true")
    report.add_argument("--compare", action="store_true")

    scheduled = subparsers.add_parser("run-scheduled-report")
    scheduled.add_argument(
        "--run-context",
        choices=[item.value for item in ScheduledRunContext],
        default=ScheduledRunContext.MANUAL.value,
    )
    scheduled.add_argument("--run-date")
    scheduled.add_argument("--force", action="store_true")
    scheduled.add_argument(
        "--price",
        action="append",
        default=[],
        help="Manual price in the format TICKER=PRICE",
    )
    scheduled.add_argument("--live-prices", action="store_true")
    scheduled.add_argument("--market-index", choices=sorted(INDEX_SYMBOL_MAP.keys()))
    scheduled.add_argument("--include-nasdaq", action="store_true")
    scheduled.add_argument("--market-condition-days", type=int, default=400)
    scheduled.add_argument("--json", action="store_true")
    scheduled.add_argument("--markdown", action="store_true")
    scheduled.add_argument("--save-run", action="store_true")
    scheduled.add_argument("--compare", action="store_true")
    scheduled.add_argument("--email", action="store_true")
    scheduled.add_argument("--email-on-failure", action="store_true")
    scheduled.add_argument("--email-to")

    market_condition = subparsers.add_parser("market-condition")
    market_condition.add_argument(
        "--primary-index", choices=sorted(INDEX_SYMBOL_MAP.keys()), default="SP500"
    )
    market_condition.add_argument("--include-nasdaq", action="store_true")
    market_condition.add_argument("--days", type=int, default=250)
    market_condition.add_argument("--json", action="store_true")

    fundamentals = subparsers.add_parser("fundamentals")
    fundamentals.add_argument("--json", action="store_true")
    fundamentals.add_argument("--holdings-only", action="store_true")
    fundamentals.add_argument("--watchlist-only", action="store_true")

    fundamentals_summary = subparsers.add_parser("fundamentals-summary")
    fundamentals_summary.add_argument("--json", action="store_true")

    news = subparsers.add_parser("news")
    news.add_argument("--json", action="store_true")
    news.add_argument("--holdings-only", action="store_true")
    news.add_argument("--watchlist-only", action="store_true")
    news.add_argument("--include-market", action="store_true")
    news.add_argument("--include-sectors", action="store_true")
    news.add_argument("--limit-per-topic", type=int)
    news.add_argument("--max-age-hours", type=int)

    news_summary = subparsers.add_parser("news-summary")
    news_summary.add_argument("--json", action="store_true")
    news_summary.add_argument("--holdings-only", action="store_true")
    news_summary.add_argument("--watchlist-only", action="store_true")
    news_summary.add_argument("--include-market", action="store_true")
    news_summary.add_argument("--include-sectors", action="store_true")
    news_summary.add_argument("--limit-per-topic", type=int)
    news_summary.add_argument("--max-age-hours", type=int)
    return parser


def add_order_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("ticker")
    parser.add_argument("side", choices=[item.value for item in OrderSide])
    parser.add_argument("order_type", choices=[item.value for item in OrderType])
    parser.add_argument("shares", type=parse_decimal)
    parser.add_argument("--limit-price", type=parse_decimal)
    parser.add_argument("--stop-price", type=parse_decimal)


def print_risk_assessment(risk_assessment: RiskAssessment) -> None:
    print(f"Risk profile: {risk_assessment.risk_level}")
    print(f"Risk summary: {risk_assessment.summary}")
    if not risk_assessment.warnings:
        return
    print("Risk warnings:")
    for warning in risk_assessment.warnings:
        parts = [f"- [{warning.severity}] {warning.code}: {warning.message}"]
        if warning.ticker is not None:
            parts.append(f"ticker={warning.ticker}")
        if warning.value is not None and warning.limit is not None:
            parts.append(f"value={warning.value}% limit={warning.limit}%")
        print(" ".join(parts))


def print_snapshot(snapshot: PortfolioSnapshot) -> None:
    print(f"Cash balance: {snapshot.cash_balance}")
    print(f"Invested value: {snapshot.invested_value}")

    if snapshot.total_portfolio_value is None:
        print("Total portfolio value: unavailable")
        if snapshot.valuation_status == "multi_currency_cash_unsupported":
            print(
                "Reason: multiple cash currencies detected; total valuation and "
                "allocation require FX conversion (not implemented)."
            )
        elif snapshot.valuation_status == "missing_prices":
            print("Reason: one or more holding prices are missing.")
    else:
        print(f"Total portfolio value: {snapshot.total_portfolio_value}")

    if snapshot.total_unrealized_gain_loss_percent is None:
        print(f"Total unrealized gain/loss: {snapshot.total_unrealized_gain_loss}")
    else:
        print(
            "Total unrealized gain/loss: "
            f"{snapshot.total_unrealized_gain_loss} "
            f"({snapshot.total_unrealized_gain_loss_percent}%)"
        )

    if (
        snapshot.cash_allocation_percent is None
        or snapshot.invested_allocation_percent is None
    ):
        print("Allocation: unavailable")
    else:
        print(
            "Allocation: "
            f"cash={snapshot.cash_allocation_percent}% "
            f"invested={snapshot.invested_allocation_percent}%"
        )

    print(f"Price coverage: {snapshot.price_completeness_status}")
    print("Holdings:")

    for holding in snapshot.holdings:
        if not holding.price_available:
            print(
                f"- {holding.ticker}: shares={holding.share_count} "
                f"avg={holding.average_purchase_price} "
                f"price_status={holding.price_status} "
                f"message='{holding.missing_price_message}'"
            )
            continue

        allocation_invested = (
            f"{holding.allocation_in_invested_percent}%"
            if holding.allocation_in_invested_percent is not None
            else "n/a"
        )
        allocation_total = (
            f"{holding.allocation_in_total_percent}%"
            if holding.allocation_in_total_percent is not None
            else "n/a"
        )

        print(
            f"- {holding.ticker}: shares={holding.share_count} "
            f"avg={holding.average_purchase_price} "
            f"current={holding.current_price} "
            f"value={holding.estimated_value} "
            f"gain_loss={holding.unrealized_gain_loss} "
            f"alloc_invested={allocation_invested} "
            f"alloc_total={allocation_total}"
        )

    if snapshot.active_orders:
        print("Active orders:")
        for order in snapshot.active_orders:
            print(f"- {order.description}")


def print_recommendation_report(report) -> None:
    print(
        "Deterministic recommendations are decision support only and not financial advice."
    )
    print(f"Summary: {report.summary}")
    print(f"Cash deployment status: {report.cash_deployment.status.value}")
    print(f"Cash deployment confidence: {report.cash_deployment.confidence.value}")
    print(f"Suggested review action: {report.cash_deployment.suggested_action}")

    if report.cash_deployment.reasoning_inputs:
        print("Cash deployment reasoning inputs:")
        for item in report.cash_deployment.reasoning_inputs:
            print(f"- {item}")
    if report.cash_deployment.warnings:
        print("Cash deployment warnings:")
        for item in report.cash_deployment.warnings:
            print(f"- {item}")

    if not report.holdings:
        print("Holdings: none")

    for holding in report.holdings:
        print(f"Holding: {holding.ticker}")
        print(f"  Deterministic status: {holding.status.value}")
        print(f"  Confidence: {holding.confidence.value}")
        print(f"  Risk level: {holding.risk_level.value}")
        print(f"  Suggested review action: {holding.suggested_action}")
        print(f"  Blocked by risk: {holding.blocked_by_risk}")
        print(f"  Data quality: {holding.data_quality}")
        print("  Key reasoning inputs:")
        for item in holding.reasoning_inputs:
            print(f"  - {item}")
        if holding.warnings:
            print("  Warnings:")
            for item in holding.warnings:
                print(f"  - {item}")
        if holding.invalidation_conditions:
            print("  Invalidation conditions:")
            for item in holding.invalidation_conditions:
                print(f"  - {item}")

    if report.limitations:
        print("Limitations:")
        for item in report.limitations:
            print(f"- {item}")


def print_market_condition_report(report) -> None:
    print(f"Status: {report.status.value}")
    print(f"Summary: {report.summary}")
    if report.primary_index is not None:
        primary = report.primary_index
        print(f"Primary index: {primary.symbol} ({primary.provider_symbol})")
        print(f"  trend_status={primary.trend_status} source={primary.source}")
        print(
            f"  latest_close={primary.latest_close or 'n/a'} "
            f"sma50={primary.sma_50 or 'n/a'} sma200={primary.sma_200 or 'n/a'}"
        )
        print(f"  volatility_proxy={primary.volatility_proxy or 'n/a'}")
    if report.secondary_indexes:
        print("Secondary indexes:")
        for item in report.secondary_indexes:
            print(f"- {item.symbol}: trend_status={item.trend_status}")
    if report.reasoning_inputs:
        print("Reasoning inputs:")
        for item in report.reasoning_inputs:
            print(f"- {item}")
    if report.warnings:
        print("Warnings:")
        for item in report.warnings:
            print(f"- {item}")


def print_technical_report(
    report: TechnicalAnalysisReport,
    holdings_only: bool,
    watchlist_only: bool,
) -> None:
    print(report.summary)

    def _print_section(name: str, snapshots) -> None:
        print(f"{name}:")
        if not snapshots:
            print("- none")
            return
        for item in snapshots:
            print(f"- {item.ticker} [{item.data_status}] source={item.source}")
            print(f"  latest_close={item.latest_close or 'n/a'}")
            print(
                "  sma20={0} sma50={1} sma200={2}".format(
                    item.moving_averages.sma_20 or "n/a",
                    item.moving_averages.sma_50 or "n/a",
                    item.moving_averages.sma_200 or "n/a",
                )
            )
            print(f"  rsi14={item.rsi_14 or 'n/a'}")
            print(
                f"  recent_high={item.recent_high or 'n/a'} "
                f"recent_low={item.recent_low or 'n/a'}"
            )
            print(
                f"  volume_trend={item.volume_trend.status} "
                f"recent_avg={item.volume_trend.recent_average_volume or 'n/a'} "
                f"previous_avg={item.volume_trend.previous_average_volume or 'n/a'}"
            )
            if item.warnings:
                print("  warnings:")
                for warning in item.warnings:
                    print(f"  - {warning}")

    if not watchlist_only:
        _print_section("Holdings", report.holdings)
    if not holdings_only:
        _print_section("Watchlist", report.watchlist)

    if report.limitations:
        print("Limitations:")
        for limitation in report.limitations:
            print(f"- {limitation}")


def print_fundamentals_report(
    report, holdings_only: bool, watchlist_only: bool
) -> None:
    print(report.summary)

    def _print_metrics(name: str, metrics) -> None:
        if not metrics:
            print(f"  {name}: unavailable")
            return
        print(f"  {name}:")
        for metric in metrics:
            print(f"  - {metric.name}={metric.value or 'n/a'}")

    def _print_section(name: str, snapshots) -> None:
        print(f"{name}:")
        if not snapshots:
            print("- none")
            return
        for item in snapshots:
            print(f"- {item.ticker} [{item.data_status}] source={item.source}")
            print(f"  company_name={item.profile.company_name or 'n/a'}")
            print(f"  sector={item.profile.sector or 'n/a'}")
            print(f"  industry={item.profile.industry or 'n/a'}")
            print(f"  revenue_growth={item.revenue_growth.value or 'n/a'}")
            print(f"  earnings_growth={item.earnings_growth.value or 'n/a'}")
            _print_metrics("profitability", item.profitability)
            _print_metrics("debt", item.debt)
            _print_metrics("valuation", item.valuation)
            if item.warnings:
                print("  warnings:")
                for warning in item.warnings:
                    print(f"  - {warning}")

    if not watchlist_only:
        _print_section("Holdings", report.holdings)
    if not holdings_only:
        _print_section("Watchlist", report.watchlist)


def print_news_report(report, holdings_only: bool, watchlist_only: bool) -> None:
    print(report.summary)

    def _print_articles(section: str, items) -> None:
        print(f"{section}:")
        if not items:
            print("- none")
            return
        for result in items:
            print(
                f"- topic={result.topic} source={result.source} available={result.available}"
            )
            if result.error:
                print(f"  error={result.error}")
            if not result.articles:
                print("  articles: none")
                continue
            for article in result.articles:
                print(f"  * {article.title}")
                print(
                    "    source={0} quality={1} recency={2}".format(
                        article.source_name,
                        article.source_quality.value,
                        article.recency_status.value,
                    )
                )
                if article.url:
                    print(f"    url={article.url}")

    if not watchlist_only:
        _print_articles("Holdings", report.holdings)
    if not holdings_only:
        _print_articles("Watchlist", report.watchlist)
    _print_articles("Market", report.market)
    _print_articles("Sectors", report.sectors)

    if report.warnings:
        print("Warnings:")
        for warning in report.warnings:
            print(f"- {warning}")
    if report.limitations:
        print("Limitations:")
        for limitation in report.limitations:
            print(f"- {limitation}")


def print_news_summary_report(
    report, holdings_only: bool, watchlist_only: bool
) -> None:
    print(report.summary)
    print(
        "News summaries are decision-support input only and are not trade recommendations."
    )

    def _print_claims(name: str, claims) -> None:
        print(f"  {name}:")
        if not claims:
            print("  - none")
            return
        for claim in claims:
            print(f"  - [{claim.confidence}] {claim.text}")
            if claim.warning:
                print(f"    warning={claim.warning}")

    def _print_section(name: str, items) -> None:
        print(f"{name}:")
        if not items:
            print("- none")
            return
        for result in items:
            print(
                f"- {result.topic} [{result.topic_type}] [confidence={result.confidence}]"
            )
            _print_claims("Confirmed facts", result.confirmed_facts)
            _print_claims(
                "Possible market interpretations", result.market_interpretations
            )
            _print_claims("Uncertainties", result.uncertainties)
            _print_claims("Speculative claims", result.speculative_claims)
            if result.source_references:
                print("  Source references:")
                for ref in result.source_references:
                    print(
                        f"  - {ref.source_name}: {ref.title} "
                        f"quality={ref.source_quality} "
                        f"recency={ref.recency_status}"
                    )
                    if ref.url:
                        print(f"    url={ref.url}")

    if not watchlist_only:
        _print_section("Holdings", report.holdings)
    if not holdings_only:
        _print_section("Watchlist", report.watchlist)
    _print_section("Market", report.market)
    _print_section("Sectors", report.sectors)

    if report.warnings:
        print("Warnings:")
        for warning in report.warnings:
            print(f"- {warning}")
    if report.limitations:
        print("Limitations:")
        for limitation in report.limitations:
            print(f"- {limitation}")


def print_fundamental_summary_report(report) -> None:
    print(report.summary)

    def _print_section(name: str, summaries) -> None:
        print(f"{name}:")
        if not summaries:
            print("- none")
            return
        for item in summaries:
            print(f"- {item.ticker} [{item.data_status}] source={item.source}")
            print(f"  risk_level={item.risk_level.value}")
            print(f"  confidence={item.confidence.value}")
            print(f"  company_context={item.company_context}")
            print(f"  revenue_trend={item.revenue_trend}")
            print(f"  profitability={item.profitability}")
            print(f"  valuation_risk={item.valuation_risk}")
            print(f"  debt_risk={item.debt_risk}")
            print("  strengths:")
            if item.strengths:
                for signal in item.strengths:
                    print(f"  - {signal.message}")
            else:
                print("  - none")
            print("  weaknesses:")
            if item.weaknesses:
                for signal in item.weaknesses:
                    print(f"  - {signal.message}")
            else:
                print("  - none")
            print("  missing_information:")
            if item.missing_information:
                for value in item.missing_information:
                    print(f"  - {value}")
            else:
                print("  - none")
            print("  flags:")
            if item.flags:
                for value in item.flags:
                    print(f"  - {value}")
            else:
                print("  - none")

    _print_section("Holdings", report.holdings)
    _print_section("Watchlist", report.watchlist)
    print("Limitations:")
    for limitation in report.limitations:
        print(f"- {limitation}")


def build_report_payload(
    *,
    args,
    portfolio: Portfolio,
    store: PortfolioStore,
    print_live_price_warnings: bool = True,
) -> tuple[
    dict[str, object],
    object,
    object,
    object,
    object | None,
    ReportRunComparison | None,
    tuple[str, ...],
]:
    latest_prices = dict(parse_price(item) for item in args.price)
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
    saved_run = None
    comparison: ReportRunComparison | None = None
    if args.save_run:
        context = getattr(args, "save_command_context", "report")
        report_run_id = store.save_report_run(
            portfolio_name=portfolio.name,
            report=report,
            recommendation_report=recommendation_report,
            risk_assessment=risk_assessment,
            command_context=context,
        )
        saved_run = store.get_latest_report_run(portfolio.name)
        if args.compare:
            previous = store.get_previous_report_run(portfolio.name, report_run_id)
            previous_statuses = (
                store.list_report_recommendation_statuses(previous.id)
                if previous and previous.id is not None
                else ()
            )
            current_statuses = store.list_report_recommendation_statuses(report_run_id)
            comparison = compare_recommendation_statuses(
                previous=previous_statuses,
                current=current_statuses,
                previous_run_id=previous.id if previous else None,
                current_run_id=report_run_id,
            )
    elif args.compare:
        latest = store.get_latest_report_run(portfolio.name)
        previous_statuses = (
            store.list_report_recommendation_statuses(latest.id)
            if latest and latest.id is not None
            else ()
        )
        current_statuses = tuple(
            StoredRecommendationStatus(
                ticker=item.ticker,
                status=item.status.value,
                confidence=item.confidence.value,
                risk_level=item.risk_level.value,
                blocked_by_risk=item.blocked_by_risk,
                suggested_action=item.suggested_action,
            )
            for item in recommendation_report.holdings
        )
        comparison = compare_recommendation_statuses(
            previous=previous_statuses,
            current=current_statuses,
            previous_run_id=latest.id if latest else None,
            current_run_id=None,
        )

    payload: dict[str, object] = report.as_dict()
    if saved_run is not None:
        payload["saved_run"] = {
            "id": saved_run.id,
            "created_at": saved_run.created_at,
            "portfolio_name": saved_run.portfolio_name,
        }
    if comparison is not None:
        payload["comparison"] = {
            "previous_run_id": comparison.previous_run_id,
            "current_run_id": comparison.current_run_id,
            "summary": comparison.summary,
            "changes": [item.__dict__ for item in comparison.changes],
        }
    return (
        payload,
        report,
        saved_run,
        comparison,
        risk_assessment,
        recommendation_report,
        tuple(live_price_warnings),
    )


def run(argv: list[str] | None = None) -> int:
    parser = build_parser()
    raw_args = argv if argv is not None else sys.argv[1:]
    args = parser.parse_args(argv)
    cli_database_override = any(
        item == "--database" or item.startswith("--database=") for item in raw_args
    )
    store = build_portfolio_store(
        backend=settings.storage_backend,
        database_path=args.database,
        database_url=settings.database_url or None,
        cli_database_override=cli_database_override,
    )
    store.initialize()
    portfolio = load_portfolio(store, args.portfolio)
    existing_transactions = portfolio.transactions

    if args.command == "snapshot":
        latest_prices = dict(parse_price(item) for item in args.price)

        if args.live_prices:
            provider = build_market_data_provider(
                settings.market_data_provider,
                settings.market_data_timeout_seconds,
            )
            fetched_prices, warnings = fetch_portfolio_latest_prices(
                portfolio, provider
            )
            latest_prices = {**fetched_prices, **latest_prices}
            for warning in warnings:
                print(f"Warning: unable to fetch price for {warning}")

        snapshot = generate_snapshot(portfolio, latest_prices)

        risk_assessment = None
        if args.risk:
            risk_assessment = assess_portfolio_risk(portfolio, snapshot)
            snapshot = replace(snapshot, risk_assessment=risk_assessment.as_dict())

        if args.json:
            print(snapshot.to_json())
        else:
            print_snapshot(snapshot)
            if risk_assessment is not None:
                print_risk_assessment(risk_assessment)

        return 0

    if args.command == "recommendations":
        latest_prices = dict(parse_price(item) for item in args.price)
        if args.live_prices:
            provider = build_market_data_provider(
                settings.market_data_provider,
                settings.market_data_timeout_seconds,
            )
            fetched_prices, warnings = fetch_portfolio_latest_prices(
                portfolio, provider
            )
            latest_prices = {**fetched_prices, **latest_prices}
            for warning in warnings:
                print(f"Warning: unable to fetch price for {warning}")

        snapshot = generate_snapshot(portfolio, latest_prices)
        risk_assessment = assess_portfolio_risk(portfolio, snapshot)
        report = build_recommendation_report(portfolio, snapshot, risk_assessment)

        if args.json:
            print(__import__("json").dumps(report.as_dict(), indent=2))
        else:
            print_recommendation_report(report)
        return 0

    if args.command == "evaluate-order":
        latest_prices = dict(parse_price(item) for item in args.price)
        if args.live_prices:
            provider = build_market_data_provider(
                settings.market_data_provider,
                settings.market_data_timeout_seconds,
            )
            fetched_prices, warnings = fetch_portfolio_latest_prices(
                portfolio, provider
            )
            latest_prices = {**fetched_prices, **latest_prices}
            for warning in warnings:
                print(f"Warning: unable to fetch price for {warning}")

        snapshot = generate_snapshot(portfolio, latest_prices)
        proposed = ProposedOrder(
            ticker=args.ticker,
            side=OrderSide(args.side),
            order_type=OrderType(args.order_type),
            entry_price=args.entry_price,
            share_count=args.shares,
            stop_price=args.stop_price,
            limit_price=args.limit_price,
            target_price=args.target_price,
            currency=args.currency,
        )
        evaluation = evaluate_proposed_order(portfolio, snapshot, proposed)
        if args.json:
            print(__import__("json").dumps(evaluation.as_dict(), indent=2))
        else:
            print(
                f"Proposed order: {evaluation.ticker} {evaluation.side} {evaluation.order_type}"
            )
            print(f"Valid: {evaluation.valid}")
            print(f"Estimated total cost: {evaluation.estimated_total_cost or 'n/a'}")
            print(
                f"Estimated total proceeds: {evaluation.estimated_total_proceeds or 'n/a'}"
            )
            print(f"Maximum affordable shares: {evaluation.maximum_affordable_shares}")
            print(
                f"Maximum risk-allowed shares: {evaluation.maximum_risk_allowed_shares or 'n/a'}"
            )
            print(f"Suggested maximum shares: {evaluation.suggested_maximum_shares}")
            print(f"Cash after order: {evaluation.cash_after_order or 'n/a'}")
            print(
                f"Cash reserve after order: {evaluation.cash_reserve_percent_after_order or 'n/a'}%"
            )
            print(
                f"Maximum capital at risk: {evaluation.maximum_capital_at_risk or 'n/a'}"
            )
            print(f"Expected upside: {evaluation.expected_upside or 'n/a'}")
            print(f"Expected downside: {evaluation.expected_downside or 'n/a'}")
            print(f"Risk/reward ratio: {evaluation.risk_reward_ratio or 'n/a'}")
            if evaluation.warnings:
                print("Warnings:")
                for warning in evaluation.warnings:
                    print(f"- {warning}")
            if evaluation.errors:
                print("Validation errors:")
                for error in evaluation.errors:
                    print(f"- {error}")
        return 0

    if args.command == "technicals":
        provider = build_market_data_provider(
            settings.market_data_provider,
            settings.market_data_timeout_seconds,
        )
        report = build_technical_analysis_report(portfolio, provider, days=args.days)
        if args.holdings_only and not args.watchlist_only:
            report = TechnicalAnalysisReport(
                holdings=report.holdings,
                watchlist=(),
                summary=report.summary,
                limitations=report.limitations,
            )
        if args.watchlist_only and not args.holdings_only:
            report = TechnicalAnalysisReport(
                holdings=(),
                watchlist=report.watchlist,
                summary=report.summary,
                limitations=report.limitations,
            )
        if args.json:
            print(report.to_json())
        else:
            print_technical_report(report, args.holdings_only, args.watchlist_only)
        return 0
    if args.command == "fundamentals":
        provider = build_fundamental_data_provider(
            settings.fundamental_data_provider,
            settings.fundamental_data_timeout_seconds,
        )
        report = build_fundamental_analysis_report(portfolio, provider)
        if args.holdings_only and not args.watchlist_only:
            report = replace(report, watchlist=())
        if args.watchlist_only and not args.holdings_only:
            report = replace(report, holdings=())
        if args.json:
            print(report.to_json())
        else:
            print_fundamentals_report(report, args.holdings_only, args.watchlist_only)
        return 0

    if args.command == "fundamentals-summary":
        provider = build_fundamental_data_provider(
            settings.fundamental_data_provider,
            settings.fundamental_data_timeout_seconds,
        )
        raw_report = build_fundamental_analysis_report(portfolio, provider)
        report = build_fundamental_summary_report(raw_report)
        if args.json:
            print(report.to_json())
        else:
            print_fundamental_summary_report(report)
        return 0

    if args.command == "news":
        provider = build_news_data_provider(
            settings.news_provider,
            settings.news_timeout_seconds,
        )
        report = build_news_report(
            portfolio,
            provider,
            include_market=args.include_market,
            include_sectors=args.include_sectors,
            limit_per_topic=args.limit_per_topic
            or settings.news_max_articles_per_topic,
            max_age_hours=args.max_age_hours or settings.news_max_age_hours,
        )
        if args.holdings_only and not args.watchlist_only:
            report = replace(report, watchlist=())
        if args.watchlist_only and not args.holdings_only:
            report = replace(report, holdings=())
        if settings.news_provider.strip().lower() != "static":
            report = replace(
                report,
                warnings=report.warnings
                + (
                    (
                        "unsupported news provider "
                        f"'{settings.news_provider}' configured; using static fallback."
                    ),
                ),
            )
        if args.json:
            print(report.to_json())
        else:
            print_news_report(report, args.holdings_only, args.watchlist_only)
        return 0

    if args.command == "news-summary":
        provider = build_news_data_provider(
            settings.news_provider,
            settings.news_timeout_seconds,
        )
        raw_report = build_news_report(
            portfolio,
            provider,
            include_market=args.include_market,
            include_sectors=args.include_sectors,
            limit_per_topic=args.limit_per_topic
            or settings.news_max_articles_per_topic,
            max_age_hours=args.max_age_hours or settings.news_max_age_hours,
        )
        report = build_news_summary_report(raw_report)
        if args.holdings_only and not args.watchlist_only:
            report = replace(report, watchlist=())
        if args.watchlist_only and not args.holdings_only:
            report = replace(report, holdings=())
        if settings.news_provider.strip().lower() != "static":
            report = replace(
                report,
                warnings=report.warnings
                + (
                    (
                        "unsupported news provider "
                        f"'{settings.news_provider}' configured; using static fallback."
                    ),
                ),
            )
        if args.json:
            print(report.to_json())
        else:
            print_news_summary_report(report, args.holdings_only, args.watchlist_only)
        return 0

    if args.command == "market-condition":
        provider = build_market_data_provider(
            settings.market_data_provider,
            settings.market_data_timeout_seconds,
        )
        report = classify_market_condition(
            provider=provider,
            primary_symbol=args.primary_index,
            include_nasdaq=args.include_nasdaq,
            days=args.days,
        )
        if args.json:
            print(report.to_json())
        else:
            print_market_condition_report(report)
        return 0

    if args.command == "report":
        payload, report, saved_run, comparison, _, _, _ = build_report_payload(
            args=args, portfolio=portfolio, store=store
        )
        if not args.narrative:
            if args.json:
                print(json.dumps(payload, indent=2))
            else:
                print(report.to_markdown())
                if saved_run is not None:
                    print(
                        f"\nSaved report run id={saved_run.id} for "
                        f"{saved_run.portfolio_name}."
                    )
                if args.compare and not args.save_run:
                    print("Current run was not saved.")
                if comparison is not None:
                    print("\n## Recommendation Changes")
                    print(f"Previous run: {comparison.previous_run_id}")
                    print(f"Current run: {comparison.current_run_id}")
                    print(f"Summary: {comparison.summary}")
                    for change in comparison.changes:
                        print(f"\n- {change.ticker}: {change.change_type}")
            return 0

        evidence = build_narrative_evidence(report)
        request = NarrativeRequest(
            evidence=evidence,
            requested_sections=NARRATIVE_SECTIONS,
            max_words=settings.narrative_max_words,
            style=settings.narrative_style,
        )
        provider = build_narrative_provider(settings.narrative_provider)
        narrative = generate_narrative(request, provider)

        if args.json:
            payload["narrative"] = narrative.as_dict()
            print(json.dumps(payload, indent=2))
        else:
            print(f"{report.to_markdown()}\n\n{format_narrative_markdown(narrative)}")
        return 0

    if args.command == "run-scheduled-report":
        run_day = parse_date(args.run_date)
        trading = evaluate_us_trading_day(run_day)
        email_override = (
            tuple(item.strip() for item in args.email_to.split(",") if item.strip())
            if args.email_to
            else None
        )
        email_provider = build_email_provider(
            settings, to_addresses_override=email_override
        )

        def _notify(
            message_builder, result: ScheduledReportResult
        ) -> EmailSendResult | None:
            if not (args.email or args.email_on_failure):
                return None
            message = message_builder(
                result,
                portfolio.name,
                settings.email_from,
                email_override or settings.email_to_addresses,
            )
            return email_provider.send(message)

        if not trading.is_trading_day and not args.force:
            message = f"Skipped scheduled report for {trading.calendar_date}: {trading.reason}"
            result = ScheduledReportResult(
                status=ScheduledReportStatus.SKIPPED,
                run_context=args.run_context,
                trading_day=trading.as_dict(),
                report=None,
                saved_report_id=None,
                comparison=None,
                message=message,
                warnings=(),
            )
            if args.json:
                print(json.dumps(result.as_dict(), indent=2))
            else:
                print(message)
            return 0
        try:
            args.save_command_context = f"scheduled:{args.run_context}"
            payload, report, saved_run, comparison, _, _, live_price_warnings = (
                build_report_payload(
                    args=args,
                    portfolio=portfolio,
                    store=store,
                    print_live_price_warnings=not args.json,
                )
            )
            message = f"Generated scheduled report for {trading.calendar_date}."
            result = ScheduledReportResult(
                status=ScheduledReportStatus.GENERATED,
                run_context=args.run_context,
                trading_day=trading.as_dict(),
                report=payload,
                saved_report_id=saved_run.id if saved_run else None,
                comparison=payload.get("comparison")
                if isinstance(payload.get("comparison"), dict)
                else None,
                message=message,
                warnings=live_price_warnings,
            )
            notification = None
            if args.email:
                notification = _notify(build_scheduled_success_email, result)
                if notification is not None and notification.warnings:
                    result = replace(
                        result,
                        warnings=result.warnings + tuple(notification.warnings),
                    )
                if notification is not None:
                    result = replace(result, notification=notification.as_dict())

            if args.json:
                print(json.dumps(result.as_dict(), indent=2))
            elif args.markdown or not args.json:
                print(report.to_markdown())
                if notification is not None and not notification.sent:
                    print(
                        f"Warning: {notification.error or 'unable to send email notification'}"
                    )
            return 0
        except Exception:
            message = "Scheduled report failed unexpectedly."
            result = ScheduledReportResult(
                status=ScheduledReportStatus.FAILED,
                run_context=args.run_context,
                trading_day=trading.as_dict(),
                report=None,
                saved_report_id=None,
                comparison=None,
                message=message,
                warnings=(),
            )
            if args.email_on_failure:
                notification = _notify(build_scheduled_failure_email, result)
                if notification is not None:
                    result = replace(result, notification=notification.as_dict())
            if args.json:
                print(json.dumps(result.as_dict(), indent=2))
            else:
                print(message)
            return 1

    if args.command == "market-index":
        provider = build_market_data_provider(
            settings.market_data_provider,
            settings.market_data_timeout_seconds,
        )
        quote = provider.get_index_quote(args.symbol)

        if quote.available and quote.price is not None:
            print(f"{args.symbol}: {quote.price} ({quote.source})")
            return 0

        print(f"{args.symbol}: unavailable ({quote.error or 'unknown error'})")
        return 1

    if args.command == "add-cash":
        portfolio = upsert_cash(portfolio, args.currency, args.amount)
    elif args.command == "withdraw-cash":
        portfolio = upsert_cash(portfolio, args.currency, -args.amount)
    elif args.command == "add-holding":
        portfolio = add_holding(
            portfolio,
            args.ticker,
            args.shares,
            args.average_price,
            args.sector,
        )
    elif args.command == "record-buy":
        portfolio = record_buy(
            portfolio,
            args.ticker,
            args.shares,
            args.price,
            args.currency,
            parse_date(args.date),
        )
    elif args.command == "record-sell":
        portfolio = record_sell(
            portfolio,
            args.ticker,
            args.shares,
            args.price,
            args.currency,
            parse_date(args.date),
        )
    elif args.command in {"add-order", "update-order"}:
        order = ActiveOrder(
            args.ticker,
            OrderSide(args.side),
            OrderType(args.order_type),
            args.shares,
            args.limit_price,
            args.stop_price,
        )
        portfolio = add_or_update_order(portfolio, order)
    elif args.command == "remove-order":
        portfolio = remove_order(portfolio, args.ticker)
    elif args.command == "add-watchlist":
        portfolio = add_watchlist_item(portfolio, args.ticker, args.note)
    elif args.command == "remove-watchlist":
        portfolio = remove_watchlist_item(portfolio, args.ticker)
    elif args.command == "set-goal":
        portfolio = set_goal(portfolio, args.name, args.target_amount)
    elif args.command == "set-timeline":
        portfolio = set_timeline(
            portfolio,
            date.fromisoformat(args.start_date),
            parse_optional_date(args.target_date),
        )
    elif args.command == "set-risk":
        portfolio = set_risk_profile(portfolio, RiskLevel(args.level), args.notes)
    else:
        parser.error(f"unsupported command: {args.command}")

    save_portfolio_update(store, args.portfolio, portfolio, existing_transactions)
    return 0


def main() -> None:
    raise SystemExit(run())
