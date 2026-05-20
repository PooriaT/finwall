from finwall.storage_interface import PortfolioStore


class PostgresPortfolioStore(PortfolioStore):
    def __init__(self, database_url: str) -> None:
        self._database_url = database_url

    def _unsupported(self) -> None:
        raise NotImplementedError(
            "Postgres persistence is configured, but Postgres storage "
            "methods are not implemented yet."
        )

    def initialize(self) -> None:
        self._unsupported()

    def save_portfolio(self, portfolio):
        self._unsupported()

    def get_portfolio(self, name):
        self._unsupported()

    def delete_portfolio(self, name):
        self._unsupported()

    def add_trade_transaction(self, portfolio_name, transaction):
        self._unsupported()

    def list_trade_transactions(self, portfolio_name):
        self._unsupported()

    def record_cash_history(self, portfolio_name, cash_balance, recorded_on):
        self._unsupported()

    def list_cash_history(self, portfolio_name):
        self._unsupported()

    def save_report_run(
        self,
        portfolio_name,
        report,
        recommendation_report,
        risk_assessment,
        command_context,
    ):
        self._unsupported()

    def get_latest_report_run(self, portfolio_name):
        self._unsupported()

    def get_previous_report_run(self, portfolio_name, current_report_run_id):
        self._unsupported()

    def list_report_runs(self, portfolio_name):
        self._unsupported()

    def list_report_recommendation_statuses(self, report_run_id):
        self._unsupported()

    def list_report_risk_warnings(self, report_run_id):
        self._unsupported()

    def list_report_suggested_orders(self, report_run_id):
        self._unsupported()
