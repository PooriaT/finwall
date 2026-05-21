from dataclasses import replace
from datetime import date
from decimal import Decimal

from finwall.models import (
    ActiveOrder,
    CashBalance,
    Holding,
    InvestmentGoal,
    Portfolio,
    RiskLevel,
    RiskProfile,
    Timeline,
    TradeSide,
    TradeTransaction,
    WatchlistItem,
)
from finwall.storage_interface import PortfolioStore


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
        holdings = holdings + (
            Holding(
                ticker, remaining, existing.average_purchase_price, existing.sector
            ),
        )
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
    portfolio: Portfolio, name: str, target_amount: Decimal | None
) -> Portfolio:
    timeline = portfolio.goals[0].timeline if portfolio.goals else None
    return replace(portfolio, goals=(InvestmentGoal(name, target_amount, timeline),))


def set_timeline(
    portfolio: Portfolio, start_date: date, target_date: date | None
) -> Portfolio:
    timeline = Timeline(start_date, target_date)
    goal = portfolio.goals[0] if portfolio.goals else InvestmentGoal("Default goal")
    return replace(portfolio, goals=(replace(goal, timeline=timeline),))


def set_risk_profile(
    portfolio: Portfolio, level: RiskLevel, notes: str | None
) -> Portfolio:
    return replace(portfolio, risk_profile=RiskProfile(level, notes))


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
