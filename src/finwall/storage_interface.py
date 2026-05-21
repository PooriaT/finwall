from typing import Protocol

from finwall.models import CashBalance, Portfolio, TradeTransaction
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


class PortfolioStore(Protocol):
    def initialize(self) -> None: ...
    def save_portfolio(self, portfolio: Portfolio) -> None: ...
    def get_portfolio(self, name: str) -> Portfolio | None: ...
    def delete_portfolio(self, name: str) -> None: ...
    def add_trade_transaction(
        self, portfolio_name: str, transaction: TradeTransaction
    ) -> None: ...
    def list_trade_transactions(
        self, portfolio_name: str
    ) -> tuple[TradeTransaction, ...]: ...
    def record_cash_history(
        self, portfolio_name: str, cash_balance: CashBalance, recorded_on
    ) -> None: ...
    def list_cash_history(
        self, portfolio_name: str
    ) -> tuple[tuple[CashBalance, object], ...]: ...
    def save_report_run(
        self,
        portfolio_name: str,
        report: DecisionSupportReport,
        recommendation_report: RecommendationReport,
        risk_assessment: RiskAssessment,
        command_context: str,
    ) -> int: ...
    def get_latest_report_run(self, portfolio_name: str) -> StoredReportRun | None: ...
    def get_previous_report_run(
        self, portfolio_name: str, current_report_run_id: int
    ) -> StoredReportRun | None: ...
    def list_report_runs(self, portfolio_name: str) -> tuple[StoredReportRun, ...]: ...
    def list_report_recommendation_statuses(
        self, report_run_id: int
    ) -> tuple[StoredRecommendationStatus, ...]: ...
    def list_report_risk_warnings(
        self, report_run_id: int
    ) -> tuple[StoredRiskWarning, ...]: ...
    def list_report_suggested_orders(
        self, report_run_id: int
    ) -> tuple[StoredSuggestedOrder, ...]: ...
    def get_scheduled_run(
        self,
        portfolio_name: str,
        run_date: str,
        run_context: str,
    ) -> StoredScheduledRun | None: ...
    def start_scheduled_run(
        self,
        portfolio_name: str,
        run_date: str,
        run_context: str,
    ) -> StoredScheduledRun: ...
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
    ) -> StoredScheduledRun: ...
    def list_scheduled_runs(
        self,
        portfolio_name: str,
        limit: int = 10,
    ) -> tuple[StoredScheduledRun, ...]: ...
