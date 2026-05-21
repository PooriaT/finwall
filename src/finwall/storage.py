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
from finwall.portfolio_audit import PortfolioAuditEvent
from finwall.recommendations import RecommendationReport
from finwall.report_history import (
    StoredRecommendationStatus,
    StoredReportRun,
    StoredRiskWarning,
    StoredSuggestedOrder,
)
from finwall.reports import DecisionSupportReport
from finwall.risk import RiskAssessment
from finwall.scheduled_report import StoredScheduledRun

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

CREATE TABLE IF NOT EXISTS report_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    portfolio_id INTEGER NOT NULL REFERENCES portfolios(id) ON DELETE CASCADE,
    created_at TEXT NOT NULL,
    command_context TEXT NOT NULL,
    report_summary TEXT NOT NULL,
    report_json TEXT NOT NULL,
    price_completeness_status TEXT,
    valuation_status TEXT,
    recommendation_summary TEXT
);

CREATE TABLE IF NOT EXISTS report_recommendation_statuses (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    report_run_id INTEGER NOT NULL REFERENCES report_runs(id) ON DELETE CASCADE,
    ticker TEXT NOT NULL,
    status TEXT NOT NULL,
    confidence TEXT NOT NULL,
    risk_level TEXT NOT NULL,
    blocked_by_risk INTEGER NOT NULL,
    suggested_action TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS report_risk_warnings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    report_run_id INTEGER NOT NULL REFERENCES report_runs(id) ON DELETE CASCADE,
    code TEXT NOT NULL,
    severity TEXT NOT NULL,
    ticker TEXT,
    message TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS report_suggested_orders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    report_run_id INTEGER NOT NULL REFERENCES report_runs(id) ON DELETE CASCADE,
    ticker TEXT NOT NULL,
    side TEXT NOT NULL,
    order_type TEXT NOT NULL,
    share_count TEXT NOT NULL,
    limit_price TEXT,
    stop_price TEXT,
    description TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS portfolio_audit_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    portfolio_id INTEGER NOT NULL REFERENCES portfolios(id) ON DELETE CASCADE,
    changed_at TEXT NOT NULL,
    actor TEXT NOT NULL,
    source TEXT NOT NULL,
    action TEXT NOT NULL,
    entity_type TEXT NOT NULL,
    entity_id TEXT,
    status TEXT NOT NULL,
    summary TEXT NOT NULL,
    before_json TEXT,
    after_json TEXT,
    safe_error_message TEXT
);

