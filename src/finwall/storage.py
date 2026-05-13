import sqlite3
from collections.abc import Iterable
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Any

from finwall.models import (
    ActiveOrder,
    CashBalance,
    Holding,
    InvestmentGoal,
    OrderSide,
    OrderType,
    Portfolio,
    RecommendationRecord,
    RiskLevel,
    RiskProfile,
    Timeline,
    TradeSide,
    TradeTransaction,
    WatchlistItem,
)

SCHEMA = """
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS portfolios (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    risk_level TEXT,
    risk_notes TEXT
);

CREATE TABLE IF NOT EXISTS cash_balances (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    portfolio_id INTEGER NOT NULL REFERENCES portfolios(id) ON DELETE CASCADE,
    currency TEXT NOT NULL,
    amount TEXT NOT NULL,
    UNIQUE(portfolio_id, currency)
);

CREATE TABLE IF NOT EXISTS cash_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    portfolio_id INTEGER NOT NULL REFERENCES portfolios(id) ON DELETE CASCADE,
    currency TEXT NOT NULL,
    amount TEXT NOT NULL,
    recorded_on TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS holdings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    portfolio_id INTEGER NOT NULL REFERENCES portfolios(id) ON DELETE CASCADE,
    ticker TEXT NOT NULL,
    share_count TEXT NOT NULL,
    average_purchase_price TEXT NOT NULL,
    sector TEXT,
    UNIQUE(portfolio_id, ticker)
);

CREATE TABLE IF NOT EXISTS trade_transactions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    portfolio_id INTEGER NOT NULL REFERENCES portfolios(id) ON DELETE CASCADE,
    ticker TEXT NOT NULL,
    side TEXT NOT NULL,
    share_count TEXT NOT NULL,
    price TEXT NOT NULL,
    traded_on TEXT NOT NULL,
    fees TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS active_orders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    portfolio_id INTEGER NOT NULL REFERENCES portfolios(id) ON DELETE CASCADE,
    ticker TEXT NOT NULL,
    side TEXT NOT NULL,
    order_type TEXT NOT NULL,
    share_count TEXT NOT NULL,
    limit_price TEXT,
    stop_price TEXT
);

CREATE TABLE IF NOT EXISTS watchlist_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    portfolio_id INTEGER NOT NULL REFERENCES portfolios(id) ON DELETE CASCADE,
    ticker TEXT NOT NULL,
    note TEXT,
    UNIQUE(portfolio_id, ticker)
);

CREATE TABLE IF NOT EXISTS investment_goals (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    portfolio_id INTEGER NOT NULL REFERENCES portfolios(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    target_amount TEXT,
    start_date TEXT,
    target_date TEXT
);

CREATE TABLE IF NOT EXISTS recommendation_records (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    portfolio_id INTEGER NOT NULL REFERENCES portfolios(id) ON DELETE CASCADE,
    title TEXT NOT NULL,
    summary TEXT NOT NULL,
    created_on TEXT NOT NULL
);
"""


