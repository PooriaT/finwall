import argparse
from dataclasses import replace
from datetime import date
from decimal import Decimal

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
from finwall.storage import SQLitePortfolioStore

DEFAULT_PORTFOLIO = "Primary"


def load_portfolio(store: SQLitePortfolioStore, name: str) -> Portfolio:
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
    existing = next((item for item in portfolio.holdings if item.ticker == ticker), None)
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
    existing = next((item for item in portfolio.holdings if item.ticker == ticker), None)
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
    transaction = TradeTransaction(ticker, TradeSide.SELL, share_count, price, traded_on)
    return replace(
        portfolio,
        holdings=holdings,
        transactions=portfolio.transactions + (transaction,),
    )


def add_or_update_order(portfolio: Portfolio, order: ActiveOrder) -> Portfolio:
    orders = tuple(item for item in portfolio.active_orders if item.ticker != order.ticker)
    return replace(portfolio, active_orders=orders + (order,))


def remove_order(portfolio: Portfolio, ticker: str) -> Portfolio:
    orders = tuple(item for item in portfolio.active_orders if item.ticker != ticker)
    return replace(portfolio, active_orders=orders)


def add_watchlist_item(portfolio: Portfolio, ticker: str, note: str | None) -> Portfolio:
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


def save_updated(args: argparse.Namespace, portfolio: Portfolio) -> None:
    store = SQLitePortfolioStore(args.database)
    store.initialize()
    store.save_portfolio(portfolio)


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
    return parser


def add_order_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("ticker")
    parser.add_argument("side", choices=[item.value for item in OrderSide])
    parser.add_argument("order_type", choices=[item.value for item in OrderType])
    parser.add_argument("shares", type=parse_decimal)
    parser.add_argument("--limit-price", type=parse_decimal)
    parser.add_argument("--stop-price", type=parse_decimal)


def run(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    store = SQLitePortfolioStore(args.database)
    store.initialize()
    portfolio = load_portfolio(store, args.portfolio)

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

    store.save_portfolio(portfolio)
    return 0


def main() -> None:
    raise SystemExit(run())