CREATE TABLE IF NOT EXISTS scheduled_report_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    portfolio_id INTEGER NOT NULL REFERENCES portfolios(id) ON DELETE CASCADE,
    run_date TEXT NOT NULL,
    run_context TEXT NOT NULL,
    status TEXT NOT NULL,
    started_at TEXT NOT NULL,
    finished_at TEXT,
    report_run_id INTEGER REFERENCES report_runs(id),
    notification_attempted INTEGER NOT NULL DEFAULT 0,
    notification_sent INTEGER NOT NULL DEFAULT 0,
    notification_provider TEXT,
    error_category TEXT NOT NULL,
    safe_error_message TEXT,
    UNIQUE(portfolio_id, run_date, run_context)
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

    def add_trade_transaction(
        self, portfolio_name: str, transaction: TradeTransaction
    ) -> None:
        with self._connect() as connection:
            portfolio_id = self._require_portfolio_id(connection, portfolio_name)
            self._insert_trade_transaction(connection, portfolio_id, transaction)

    def list_trade_transactions(
        self, portfolio_name: str
    ) -> tuple[TradeTransaction, ...]:
        with self._connect() as connection:
            portfolio_id = self._require_portfolio_id(connection, portfolio_name)
            return self._read_trade_transactions(connection, portfolio_id)

    def record_cash_history(
        self,
        portfolio_name: str,
        cash_balance: CashBalance,
        recorded_on: date,
    ) -> None:
        with self._connect() as connection:
            portfolio_id = self._require_portfolio_id(connection, portfolio_name)
            connection.execute(
                """
                INSERT INTO cash_history (portfolio_id, currency, amount, recorded_on)
                VALUES (?, ?, ?, ?)
                """,
                (
                    portfolio_id,
                    cash_balance.currency,
                    str(cash_balance.amount),
                    recorded_on.isoformat(),
                ),
            )

    def list_cash_history(
        self, portfolio_name: str
    ) -> tuple[tuple[CashBalance, date], ...]:
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
                (
                    CashBalance(row["currency"], Decimal(row["amount"])),
                    date.fromisoformat(row["recorded_on"]),
                )
                for row in rows
            )

    def save_report_run(
        self,
        portfolio_name: str,
        report: DecisionSupportReport,
        recommendation_report: RecommendationReport,
        risk_assessment: RiskAssessment,
        command_context: str,
    ) -> int:
        with self._connect() as connection:
            portfolio_id = self._require_portfolio_id(connection, portfolio_name)
            report_run = connection.execute(
                """
                INSERT INTO report_runs (
                    portfolio_id, created_at, command_context, report_summary, report_json,
                    price_completeness_status, valuation_status, recommendation_summary
                ) VALUES (?, datetime('now'), ?, ?, ?, ?, ?, ?)
                """,
                (
                    portfolio_id,
                    command_context,
                    report.strategy_assessment.summary,
                    report.to_json(),
                    report.portfolio_snapshot.get("price_coverage"),
                    report.portfolio_snapshot.get("valuation_status"),
                    recommendation_report.summary,
                ),
            )
            report_run_id = int(report_run.lastrowid)
            for holding in recommendation_report.holdings:
                connection.execute(
                    """
                    INSERT INTO report_recommendation_statuses (
                        report_run_id, ticker, status, confidence, risk_level,
                        blocked_by_risk, suggested_action
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        report_run_id,
                        holding.ticker,
                        holding.status.value,
                        holding.confidence.value,
                        holding.risk_level.value,
                        int(holding.blocked_by_risk),
                        holding.suggested_action,
                    ),
                )
            for warning in risk_assessment.warnings:
                connection.execute(
                    """
                    INSERT INTO report_risk_warnings (
                        report_run_id, code, severity, ticker, message
                    ) VALUES (?, ?, ?, ?, ?)
                    """,
                    (
                        report_run_id,
                        warning.code,
                        warning.severity,
                        warning.ticker,
                        warning.message,
                    ),
                )
            for order in report.suggested_orders.active_orders:
                connection.execute(
                    """
                    INSERT INTO report_suggested_orders (
                        report_run_id, ticker, side, order_type, share_count,
                        limit_price, stop_price, description
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        report_run_id,
                        order["ticker"],
                        order["side"],
                        order["order_type"],
                        str(order["share_count"]),
                        self._decimal_to_text(order["limit_price"]),
                        self._decimal_to_text(order["stop_price"]),
                        order["description"],
                    ),
                )
            return report_run_id

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database_path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        return connection

    def get_latest_report_run(self, portfolio_name: str) -> StoredReportRun | None:
        with self._connect() as connection:
            portfolio_id = self._require_portfolio_id(connection, portfolio_name)
            row = connection.execute(
                """
                SELECT rr.id, p.name AS portfolio_name, rr.created_at, rr.command_context,
                       rr.report_summary, rr.report_json, rr.price_completeness_status,
                       rr.valuation_status, rr.recommendation_summary
                FROM report_runs rr
                INNER JOIN portfolios p ON p.id = rr.portfolio_id
                WHERE rr.portfolio_id = ?
                ORDER BY rr.id DESC
                LIMIT 1
                """,
                (portfolio_id,),
            ).fetchone()
            return self._to_stored_report_run(row) if row is not None else None

    def get_previous_report_run(
        self, portfolio_name: str, before_report_id: int
    ) -> StoredReportRun | None:
        with self._connect() as connection:
            portfolio_id = self._require_portfolio_id(connection, portfolio_name)
            row = connection.execute(
                """
                SELECT rr.id, p.name AS portfolio_name, rr.created_at, rr.command_context,
                       rr.report_summary, rr.report_json, rr.price_completeness_status,
                       rr.valuation_status, rr.recommendation_summary
                FROM report_runs rr
                INNER JOIN portfolios p ON p.id = rr.portfolio_id
                WHERE rr.portfolio_id = ? AND rr.id < ?
                ORDER BY rr.id DESC
                LIMIT 1
                """,
                (portfolio_id, before_report_id),
            ).fetchone()
            return self._to_stored_report_run(row) if row is not None else None

    def list_report_runs(
        self, portfolio_name: str, limit: int = 10
    ) -> tuple[StoredReportRun, ...]:
        with self._connect() as connection:
            portfolio_id = self._require_portfolio_id(connection, portfolio_name)
            rows = connection.execute(
                """
                SELECT rr.id, p.name AS portfolio_name, rr.created_at, rr.command_context,
                       rr.report_summary, rr.report_json, rr.price_completeness_status,
                       rr.valuation_status, rr.recommendation_summary
                FROM report_runs rr
                INNER JOIN portfolios p ON p.id = rr.portfolio_id
                WHERE rr.portfolio_id = ?
                ORDER BY rr.id DESC
                LIMIT ?
                """,
                (portfolio_id, limit),
            ).fetchall()
            return tuple(self._to_stored_report_run(row) for row in rows)

    def list_report_recommendation_statuses(
        self, report_run_id: int
    ) -> tuple[StoredRecommendationStatus, ...]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT ticker, status, confidence, risk_level, blocked_by_risk, suggested_action
                FROM report_recommendation_statuses
                WHERE report_run_id = ?
                ORDER BY ticker
                """,
                (report_run_id,),
            ).fetchall()
            return tuple(
                StoredRecommendationStatus(
                    ticker=row["ticker"],
                    status=row["status"],
                    confidence=row["confidence"],
                    risk_level=row["risk_level"],
                    blocked_by_risk=bool(row["blocked_by_risk"]),
                    suggested_action=row["suggested_action"],
                )
                for row in rows
            )

    def list_report_risk_warnings(
        self, report_run_id: int
    ) -> tuple[StoredRiskWarning, ...]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT code, severity, ticker, message
                FROM report_risk_warnings
                WHERE report_run_id = ?
                ORDER BY id
                """,
                (report_run_id,),
            ).fetchall()
            return tuple(
                StoredRiskWarning(
                    code=row["code"],
                    severity=row["severity"],
                    ticker=row["ticker"],
                    message=row["message"],
                )
                for row in rows
            )

    def list_report_suggested_orders(
        self, report_run_id: int
    ) -> tuple[StoredSuggestedOrder, ...]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT ticker, side, order_type, share_count, limit_price, stop_price, description
                FROM report_suggested_orders
                WHERE report_run_id = ?
                ORDER BY id
                """,
                (report_run_id,),
            ).fetchall()
            return tuple(
                StoredSuggestedOrder(
                    ticker=row["ticker"],
                    side=row["side"],
                    order_type=row["order_type"],
                    share_count=row["share_count"],
                    limit_price=row["limit_price"],
                    stop_price=row["stop_price"],
                    description=row["description"],
                )
                for row in rows
            )


    def record_portfolio_audit_event(
        self,
        portfolio_name: str,
        *,
        actor: str,
        source: str,
        action: str,
        entity_type: str,
        entity_id: str | None,
        status: str,
        summary: str,
        before_json: str | None,
        after_json: str | None,
        safe_error_message: str | None,
    ) -> int:
        with self._connect() as connection:
            portfolio_id = self._require_portfolio_id(connection, portfolio_name)
            row = connection.execute(
                """
                INSERT INTO portfolio_audit_events (
                    portfolio_id, changed_at, actor, source, action, entity_type,
                    entity_id, status, summary, before_json, after_json, safe_error_message
                ) VALUES (?, datetime('now'), ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    portfolio_id,
                    actor,
                    source,
                    action,
                    entity_type,
                    entity_id,
                    status,
                    summary,
                    before_json,
                    after_json,
                    safe_error_message,
                ),
            )
            return int(row.lastrowid)

    def list_portfolio_audit_events(
        self,
        portfolio_name: str,
        limit: int = 50,
    ) -> tuple[PortfolioAuditEvent, ...]:
        with self._connect() as connection:
            portfolio_id = self._require_portfolio_id(connection, portfolio_name)
            rows = connection.execute(
                """
                SELECT pae.id, p.name AS portfolio_name, pae.changed_at, pae.actor, pae.source,
                       pae.action, pae.entity_type, pae.entity_id, pae.status, pae.summary,
                       pae.before_json, pae.after_json, pae.safe_error_message
                FROM portfolio_audit_events pae
                INNER JOIN portfolios p ON p.id = pae.portfolio_id
                WHERE pae.portfolio_id = ?
                ORDER BY pae.id DESC
                LIMIT ?
                """,
                (portfolio_id, limit),
            ).fetchall()
            return tuple(
                PortfolioAuditEvent(
                    id=row["id"],
                    portfolio_name=row["portfolio_name"],
                    changed_at=row["changed_at"],
                    actor=row["actor"],
                    source=row["source"],
                    action=row["action"],
                    entity_type=row["entity_type"],
                    entity_id=row["entity_id"],
                    status=row["status"],
                    summary=row["summary"],
                    before_json=row["before_json"],
                    after_json=row["after_json"],
                    safe_error_message=row["safe_error_message"],
                )
                for row in rows
            )

    def get_scheduled_run(
        self, portfolio_name: str, run_date: str, run_context: str
    ) -> StoredScheduledRun | None:
        with self._connect() as connection:
            portfolio_id = self._require_portfolio_id(connection, portfolio_name)
            row = connection.execute(
                """
                SELECT srr.*, p.name AS portfolio_name
                FROM scheduled_report_runs srr
                INNER JOIN portfolios p ON p.id = srr.portfolio_id
                WHERE srr.portfolio_id = ? AND srr.run_date = ? AND srr.run_context = ?
                """,
                (portfolio_id, run_date, run_context),
            ).fetchone()
            return self._to_stored_scheduled_run(row) if row is not None else None

    def start_scheduled_run(
        self, portfolio_name: str, run_date: str, run_context: str
    ) -> StoredScheduledRun:
        with self._connect() as connection:
            portfolio_id = self._require_portfolio_id(connection, portfolio_name)
            connection.execute(
                """
                INSERT INTO scheduled_report_runs (
                    portfolio_id, run_date, run_context, status, started_at, error_category
                ) VALUES (?, ?, ?, 'started', datetime('now'), 'none')
                ON CONFLICT(portfolio_id, run_date, run_context) DO UPDATE SET
                    status = CASE
                        WHEN scheduled_report_runs.status = 'failed' THEN 'started'
                        ELSE scheduled_report_runs.status
                    END,
                    started_at = CASE
                        WHEN scheduled_report_runs.status = 'failed' THEN datetime('now')
                        ELSE scheduled_report_runs.started_at
                    END,
                    finished_at = CASE
                        WHEN scheduled_report_runs.status = 'failed' THEN NULL
                        ELSE scheduled_report_runs.finished_at
                    END
                """,
                (portfolio_id, run_date, run_context),
            )
            row = connection.execute(
                """
                SELECT srr.*, p.name AS portfolio_name
                FROM scheduled_report_runs srr
                INNER JOIN portfolios p ON p.id = srr.portfolio_id
                WHERE srr.portfolio_id = ? AND srr.run_date = ? AND srr.run_context = ?
                """,
                (portfolio_id, run_date, run_context),
            ).fetchone()
            return self._to_stored_scheduled_run(row)

    def finish_scheduled_run(
        self,
        scheduled_run_id: int,
        *,
        status: str,
        report_run_id: int | None,
        notification_attempted: bool,
        notification_sent: bool,
        notification_provider: str | None,
        error_category: str,
        safe_error_message: str | None,
    ) -> StoredScheduledRun:
        with self._connect() as connection:
            connection.execute(
                """
                UPDATE scheduled_report_runs
                SET status = ?, finished_at = datetime('now'), report_run_id = ?,
                    notification_attempted = ?, notification_sent = ?,
                    notification_provider = ?, error_category = ?, safe_error_message = ?
                WHERE id = ?
                """,
                (
                    status,
                    report_run_id,
                    int(notification_attempted),
                    int(notification_sent),
                    notification_provider,
                    error_category,
                    safe_error_message,
                    scheduled_run_id,
                ),
            )
            row = connection.execute(
                """
                SELECT srr.*, p.name AS portfolio_name
                FROM scheduled_report_runs srr
                INNER JOIN portfolios p ON p.id = srr.portfolio_id
                WHERE srr.id = ?
                """,
                (scheduled_run_id,),
            ).fetchone()
            return self._to_stored_scheduled_run(row)

    def list_scheduled_runs(
        self, portfolio_name: str, limit: int = 10
    ) -> tuple[StoredScheduledRun, ...]:
        with self._connect() as connection:
            portfolio_id = self._require_portfolio_id(connection, portfolio_name)
            rows = connection.execute(
                """
                SELECT srr.*, p.name AS portfolio_name
                FROM scheduled_report_runs srr
                INNER JOIN portfolios p ON p.id = srr.portfolio_id
                WHERE srr.portfolio_id = ?
                ORDER BY srr.id DESC
                LIMIT ?
                """,
                (portfolio_id, limit),
            ).fetchall()
            return tuple(self._to_stored_scheduled_run(row) for row in rows)

    def _upsert_portfolio(
        self, connection: sqlite3.Connection, portfolio: Portfolio
    ) -> int:
        risk_level = (
            portfolio.risk_profile.level.value
            if portfolio.risk_profile is not None
            else None
        )
        risk_notes = (
            portfolio.risk_profile.notes if portfolio.risk_profile is not None else None
        )
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

    def _to_stored_report_run(self, row: sqlite3.Row) -> StoredReportRun:
        return StoredReportRun(
            id=row["id"],
            portfolio_name=row["portfolio_name"],
            created_at=row["created_at"],
            command_context=row["command_context"],
            report_summary=row["report_summary"],
            report_json=row["report_json"],
            price_completeness_status=row["price_completeness_status"],
            valuation_status=row["valuation_status"],
            recommendation_summary=row["recommendation_summary"],
        )

    def _to_stored_scheduled_run(self, row: sqlite3.Row) -> StoredScheduledRun:
        return StoredScheduledRun(
            id=row["id"],
            portfolio_name=row["portfolio_name"],
            run_date=row["run_date"],
            run_context=row["run_context"],
            status=row["status"],
            started_at=row["started_at"],
            finished_at=row["finished_at"],
            report_run_id=row["report_run_id"],
            notification_attempted=bool(row["notification_attempted"]),
            notification_sent=bool(row["notification_sent"]),
            notification_provider=row["notification_provider"],
            error_category=row["error_category"],
            safe_error_message=row["safe_error_message"],
        )

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
            connection.execute(
                f"DELETE FROM {table} WHERE portfolio_id = ?", (portfolio_id,)
            )

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
            start_date = (
                goal.timeline.start_date.isoformat()
                if goal.timeline is not None
                else None
            )
            target_date = (
                goal.timeline.target_date.isoformat()
                if goal.timeline and goal.timeline.target_date
                else None
            )
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
        row = connection.execute(
            "SELECT id FROM portfolios WHERE name = ?", (name,)
        ).fetchone()
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
        return tuple(
            CashBalance(row["currency"], Decimal(row["amount"])) for row in rows
        )

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
        return tuple(
            WatchlistItem(ticker=row["ticker"], note=row["note"]) for row in rows
        )

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
        target_date = (
            date.fromisoformat(row["target_date"]) if row["target_date"] else None
        )
        return Timeline(
            start_date=date.fromisoformat(row["start_date"]), target_date=target_date
        )

    def _validate_portfolio(self, portfolio: Portfolio) -> None:
        if not isinstance(portfolio, Portfolio):
            raise ValueError("portfolio must be a Portfolio instance")
        self._validate_items(portfolio.cash_balances, CashBalance, "cash_balances")
        self._validate_items(portfolio.holdings, Holding, "holdings")
        self._validate_items(portfolio.transactions, TradeTransaction, "transactions")
        self._validate_items(portfolio.active_orders, ActiveOrder, "active_orders")
        self._validate_items(portfolio.watchlist, WatchlistItem, "watchlist")
        self._validate_items(portfolio.goals, InvestmentGoal, "goals")
        self._validate_items(
            portfolio.recommendations,
            RecommendationRecord,
            "recommendations",
        )
        if portfolio.risk_profile is not None and not isinstance(
            portfolio.risk_profile, RiskProfile
        ):
            raise ValueError("risk_profile must be a RiskProfile instance")

    def _validate_items(
        self, items: Iterable[Any], item_type: type, field_name: str
    ) -> None:
        if not all(isinstance(item, item_type) for item in items):
            raise ValueError(f"{field_name} contains invalid items")

    def _decimal_to_text(self, value: Decimal | None) -> str | None:
        return str(value) if value is not None else None

    def _text_to_decimal(self, value: str | None) -> Decimal | None:
        return Decimal(value) if value is not None else None