class SQLitePortfolioStore:
    def __init__(self, database_path: str | Path) -> None:
        self.database_path = Path(database_path)

    def initialize(self) -> None:
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as connection:
            connection.executescript(SCHEMA)

    def save_portfolio(self, portfolio: Portfolio) -> None:
        self._validate_portfolio(portfolio)
        with self._connect() as connection:
            portfolio_id = self._upsert_portfolio(connection, portfolio)
            self._replace_portfolio_rows(connection, portfolio_id, portfolio)

    def get_portfolio(self, name: str) -> Portfolio | None:
        with self._connect() as connection:
            portfolio_row = connection.execute(
                "SELECT id, name, risk_level, risk_notes FROM portfolios WHERE name = ?",
                (name,),
            ).fetchone()
            if portfolio_row is None:
                return None

            portfolio_id = portfolio_row["id"]
            risk_profile = self._read_risk_profile(portfolio_row)

            return Portfolio(
                name=portfolio_row["name"],
                cash_balances=self._read_cash_balances(connection, portfolio_id),
                holdings=self._read_holdings(connection, portfolio_id),
                transactions=self._read_trade_transactions(connection, portfolio_id),
                active_orders=self._read_active_orders(connection, portfolio_id),
                watchlist=self._read_watchlist(connection, portfolio_id),
                goals=self._read_goals(connection, portfolio_id),
                risk_profile=risk_profile,
                recommendations=self._read_recommendations(connection, portfolio_id),
            )

    def delete_portfolio(self, name: str) -> None:
        with self._connect() as connection:
            connection.execute("DELETE FROM portfolios WHERE name = ?", (name,))

    def add_trade_transaction(self, portfolio_name: str, transaction: TradeTransaction) -> None:
        with self._connect() as connection:
            portfolio_id = self._require_portfolio_id(connection, portfolio_name)
            self._insert_trade_transaction(connection, portfolio_id, transaction)

    def list_trade_transactions(self, portfolio_name: str) -> tuple[TradeTransaction, ...]:
        with self._connect() as connection:
            portfolio_id = self._require_portfolio_id(connection, portfolio_name)
            return self._read_trade_transactions(connection, portfolio_id)

    def record_cash_history(self, portfolio_name: str, cash_balance: CashBalance, recorded_on: date) -> None:
        with self._connect() as connection:
            portfolio_id = self._require_portfolio_id(connection, portfolio_name)
            connection.execute(
                """
                INSERT INTO cash_history (portfolio_id, currency, amount, recorded_on)
                VALUES (?, ?, ?, ?)
                """,
                (portfolio_id, cash_balance.currency, str(cash_balance.amount), recorded_on.isoformat()),
            )

    def list_cash_history(self, portfolio_name: str) -> tuple[tuple[CashBalance, date], ...]:
        with self._connect() as connection:
            portfolio_id = self._require_portfolio_id(connection, portfolio_name)
            rows = connection.execute(
                """
                SELECT currency, amount, recorded_on
                FROM cash_history
                WHERE portfolio_id = ?
                ORDER BY id
                """,
                (portfolio_id,),
            ).fetchall()
            return tuple(
                (CashBalance(row["currency"], Decimal(row["amount"])), date.fromisoformat(row["recorded_on"]))
                for row in rows
            )

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database_path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        return connection

    def _upsert_portfolio(self, connection: sqlite3.Connection, portfolio: Portfolio) -> int:
        risk_level = portfolio.risk_profile.level.value if portfolio.risk_profile is not None else None
        risk_notes = portfolio.risk_profile.notes if portfolio.risk_profile is not None else None
        connection.execute(
            """
            INSERT INTO portfolios (name, risk_level, risk_notes)
            VALUES (?, ?, ?)
            ON CONFLICT(name) DO UPDATE SET
                risk_level = excluded.risk_level,
                risk_notes = excluded.risk_notes
            """,
            (portfolio.name, risk_level, risk_notes),
        )
        return self._require_portfolio_id(connection, portfolio.name)

    def _replace_portfolio_rows(
        self,
        connection: sqlite3.Connection,
        portfolio_id: int,
        portfolio: Portfolio,
    ) -> None:
        for table in (
            "cash_balances",
            "holdings",
            "active_orders",
            "watchlist_items",
            "investment_goals",
            "recommendation_records",
        ):
            connection.execute(f"DELETE FROM {table} WHERE portfolio_id = ?", (portfolio_id,))

        for cash_balance in portfolio.cash_balances:
            connection.execute(
                """
                INSERT INTO cash_balances (portfolio_id, currency, amount)
                VALUES (?, ?, ?)
                """,
                (portfolio_id, cash_balance.currency, str(cash_balance.amount)),
            )

        for holding in portfolio.holdings:
            connection.execute(
                """
                INSERT INTO holdings (
                    portfolio_id, ticker, share_count, average_purchase_price, sector
                ) VALUES (?, ?, ?, ?, ?)
                """,
                (
                    portfolio_id,
                    holding.ticker,
                    str(holding.share_count),
                    str(holding.average_purchase_price),
                    holding.sector,
                ),
            )

        for transaction in portfolio.transactions:
            self._insert_trade_transaction(connection, portfolio_id, transaction)

        for order in portfolio.active_orders:
            connection.execute(
                """
                INSERT INTO active_orders (
                    portfolio_id, ticker, side, order_type, share_count, limit_price, stop_price
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    portfolio_id,
                    order.ticker,
                    order.side.value,
                    order.order_type.value,
                    str(order.share_count),
                    self._decimal_to_text(order.limit_price),
                    self._decimal_to_text(order.stop_price),
                ),
            )

        for item in portfolio.watchlist:
            connection.execute(
                """
                INSERT INTO watchlist_items (portfolio_id, ticker, note)
                VALUES (?, ?, ?)
                """,
                (portfolio_id, item.ticker, item.note),
            )

        for goal in portfolio.goals:
            start_date = goal.timeline.start_date.isoformat() if goal.timeline is not None else None
            target_date = goal.timeline.target_date.isoformat() if goal.timeline and goal.timeline.target_date else None
            connection.execute(
                """
                INSERT INTO investment_goals (
                    portfolio_id, name, target_amount, start_date, target_date
                ) VALUES (?, ?, ?, ?, ?)
                """,
                (
                    portfolio_id,
                    goal.name,
                    self._decimal_to_text(goal.target_amount),
                    start_date,
                    target_date,
                ),
            )

        for recommendation in portfolio.recommendations:
            connection.execute(
                """
                INSERT INTO recommendation_records (portfolio_id, title, summary, created_on)
                VALUES (?, ?, ?, ?)
                """,
                (
                    portfolio_id,
                    recommendation.title,
                    recommendation.summary,
                    recommendation.created_on.isoformat(),
                ),
            )

    def _insert_trade_transaction(
        self,
        connection: sqlite3.Connection,
        portfolio_id: int,
        transaction: TradeTransaction,
    ) -> None:
        connection.execute(
            """
            INSERT INTO trade_transactions (
                portfolio_id, ticker, side, share_count, price, traded_on, fees
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                portfolio_id,
                transaction.ticker,
                transaction.side.value,
                str(transaction.share_count),
                str(transaction.price),
                transaction.traded_on.isoformat(),
                str(transaction.fees),
            ),
        )

    def _require_portfolio_id(self, connection: sqlite3.Connection, name: str) -> int:
        row = connection.execute("SELECT id FROM portfolios WHERE name = ?", (name,)).fetchone()
        if row is None:
            raise ValueError(f"portfolio does not exist: {name}")
        return int(row["id"])

    def _read_risk_profile(self, row: sqlite3.Row) -> RiskProfile | None:
        if row["risk_level"] is None:
            return None
        return RiskProfile(level=RiskLevel(row["risk_level"]), notes=row["risk_notes"])

    def _read_cash_balances(
        self,
        connection: sqlite3.Connection,
        portfolio_id: int,
    ) -> tuple[CashBalance, ...]:
        rows = connection.execute(
            "SELECT currency, amount FROM cash_balances WHERE portfolio_id = ? ORDER BY currency",
            (portfolio_id,),
        ).fetchall()
        return tuple(CashBalance(row["currency"], Decimal(row["amount"])) for row in rows)

    def _read_holdings(
        self,
        connection: sqlite3.Connection,
        portfolio_id: int,
    ) -> tuple[Holding, ...]:
        rows = connection.execute(
            """
            SELECT ticker, share_count, average_purchase_price, sector
            FROM holdings
            WHERE portfolio_id = ?
            ORDER BY ticker
            """,
            (portfolio_id,),
        ).fetchall()
        return tuple(
            Holding(
                ticker=row["ticker"],
                share_count=Decimal(row["share_count"]),
                average_purchase_price=Decimal(row["average_purchase_price"]),
                sector=row["sector"],
            )
            for row in rows
        )

    def _read_trade_transactions(
        self,
        connection: sqlite3.Connection,
        portfolio_id: int,
    ) -> tuple[TradeTransaction, ...]:
        rows = connection.execute(
            """
            SELECT ticker, side, share_count, price, traded_on, fees
            FROM trade_transactions
            WHERE portfolio_id = ?
            ORDER BY id
            """,
            (portfolio_id,),
        ).fetchall()
        return tuple(
            TradeTransaction(
                ticker=row["ticker"],
                side=TradeSide(row["side"]),
                share_count=Decimal(row["share_count"]),
                price=Decimal(row["price"]),
                traded_on=date.fromisoformat(row["traded_on"]),
                fees=Decimal(row["fees"]),
            )
            for row in rows
        )

    def _read_active_orders(
        self,
        connection: sqlite3.Connection,
        portfolio_id: int,
    ) -> tuple[ActiveOrder, ...]:
        rows = connection.execute(
            """
            SELECT ticker, side, order_type, share_count, limit_price, stop_price
            FROM active_orders
            WHERE portfolio_id = ?
            ORDER BY id
            """,
            (portfolio_id,),
        ).fetchall()
        return tuple(
            ActiveOrder(
                ticker=row["ticker"],
                side=OrderSide(row["side"]),
                order_type=OrderType(row["order_type"]),
                share_count=Decimal(row["share_count"]),
                limit_price=self._text_to_decimal(row["limit_price"]),
                stop_price=self._text_to_decimal(row["stop_price"]),
            )
            for row in rows
        )

    def _read_watchlist(
        self,
        connection: sqlite3.Connection,
        portfolio_id: int,
    ) -> tuple[WatchlistItem, ...]:
        rows = connection.execute(
            "SELECT ticker, note FROM watchlist_items WHERE portfolio_id = ? ORDER BY ticker",
            (portfolio_id,),
        ).fetchall()
        return tuple(WatchlistItem(ticker=row["ticker"], note=row["note"]) for row in rows)

    def _read_goals(
        self,
        connection: sqlite3.Connection,
        portfolio_id: int,
    ) -> tuple[InvestmentGoal, ...]:
        rows = connection.execute(
            """
            SELECT name, target_amount, start_date, target_date
            FROM investment_goals
            WHERE portfolio_id = ?
            ORDER BY id
            """,
            (portfolio_id,),
        ).fetchall()
        return tuple(
            InvestmentGoal(
                name=row["name"],
                target_amount=self._text_to_decimal(row["target_amount"]),
                timeline=self._read_timeline(row),
            )
            for row in rows
        )

    def _read_recommendations(
        self,
        connection: sqlite3.Connection,
        portfolio_id: int,
    ) -> tuple[RecommendationRecord, ...]:
        rows = connection.execute(
            """
            SELECT title, summary, created_on
            FROM recommendation_records
            WHERE portfolio_id = ?
            ORDER BY id
            """,
            (portfolio_id,),
        ).fetchall()
        return tuple(
            RecommendationRecord(
                title=row["title"],
                summary=row["summary"],
                created_on=date.fromisoformat(row["created_on"]),
            )
            for row in rows
        )

    def _read_timeline(self, row: sqlite3.Row) -> Timeline | None:
        if row["start_date"] is None:
            return None
        target_date = date.fromisoformat(row["target_date"]) if row["target_date"] else None
        return Timeline(start_date=date.fromisoformat(row["start_date"]), target_date=target_date)

    def _validate_portfolio(self, portfolio: Portfolio) -> None:
        if not isinstance(portfolio, Portfolio):
            raise ValueError("portfolio must be a Portfolio instance")
        self._validate_items(portfolio.cash_balances, CashBalance, "cash_balances")
        self._validate_items(portfolio.holdings, Holding, "holdings")
        self._validate_items(portfolio.transactions, TradeTransaction, "transactions")
        self._validate_items(portfolio.active_orders, ActiveOrder, "active_orders")
        self._validate_items(portfolio.watchlist, WatchlistItem, "watchlist")
        self._validate_items(portfolio.goals, InvestmentGoal, "goals")
        self._validate_items(portfolio.recommendations, RecommendationRecord, "recommendations")
        if portfolio.risk_profile is not None and not isinstance(portfolio.risk_profile, RiskProfile):
            raise ValueError("risk_profile must be a RiskProfile instance")

    def _validate_items(self, items: Iterable[Any], item_type: type, field_name: str) -> None:
        if not all(isinstance(item, item_type) for item in items):
            raise ValueError(f"{field_name} contains invalid items")

    def _decimal_to_text(self, value: Decimal | None) -> str | None:
        return str(value) if value is not None else None

    def _text_to_decimal(self, value: str | None) -> Decimal | None:
        return Decimal(value) if value is not None else None
