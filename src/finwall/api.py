import json
import logging
from dataclasses import asdict, replace
from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Any
from urllib.parse import parse_qs

from fastapi import Cookie, Depends, FastAPI, Header, HTTPException, Request
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from finwall.admin_dashboard import build_dashboard_view
from finwall.admin_ui import ADMIN_STATIC_DIR, render_admin_template
from finwall.chart_data import build_portfolio_chart_data
from finwall.config import Settings, settings
from finwall.models import ActiveOrder, OrderSide, OrderType, Portfolio, RiskLevel
from finwall.portfolio_audit import (
    PortfolioAuditEntityType,
    PortfolioAuditEvent,
    PortfolioAuditSource,
    PortfolioAuditStatus,
)
from finwall.portfolio_updates import (
    add_holding,
    add_or_update_order,
    add_watchlist_item,
    record_buy,
    record_sell,
    remove_order,
    remove_watchlist_item,
    save_portfolio_update,
    set_goal,
    set_risk_profile,
    set_timeline,
    upsert_cash,
)
from finwall.security import safe_error_message
from finwall.storage_factory import build_portfolio_store

DEFAULT_PORTFOLIO = "Primary"
ADMIN_COOKIE_NAME = "finwall_admin_token"


class CashRequest(BaseModel):
    currency: str
    amount: str


class HoldingRequest(BaseModel):
    ticker: str
    shares: str
    average_price: str
    sector: str | None = None


class TradeRequest(BaseModel):
    ticker: str
    shares: str
    price: str
    currency: str
    trade_date: date | None = None


class OrderRequest(BaseModel):
    ticker: str
    side: OrderSide
    order_type: OrderType
    shares: str
    limit_price: str | None = None
    stop_price: str | None = None


class WatchlistRequest(BaseModel):
    ticker: str
    note: str | None = None


class GoalRequest(BaseModel):
    name: str
    target_amount: str | None = None


class TimelineRequest(BaseModel):
    start_date: date
    target_date: date | None = None


class RiskProfileRequest(BaseModel):
    level: RiskLevel
    notes: str | None = None


class CashBalanceResponse(BaseModel):
    currency: str
    amount: float


class HoldingResponse(BaseModel):
    ticker: str
    share_count: float
    average_purchase_price: float
    sector: str | None = None


class TradeTransactionResponse(BaseModel):
    ticker: str
    side: str
    share_count: float
    price: float
    traded_on: date
    fees: float = 0


class ActiveOrderResponse(BaseModel):
    ticker: str
    side: OrderSide
    order_type: OrderType
    share_count: float
    limit_price: float | None = None
    stop_price: float | None = None


class WatchlistItemResponse(BaseModel):
    ticker: str
    note: str | None = None


class TimelineResponse(BaseModel):
    start_date: date
    target_date: date | None = None


class InvestmentGoalResponse(BaseModel):
    name: str
    target_amount: float | None = None
    timeline: TimelineResponse | None = None


class RiskProfileResponse(BaseModel):
    level: RiskLevel
    notes: str | None = None


class RecommendationRecordResponse(BaseModel):
    title: str
    summary: str
    created_on: date


class PortfolioResponse(BaseModel):
    name: str
    cash_balances: list[CashBalanceResponse] = Field(default_factory=list)
    holdings: list[HoldingResponse] = Field(default_factory=list)
    transactions: list[TradeTransactionResponse] = Field(default_factory=list)
    active_orders: list[ActiveOrderResponse] = Field(default_factory=list)
    watchlist: list[WatchlistItemResponse] = Field(default_factory=list)
    goals: list[InvestmentGoalResponse] = Field(default_factory=list)
    risk_profile: RiskProfileResponse | None = None
    recommendations: list[RecommendationRecordResponse] = Field(default_factory=list)


class ChartPointResponse(BaseModel):
    key: str
    label: str
    value: str | None
    percent: str | None = None
    status: str = "available"
    metadata: dict[str, Any] = Field(default_factory=dict)


class ChartSeriesResponse(BaseModel):
    key: str
    title: str
    points: list[ChartPointResponse]
    warnings: list[str] = Field(default_factory=list)


class PortfolioChartsResponse(BaseModel):
    allocation_by_holding: ChartSeriesResponse
    allocation_by_sector: ChartSeriesResponse
    cash_vs_invested: ChartSeriesResponse
    unrealized_gain_loss_by_holding: ChartSeriesResponse
    risk_warnings_by_severity: ChartSeriesResponse
    report_history_summary: ChartSeriesResponse


class PortfolioAnalysisChartsResponse(BaseModel):
    portfolio_name: str
    valuation_status: str
    price_completeness_status: str
    data_warnings: list[str]
    charts: PortfolioChartsResponse


class PortfolioAuditResponse(BaseModel):
    events: list[PortfolioAuditEvent]


def _to_decimal(value: str, field_name: str) -> Decimal:
    try:
        return Decimal(value)
    except (InvalidOperation, ValueError) as exc:
        raise HTTPException(422, detail=f"invalid decimal for {field_name}") from exc


async def _read_form(request: Request) -> dict[str, str]:
    body = (await request.body()).decode()
    parsed = parse_qs(body, keep_blank_values=True)
    return {key: values[-1] if values else "" for key, values in parsed.items()}


def create_app(app_settings: Settings = settings) -> FastAPI:
    app = FastAPI(title="Finwall API")
    app.state.settings = app_settings
    app.state.store = build_portfolio_store(
        backend=app_settings.storage_backend,
        database_path=app_settings.database_path,
        database_url=app_settings.database_url,
    )
    app.state.store.initialize()
    app.mount(
        "/admin/static",
        StaticFiles(directory=str(ADMIN_STATIC_DIR)),
        name="admin_static",
    )

    def _token_is_valid(raw_token: str | None) -> bool:
        token = app.state.settings.api_token
        return bool(token) and raw_token == token

    def _bearer_token_is_valid(authorization: str | None) -> bool:
        if authorization is None or not authorization.startswith("Bearer "):
            return False
        return _token_is_valid(authorization.removeprefix("Bearer ").strip())

    def auth(request: Request, authorization: str | None = Header(default=None)) -> str:
        token = request.app.state.settings.api_token
        if not token:
            raise HTTPException(401, detail="authentication is not configured")
        if not _bearer_token_is_valid(authorization):
            raise HTTPException(401, detail="invalid authentication credentials")
        return "api-admin"

    def read_auth(
        request: Request,
        authorization: str | None = Header(default=None),
        admin_token: str | None = Cookie(default=None, alias=ADMIN_COOKIE_NAME),
    ) -> str:
        token = request.app.state.settings.api_token
        if not token:
            raise HTTPException(401, detail="authentication is not configured")
        if _bearer_token_is_valid(authorization):
            return "api-admin"
        if _token_is_valid(admin_token):
            return "web-admin"
        raise HTTPException(401, detail="invalid authentication credentials")

    def admin_auth(request: Request) -> str:
        token = app.state.settings.api_token
        if not token:
            raise HTTPException(401, detail="authentication is not configured")
        if not _token_is_valid(request.cookies.get(ADMIN_COOKIE_NAME)):
            raise HTTPException(401, detail="invalid authentication credentials")
        return "web-admin"

    def _redirect(path: str, message: str | None = None) -> RedirectResponse:
        target = path if not message else f"{path}?msg={message}"
        return RedirectResponse(target, status_code=303)

    def get_portfolio() -> Portfolio:
        store = app.state.store
        portfolio = store.get_portfolio(DEFAULT_PORTFOLIO)
        if portfolio is None:
            portfolio = Portfolio(name=DEFAULT_PORTFOLIO)
            store.save_portfolio(portfolio)
        return portfolio

    logger = logging.getLogger(__name__)

    def _json_snapshot(value: object | None) -> str | None:
        if value is None:
            return None
        return json.dumps(value, separators=(",", ":"), sort_keys=True, default=str)

    def record_update_audit(
        portfolio_name: str,
        *,
        actor: str,
        source: str,
        action: str,
        entity_type: str,
        entity_id: str | None,
        before: object | None,
        after: object | None,
        status: str,
        summary: str,
        safe_error_message: str | None = None,
    ) -> None:
        try:
            app.state.store.record_portfolio_audit_event(
                portfolio_name,
                actor=actor,
                source=source,
                action=action,
                entity_type=entity_type,
                entity_id=entity_id,
                status=status,
                summary=summary,
                before_json=_json_snapshot(before),
                after_json=_json_snapshot(after),
                safe_error_message=safe_error_message,
            )
        except Exception:
            logger.warning("failed to record portfolio audit event")

    def _one(items, attr: str, value: str):
        return next(
            (asdict(item) for item in items if getattr(item, attr) == value), None
        )

    def _goal_snapshot(portfolio: Portfolio):
        return asdict(portfolio.goals[0]) if portfolio.goals else None

    def _timeline_snapshot(portfolio: Portfolio):
        return (
            asdict(portfolio.goals[0].timeline)
            if portfolio.goals and portfolio.goals[0].timeline
            else None
        )

    def _risk_snapshot(portfolio: Portfolio):
        return asdict(portfolio.risk_profile) if portfolio.risk_profile else None

    def _trade_snapshot(
        before: Portfolio, after: Portfolio, ticker: str, currency: str
    ):
        return {
            "cash": _one(after.cash_balances, "currency", currency),
            "holding": _one(after.holdings, "ticker", ticker),
            "trade": asdict(after.transactions[-1])
            if len(after.transactions) > len(before.transactions)
            else None,
        }

    def _audit_failure(
        actor: str,
        source: str,
        action: str,
        entity_type: str,
        entity_id: str | None,
        summary: str,
        exc: Exception,
        before: object | None = None,
    ) -> None:
        record_update_audit(
            DEFAULT_PORTFOLIO,
            actor=actor,
            source=source,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            before=before,
            after=None,
            status=PortfolioAuditStatus.FAILED,
            summary=summary,
            safe_error_message=safe_error_message(exc),
        )

    def persist(updated: Portfolio, existing: Portfolio) -> dict:
        save_portfolio_update(
            app.state.store,
            DEFAULT_PORTFOLIO,
            updated,
            existing.transactions,
        )
        return asdict(updated)

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/admin/login")
    def admin_login_get(request: Request):
        return render_admin_template(
            request, "login.html", title="Admin Login", active_nav="login"
        )

    @app.post("/admin/login")
    async def admin_login_post(request: Request):
        form = await _read_form(request)
        token = str(form.get("token", "")).strip()
        if not _token_is_valid(token):
            return render_admin_template(
                request,
                "login.html",
                title="Admin Login",
                active_nav="login",
                flash="Invalid token",
                status_code=401,
            )
        response = _redirect("/admin", "Login successful")
        response.set_cookie(
            ADMIN_COOKIE_NAME,
            token,
            httponly=True,
            samesite="lax",
            secure=app.state.settings.app_env.lower() == "production",
        )
        return response

    @app.post("/admin/logout")
    def admin_logout():
        response = _redirect("/admin/login", "Logged out")
        response.delete_cookie(ADMIN_COOKIE_NAME)
        return response

    @app.get("/admin")
    def admin_home(request: Request, _: str = Depends(admin_auth)):
        portfolio = get_portfolio()
        dashboard = build_dashboard_view(portfolio, app.state.store, app.state.settings)
        return render_admin_template(
            request,
            "home.html",
            title="Dashboard",
            active_nav="home",
            dashboard=dashboard,
        )

    @app.get("/api/v1/portfolio", response_model=PortfolioResponse)
    def read_portfolio(_: str = Depends(read_auth)):
        return asdict(get_portfolio())

    def _analysis_charts(report_history_limit: int = 10):
        bounded_limit = max(0, min(report_history_limit, 50))
        return build_portfolio_chart_data(
            get_portfolio(),
            app.state.store,
            app.state.settings,
            report_history_limit=bounded_limit,
        )

    @app.get(
        "/api/v1/portfolio/analysis/charts",
        response_model=PortfolioAnalysisChartsResponse,
    )
    def portfolio_analysis_charts(
        report_history_limit: int = 10, _: str = Depends(read_auth)
    ):
        return _analysis_charts(report_history_limit).as_dict()

    @app.get(
        "/api/v1/portfolio/analysis/allocation/holdings",
        response_model=ChartSeriesResponse,
    )
    def portfolio_allocation_holdings(
        report_history_limit: int = 10, _: str = Depends(read_auth)
    ):
        return _analysis_charts(report_history_limit).allocation_by_holding.as_dict()

    @app.get(
        "/api/v1/portfolio/analysis/allocation/sectors",
        response_model=ChartSeriesResponse,
    )
    def portfolio_allocation_sectors(
        report_history_limit: int = 10, _: str = Depends(read_auth)
    ):
        return _analysis_charts(report_history_limit).allocation_by_sector.as_dict()

    @app.get(
        "/api/v1/portfolio/analysis/cash-vs-invested",
        response_model=ChartSeriesResponse,
    )
    def portfolio_cash_vs_invested(
        report_history_limit: int = 10, _: str = Depends(read_auth)
    ):
        return _analysis_charts(report_history_limit).cash_vs_invested.as_dict()

    @app.get(
        "/api/v1/portfolio/analysis/unrealized-gain-loss",
        response_model=ChartSeriesResponse,
    )
    def portfolio_unrealized_gain_loss(
        report_history_limit: int = 10, _: str = Depends(read_auth)
    ):
        return _analysis_charts(
            report_history_limit
        ).unrealized_gain_loss_by_holding.as_dict()

    @app.get(
        "/api/v1/portfolio/analysis/risk-warnings",
        response_model=ChartSeriesResponse,
    )
    def portfolio_risk_warnings(
        report_history_limit: int = 10, _: str = Depends(read_auth)
    ):
        return _analysis_charts(
            report_history_limit
        ).risk_warnings_by_severity.as_dict()

    @app.get(
        "/api/v1/portfolio/analysis/report-history",
        response_model=ChartSeriesResponse,
    )
    def portfolio_report_history(
        report_history_limit: int = 10, _: str = Depends(read_auth)
    ):
        return _analysis_charts(report_history_limit).report_history_summary.as_dict()

    @app.get("/api/v1/portfolio/audit", response_model=PortfolioAuditResponse)
    def read_portfolio_audit(limit: int = 50, _: str = Depends(read_auth)):
        try:
            events = app.state.store.list_portfolio_audit_events(
                DEFAULT_PORTFOLIO, limit
            )
        except ValueError:
            events = ()
        return {"events": [event.as_dict() for event in events]}

    @app.post("/api/v1/portfolio/cash/add")
    def cash_add(payload: CashRequest, actor: str = Depends(auth)):
        portfolio = get_portfolio()
        before = next(
            (
                asdict(c)
                for c in portfolio.cash_balances
                if c.currency == payload.currency
            ),
            None,
        )
        updated = upsert_cash(
            portfolio, payload.currency, _to_decimal(payload.amount, "amount")
        )
        after = next(
            (
                asdict(c)
                for c in updated.cash_balances
                if c.currency == payload.currency
            ),
            None,
        )
        result = persist(updated, portfolio)
        record_update_audit(
            DEFAULT_PORTFOLIO,
            actor=actor,
            source=PortfolioAuditSource.API,
            action="cash_add",
            entity_type=PortfolioAuditEntityType.CASH,
            entity_id=payload.currency,
            before=before,
            after=after,
            status=PortfolioAuditStatus.SUCCEEDED,
            summary=f"Added cash for {payload.currency}",
        )
        return result

    @app.post("/api/v1/portfolio/cash/withdraw")
    def cash_withdraw(payload: CashRequest, actor: str = Depends(auth)):
        portfolio = get_portfolio()
        before = _one(portfolio.cash_balances, "currency", payload.currency)
        try:
            amount = _to_decimal(payload.amount, "amount")
        except HTTPException as exc:
            _audit_failure(
                actor,
                PortfolioAuditSource.API,
                "cash_withdraw",
                PortfolioAuditEntityType.CASH,
                payload.currency,
                f"Failed cash withdrawal for {payload.currency}",
                exc,
                before,
            )
            raise
        try:
            updated = upsert_cash(portfolio, payload.currency, -amount)
        except (HTTPException, ValueError) as exc:
            _audit_failure(
                actor,
                PortfolioAuditSource.API,
                "cash_withdraw",
                PortfolioAuditEntityType.CASH,
                payload.currency,
                f"Failed cash withdrawal for {payload.currency}",
                exc,
                before,
            )
            raise HTTPException(400, detail=safe_error_message(exc)) from exc
        result = persist(updated, portfolio)
        record_update_audit(
            DEFAULT_PORTFOLIO,
            actor=actor,
            source=PortfolioAuditSource.API,
            action="cash_withdraw",
            entity_type=PortfolioAuditEntityType.CASH,
            entity_id=payload.currency,
            before=before,
            after=_one(updated.cash_balances, "currency", payload.currency),
            status=PortfolioAuditStatus.SUCCEEDED,
            summary=f"Withdrew cash for {payload.currency}",
        )
        return result

    @app.post("/api/v1/portfolio/holdings")
    def holdings_upsert(payload: HoldingRequest, actor: str = Depends(auth)):
        portfolio = get_portfolio()
        before = next(
            (asdict(h) for h in portfolio.holdings if h.ticker == payload.ticker), None
        )
        updated = add_holding(
            portfolio,
            payload.ticker,
            _to_decimal(payload.shares, "shares"),
            _to_decimal(payload.average_price, "average_price"),
            payload.sector,
        )
        after = next(
            (asdict(h) for h in updated.holdings if h.ticker == payload.ticker), None
        )
        result = persist(updated, portfolio)
        record_update_audit(
            DEFAULT_PORTFOLIO,
            actor=actor,
            source=PortfolioAuditSource.API,
            action="holding_upsert",
            entity_type=PortfolioAuditEntityType.HOLDING,
            entity_id=payload.ticker,
            before=before,
            after=after,
            status=PortfolioAuditStatus.SUCCEEDED,
            summary=f"Saved holding {payload.ticker}",
        )
        return result

    @app.delete("/api/v1/portfolio/holdings/{ticker}")
    def holdings_remove(ticker: str, actor: str = Depends(auth)):
        portfolio = get_portfolio()
        before = _one(portfolio.holdings, "ticker", ticker)
        filtered = tuple(item for item in portfolio.holdings if item.ticker != ticker)
        result = persist(replace(portfolio, holdings=filtered), portfolio)
        record_update_audit(
            DEFAULT_PORTFOLIO,
            actor=actor,
            source=PortfolioAuditSource.API,
            action="holding_delete",
            entity_type=PortfolioAuditEntityType.HOLDING,
            entity_id=ticker,
            before=before,
            after=None,
            status=PortfolioAuditStatus.SUCCEEDED,
            summary=f"Deleted holding {ticker}",
        )
        return result

    @app.post("/api/v1/portfolio/trades/buy")
    def trade_buy(payload: TradeRequest, actor: str = Depends(auth)):
        portfolio = get_portfolio()
        before = _trade_snapshot(portfolio, portfolio, payload.ticker, payload.currency)
        try:
            updated = record_buy(
                portfolio,
                payload.ticker,
                _to_decimal(payload.shares, "shares"),
                _to_decimal(payload.price, "price"),
                payload.currency,
                payload.trade_date or date.today(),
            )
        except ValueError as exc:
            _audit_failure(
                actor,
                PortfolioAuditSource.API,
                "trade_buy",
                PortfolioAuditEntityType.TRADE,
                payload.ticker,
                f"Failed buy trade for {payload.ticker}",
                exc,
                before,
            )
            raise HTTPException(400, detail=safe_error_message(exc)) from exc
        result = persist(updated, portfolio)
        record_update_audit(
            DEFAULT_PORTFOLIO,
            actor=actor,
            source=PortfolioAuditSource.API,
            action="trade_buy",
            entity_type=PortfolioAuditEntityType.TRADE,
            entity_id=payload.ticker,
            before=before,
            after=_trade_snapshot(portfolio, updated, payload.ticker, payload.currency),
            status=PortfolioAuditStatus.SUCCEEDED,
            summary=f"Recorded buy trade for {payload.ticker}",
        )
        return result

    @app.post("/api/v1/portfolio/trades/sell")
    def trade_sell(payload: TradeRequest, actor: str = Depends(auth)):
        portfolio = get_portfolio()
        before = _trade_snapshot(portfolio, portfolio, payload.ticker, payload.currency)
        try:
            updated = record_sell(
                portfolio,
                payload.ticker,
                _to_decimal(payload.shares, "shares"),
                _to_decimal(payload.price, "price"),
                payload.currency,
                payload.trade_date or date.today(),
            )
        except ValueError as exc:
            _audit_failure(
                actor,
                PortfolioAuditSource.API,
                "trade_sell",
                PortfolioAuditEntityType.TRADE,
                payload.ticker,
                f"Failed sell trade for {payload.ticker}",
                exc,
                before,
            )
            raise HTTPException(400, detail=safe_error_message(exc)) from exc
        result = persist(updated, portfolio)
        record_update_audit(
            DEFAULT_PORTFOLIO,
            actor=actor,
            source=PortfolioAuditSource.API,
            action="trade_sell",
            entity_type=PortfolioAuditEntityType.TRADE,
            entity_id=payload.ticker,
            before=before,
            after=_trade_snapshot(portfolio, updated, payload.ticker, payload.currency),
            status=PortfolioAuditStatus.SUCCEEDED,
            summary=f"Recorded sell trade for {payload.ticker}",
        )
        return result

    @app.post("/api/v1/portfolio/orders")
    def orders_upsert(payload: OrderRequest, actor: str = Depends(auth)):
        portfolio = get_portfolio()
        before = _one(portfolio.active_orders, "ticker", payload.ticker)
        try:
            order = ActiveOrder(
                payload.ticker,
                payload.side,
                payload.order_type,
                _to_decimal(payload.shares, "shares"),
                _to_decimal(payload.limit_price, "limit_price")
                if payload.limit_price
                else None,
                _to_decimal(payload.stop_price, "stop_price")
                if payload.stop_price
                else None,
            )
        except (HTTPException, ValueError) as exc:
            _audit_failure(
                actor,
                PortfolioAuditSource.API,
                "order_upsert",
                PortfolioAuditEntityType.ACTIVE_ORDER,
                payload.ticker,
                f"Failed order save for {payload.ticker}",
                exc,
                before,
            )
            raise HTTPException(422, detail=safe_error_message(exc)) from exc
        updated = add_or_update_order(portfolio, order)
        result = persist(updated, portfolio)
        record_update_audit(
            DEFAULT_PORTFOLIO,
            actor=actor,
            source=PortfolioAuditSource.API,
            action="order_upsert",
            entity_type=PortfolioAuditEntityType.ACTIVE_ORDER,
            entity_id=payload.ticker,
            before=before,
            after=_one(updated.active_orders, "ticker", payload.ticker),
            status=PortfolioAuditStatus.SUCCEEDED,
            summary=f"Saved order {payload.ticker}",
        )
        return result

    @app.delete("/api/v1/portfolio/orders/{ticker}")
    def orders_remove(ticker: str, actor: str = Depends(auth)):
        portfolio = get_portfolio()
        before = _one(portfolio.active_orders, "ticker", ticker)
        result = persist(remove_order(portfolio, ticker), portfolio)
        record_update_audit(
            DEFAULT_PORTFOLIO,
            actor=actor,
            source=PortfolioAuditSource.API,
            action="order_delete",
            entity_type=PortfolioAuditEntityType.ACTIVE_ORDER,
            entity_id=ticker,
            before=before,
            after=None,
            status=PortfolioAuditStatus.SUCCEEDED,
            summary=f"Deleted order {ticker}",
        )
        return result

    @app.post("/api/v1/portfolio/watchlist")
    def watchlist_upsert(payload: WatchlistRequest, actor: str = Depends(auth)):
        portfolio = get_portfolio()
        before = _one(portfolio.watchlist, "ticker", payload.ticker)
        updated = add_watchlist_item(portfolio, payload.ticker, payload.note)
        result = persist(updated, portfolio)
        record_update_audit(
            DEFAULT_PORTFOLIO,
            actor=actor,
            source=PortfolioAuditSource.API,
            action="watchlist_upsert",
            entity_type=PortfolioAuditEntityType.WATCHLIST,
            entity_id=payload.ticker,
            before=before,
            after=_one(updated.watchlist, "ticker", payload.ticker),
            status=PortfolioAuditStatus.SUCCEEDED,
            summary=f"Saved watchlist item {payload.ticker}",
        )
        return result

    @app.delete("/api/v1/portfolio/watchlist/{ticker}")
    def watchlist_remove(ticker: str, actor: str = Depends(auth)):
        portfolio = get_portfolio()
        before = _one(portfolio.watchlist, "ticker", ticker)
        result = persist(remove_watchlist_item(portfolio, ticker), portfolio)
        record_update_audit(
            DEFAULT_PORTFOLIO,
            actor=actor,
            source=PortfolioAuditSource.API,
            action="watchlist_delete",
            entity_type=PortfolioAuditEntityType.WATCHLIST,
            entity_id=ticker,
            before=before,
            after=None,
            status=PortfolioAuditStatus.SUCCEEDED,
            summary=f"Deleted watchlist item {ticker}",
        )
        return result

    @app.put("/api/v1/portfolio/goal")
    def goal_set(payload: GoalRequest, actor: str = Depends(auth)):
        portfolio = get_portfolio()
        before = _goal_snapshot(portfolio)
        target = (
            _to_decimal(payload.target_amount, "target_amount")
            if payload.target_amount
            else None
        )
        updated = set_goal(portfolio, payload.name, target)
        result = persist(updated, portfolio)
        record_update_audit(
            DEFAULT_PORTFOLIO,
            actor=actor,
            source=PortfolioAuditSource.API,
            action="goal_set",
            entity_type=PortfolioAuditEntityType.GOAL,
            entity_id=payload.name,
            before=before,
            after=_goal_snapshot(updated),
            status=PortfolioAuditStatus.SUCCEEDED,
            summary=f"Set goal {payload.name}",
        )
        return result

    @app.put("/api/v1/portfolio/timeline")
    def timeline_set(payload: TimelineRequest, actor: str = Depends(auth)):
        portfolio = get_portfolio()
        before = _timeline_snapshot(portfolio)
        try:
            updated = set_timeline(portfolio, payload.start_date, payload.target_date)
        except ValueError as exc:
            _audit_failure(
                actor,
                PortfolioAuditSource.API,
                "timeline_set",
                PortfolioAuditEntityType.TIMELINE,
                None,
                "Failed timeline update",
                exc,
                before,
            )
            raise HTTPException(422, detail=safe_error_message(exc)) from exc
        result = persist(updated, portfolio)
        record_update_audit(
            DEFAULT_PORTFOLIO,
            actor=actor,
            source=PortfolioAuditSource.API,
            action="timeline_set",
            entity_type=PortfolioAuditEntityType.TIMELINE,
            entity_id=None,
            before=before,
            after=_timeline_snapshot(updated),
            status=PortfolioAuditStatus.SUCCEEDED,
            summary="Set timeline",
        )
        return result

    @app.put("/api/v1/portfolio/risk-profile")
    def risk_set(payload: RiskProfileRequest, actor: str = Depends(auth)):
        portfolio = get_portfolio()
        before = _risk_snapshot(portfolio)
        updated = set_risk_profile(portfolio, payload.level, payload.notes)
        result = persist(updated, portfolio)
        record_update_audit(
            DEFAULT_PORTFOLIO,
            actor=actor,
            source=PortfolioAuditSource.API,
            action="risk_profile_set",
            entity_type=PortfolioAuditEntityType.RISK_PROFILE,
            entity_id=str(payload.level),
            before=before,
            after=_risk_snapshot(updated),
            status=PortfolioAuditStatus.SUCCEEDED,
            summary=f"Set risk profile {payload.level}",
        )
        return result

    @app.get("/admin/portfolio")
    def admin_portfolio(request: Request, _: str = Depends(admin_auth)):
        return render_admin_template(
            request,
            "portfolio.html",
            title="Portfolio",
            active_nav="portfolio",
            portfolio=asdict(get_portfolio()),
        )

    @app.get("/admin/audit")
    def admin_audit(request: Request, _: str = Depends(admin_auth)):
        try:
            events = app.state.store.list_portfolio_audit_events(DEFAULT_PORTFOLIO, 100)
        except ValueError:
            events = ()
        return render_admin_template(
            request, "audit.html", title="Audit", active_nav="audit", events=events
        )

    @app.get("/admin/cash")
    def admin_cash(request: Request, _: str = Depends(admin_auth)):
        return render_admin_template(
            request, "cash.html", title="Cash", active_nav="cash"
        )

    @app.post("/admin/cash/add")
    async def admin_cash_add(request: Request, actor: str = Depends(admin_auth)):
        form = await _read_form(request)
        try:
            portfolio = get_portfolio()
            before = _one(portfolio.cash_balances, "currency", str(form["currency"]))
            updated = upsert_cash(
                portfolio,
                str(form["currency"]),
                _to_decimal(str(form["amount"]), "amount"),
            )
            persist(updated, portfolio)
            record_update_audit(
                DEFAULT_PORTFOLIO,
                actor=actor,
                source=PortfolioAuditSource.WEB,
                action="cash_add",
                entity_type=PortfolioAuditEntityType.CASH,
                entity_id=str(form["currency"]),
                before=before,
                after=_one(updated.cash_balances, "currency", str(form["currency"])),
                status=PortfolioAuditStatus.SUCCEEDED,
                summary=f"Added cash for {str(form['currency'])}",
            )
            return _redirect("/admin/cash", "Cash updated")
        except Exception as exc:
            return render_admin_template(
                request,
                "cash.html",
                title="Cash",
                active_nav="cash",
                flash=safe_error_message(exc),
                status_code=422,
            )

    @app.post("/admin/cash/withdraw")
    async def admin_cash_withdraw(request: Request, actor: str = Depends(admin_auth)):
        form = await _read_form(request)
        try:
            portfolio = get_portfolio()
            before = _one(portfolio.cash_balances, "currency", str(form["currency"]))
            updated = upsert_cash(
                portfolio,
                str(form["currency"]),
                -_to_decimal(str(form["amount"]), "amount"),
            )
            persist(updated, portfolio)
            record_update_audit(
                DEFAULT_PORTFOLIO,
                actor=actor,
                source=PortfolioAuditSource.WEB,
                action="cash_withdraw",
                entity_type=PortfolioAuditEntityType.CASH,
                entity_id=str(form["currency"]),
                before=before,
                after=_one(updated.cash_balances, "currency", str(form["currency"])),
                status=PortfolioAuditStatus.SUCCEEDED,
                summary=f"Withdrew cash for {str(form['currency'])}",
            )
            return _redirect("/admin/cash", "Cash withdrawn")
        except Exception as exc:
            if "currency" in form:
                _audit_failure(
                    actor,
                    PortfolioAuditSource.WEB,
                    "cash_withdraw",
                    PortfolioAuditEntityType.CASH,
                    str(form["currency"]),
                    f"Failed cash withdrawal for {str(form['currency'])}",
                    exc,
                )
            return render_admin_template(
                request,
                "cash.html",
                title="Cash",
                active_nav="cash",
                flash=safe_error_message(exc),
                status_code=422,
            )

    @app.get("/admin/holdings")
    def admin_holdings(request: Request, _: str = Depends(admin_auth)):
        return render_admin_template(
            request, "holdings.html", title="Holdings", active_nav="holdings"
        )

    @app.post("/admin/holdings")
    async def admin_holdings_upsert(request: Request, actor: str = Depends(admin_auth)):
        form = await _read_form(request)
        try:
            p = get_portfolio()
            before = _one(p.holdings, "ticker", str(form["ticker"]))
            updated = add_holding(
                p,
                str(form["ticker"]),
                _to_decimal(str(form["shares"]), "shares"),
                _to_decimal(str(form["average_price"]), "average_price"),
                str(form.get("sector") or "") or None,
            )
            persist(updated, p)
            record_update_audit(
                DEFAULT_PORTFOLIO,
                actor=actor,
                source=PortfolioAuditSource.WEB,
                action="holding_upsert",
                entity_type=PortfolioAuditEntityType.HOLDING,
                entity_id=str(form["ticker"]),
                before=before,
                after=_one(updated.holdings, "ticker", str(form["ticker"])),
                status=PortfolioAuditStatus.SUCCEEDED,
                summary=f"Saved holding {str(form['ticker'])}",
            )
            return _redirect("/admin/holdings", "Holding saved")
        except Exception as exc:
            return render_admin_template(
                request,
                "holdings.html",
                title="Holdings",
                active_nav="holdings",
                flash=safe_error_message(exc),
                status_code=422,
            )

    @app.post("/admin/holdings/delete")
    async def admin_holdings_delete(request: Request, actor: str = Depends(admin_auth)):
        form = await _read_form(request)
        p = get_portfolio()
        before = _one(p.holdings, "ticker", str(form["ticker"]))
        updated = replace(
            p,
            holdings=tuple(
                item for item in p.holdings if item.ticker != str(form["ticker"])
            ),
        )
        persist(updated, p)
        record_update_audit(
            DEFAULT_PORTFOLIO,
            actor=actor,
            source=PortfolioAuditSource.WEB,
            action="holding_delete",
            entity_type=PortfolioAuditEntityType.HOLDING,
            entity_id=str(form["ticker"]),
            before=before,
            after=None,
            status=PortfolioAuditStatus.SUCCEEDED,
            summary=f"Deleted holding {str(form['ticker'])}",
        )
        return _redirect("/admin/holdings", "Holding deleted")

    @app.get("/admin/trades")
    def admin_trades(request: Request, _: str = Depends(admin_auth)):
        return render_admin_template(
            request, "trades.html", title="Trades", active_nav="trades"
        )

    async def _trade(request: Request, side: str, actor: str):
        form = await _read_form(request)
        p = get_portfolio()
        before = _trade_snapshot(p, p, str(form["ticker"]), str(form["currency"]))
        try:
            trade_date = (
                date.fromisoformat(str(form["trade_date"]))
                if form.get("trade_date")
                else date.today()
            )
            fn = record_buy if side == "buy" else record_sell
            updated = fn(
                p,
                str(form["ticker"]),
                _to_decimal(str(form["shares"]), "shares"),
                _to_decimal(str(form["price"]), "price"),
                str(form["currency"]),
                trade_date,
            )
        except Exception as exc:
            _audit_failure(
                actor,
                PortfolioAuditSource.WEB,
                f"trade_{side}",
                PortfolioAuditEntityType.TRADE,
                str(form["ticker"]),
                f"Failed {side} trade for {str(form['ticker'])}",
                exc,
                before,
            )
            raise
        persist(updated, p)
        record_update_audit(
            DEFAULT_PORTFOLIO,
            actor=actor,
            source=PortfolioAuditSource.WEB,
            action=f"trade_{side}",
            entity_type=PortfolioAuditEntityType.TRADE,
            entity_id=str(form["ticker"]),
            before=before,
            after=_trade_snapshot(
                p, updated, str(form["ticker"]), str(form["currency"])
            ),
            status=PortfolioAuditStatus.SUCCEEDED,
            summary=f"Recorded {side} trade for {str(form['ticker'])}",
        )
        return _redirect("/admin/trades", f"Trade {side} recorded")

    @app.post("/admin/trades/buy")
    async def admin_trade_buy(request: Request, actor: str = Depends(admin_auth)):
        try:
            return await _trade(request, "buy", actor)
        except Exception as exc:
            return render_admin_template(
                request,
                "trades.html",
                title="Trades",
                active_nav="trades",
                flash=safe_error_message(exc),
                status_code=422,
            )

    @app.post("/admin/trades/sell")
    async def admin_trade_sell(request: Request, actor: str = Depends(admin_auth)):
        try:
            return await _trade(request, "sell", actor)
        except Exception as exc:
            return render_admin_template(
                request,
                "trades.html",
                title="Trades",
                active_nav="trades",
                flash=safe_error_message(exc),
                status_code=422,
            )

    @app.get("/admin/orders")
    def admin_orders(request: Request, _: str = Depends(admin_auth)):
        return render_admin_template(
            request, "orders.html", title="Orders", active_nav="orders"
        )

    @app.post("/admin/orders")
    async def admin_orders_upsert(request: Request, actor: str = Depends(admin_auth)):
        form = await _read_form(request)
        try:
            p = get_portfolio()
            before = _one(p.active_orders, "ticker", str(form["ticker"]))
            order = ActiveOrder(
                str(form["ticker"]),
                OrderSide(str(form["side"])),
                OrderType(str(form["order_type"])),
                _to_decimal(str(form["shares"]), "shares"),
                _to_decimal(str(form["limit_price"]), "limit_price")
                if form.get("limit_price")
                else None,
                _to_decimal(str(form["stop_price"]), "stop_price")
                if form.get("stop_price")
                else None,
            )
            updated = add_or_update_order(p, order)
            persist(updated, p)
            record_update_audit(
                DEFAULT_PORTFOLIO,
                actor=actor,
                source=PortfolioAuditSource.WEB,
                action="order_upsert",
                entity_type=PortfolioAuditEntityType.ACTIVE_ORDER,
                entity_id=str(form["ticker"]),
                before=before,
                after=_one(updated.active_orders, "ticker", str(form["ticker"])),
                status=PortfolioAuditStatus.SUCCEEDED,
                summary=f"Saved order {str(form['ticker'])}",
            )
            return _redirect("/admin/orders", "Order saved")
        except Exception as exc:
            if "ticker" in form:
                _audit_failure(
                    actor,
                    PortfolioAuditSource.WEB,
                    "order_upsert",
                    PortfolioAuditEntityType.ACTIVE_ORDER,
                    str(form["ticker"]),
                    f"Failed order save for {str(form['ticker'])}",
                    exc,
                )
            return render_admin_template(
                request,
                "orders.html",
                title="Orders",
                active_nav="orders",
                flash=safe_error_message(exc),
                status_code=422,
            )

    @app.post("/admin/orders/delete")
    async def admin_orders_delete(request: Request, actor: str = Depends(admin_auth)):
        form = await _read_form(request)
        p = get_portfolio()
        before = _one(p.active_orders, "ticker", str(form["ticker"]))
        persist(remove_order(p, str(form["ticker"])), p)
        record_update_audit(
            DEFAULT_PORTFOLIO,
            actor=actor,
            source=PortfolioAuditSource.WEB,
            action="order_delete",
            entity_type=PortfolioAuditEntityType.ACTIVE_ORDER,
            entity_id=str(form["ticker"]),
            before=before,
            after=None,
            status=PortfolioAuditStatus.SUCCEEDED,
            summary=f"Deleted order {str(form['ticker'])}",
        )
        return _redirect("/admin/orders", "Order deleted")

    @app.get("/admin/watchlist")
    def admin_watchlist(request: Request, _: str = Depends(admin_auth)):
        return render_admin_template(
            request, "watchlist.html", title="Watchlist", active_nav="watchlist"
        )

    @app.post("/admin/watchlist")
    async def admin_watchlist_upsert(
        request: Request, actor: str = Depends(admin_auth)
    ):
        form = await _read_form(request)
        p = get_portfolio()
        before = _one(p.watchlist, "ticker", str(form["ticker"]))
        updated = add_watchlist_item(
            p, str(form["ticker"]), str(form.get("note") or "") or None
        )
        persist(updated, p)
        record_update_audit(
            DEFAULT_PORTFOLIO,
            actor=actor,
            source=PortfolioAuditSource.WEB,
            action="watchlist_upsert",
            entity_type=PortfolioAuditEntityType.WATCHLIST,
            entity_id=str(form["ticker"]),
            before=before,
            after=_one(updated.watchlist, "ticker", str(form["ticker"])),
            status=PortfolioAuditStatus.SUCCEEDED,
            summary=f"Saved watchlist item {str(form['ticker'])}",
        )
        return _redirect("/admin/watchlist", "Watchlist updated")

    @app.post("/admin/watchlist/delete")
    async def admin_watchlist_delete(
        request: Request, actor: str = Depends(admin_auth)
    ):
        form = await _read_form(request)
        p = get_portfolio()
        before = _one(p.watchlist, "ticker", str(form["ticker"]))
        persist(remove_watchlist_item(p, str(form["ticker"])), p)
        record_update_audit(
            DEFAULT_PORTFOLIO,
            actor=actor,
            source=PortfolioAuditSource.WEB,
            action="watchlist_delete",
            entity_type=PortfolioAuditEntityType.WATCHLIST,
            entity_id=str(form["ticker"]),
            before=before,
            after=None,
            status=PortfolioAuditStatus.SUCCEEDED,
            summary=f"Deleted watchlist item {str(form['ticker'])}",
        )
        return _redirect("/admin/watchlist", "Watchlist item removed")

    @app.get("/admin/settings")
    def admin_settings(request: Request, _: str = Depends(admin_auth)):
        return render_admin_template(
            request, "settings.html", title="Settings", active_nav="settings"
        )

    @app.post("/admin/goal")
    async def admin_goal(request: Request, actor: str = Depends(admin_auth)):
        form = await _read_form(request)
        p = get_portfolio()
        before = _goal_snapshot(p)
        updated = set_goal(
            p,
            str(form["name"]),
            _to_decimal(str(form["target_amount"]), "target_amount")
            if form.get("target_amount")
            else None,
        )
        persist(updated, p)
        record_update_audit(
            DEFAULT_PORTFOLIO,
            actor=actor,
            source=PortfolioAuditSource.WEB,
            action="goal_set",
            entity_type=PortfolioAuditEntityType.GOAL,
            entity_id=str(form["name"]),
            before=before,
            after=_goal_snapshot(updated),
            status=PortfolioAuditStatus.SUCCEEDED,
            summary=f"Set goal {str(form['name'])}",
        )
        return _redirect("/admin/settings", "Goal set")

    @app.post("/admin/timeline")
    async def admin_timeline(request: Request, actor: str = Depends(admin_auth)):
        form = await _read_form(request)
        try:
            p = get_portfolio()
            before = _timeline_snapshot(p)
            updated = set_timeline(
                p,
                date.fromisoformat(str(form["start_date"])),
                date.fromisoformat(str(form["target_date"]))
                if form.get("target_date")
                else None,
            )
            persist(updated, p)
            record_update_audit(
                DEFAULT_PORTFOLIO,
                actor=actor,
                source=PortfolioAuditSource.WEB,
                action="timeline_set",
                entity_type=PortfolioAuditEntityType.TIMELINE,
                entity_id=None,
                before=before,
                after=_timeline_snapshot(updated),
                status=PortfolioAuditStatus.SUCCEEDED,
                summary="Set timeline",
            )
            return _redirect("/admin/settings", "Timeline set")
        except Exception as exc:
            _audit_failure(
                actor,
                PortfolioAuditSource.WEB,
                "timeline_set",
                PortfolioAuditEntityType.TIMELINE,
                None,
                "Failed timeline update",
                exc,
            )
            return render_admin_template(
                request,
                "settings.html",
                title="Settings",
                active_nav="settings",
                flash=safe_error_message(exc),
                status_code=422,
            )

    @app.post("/admin/risk-profile")
    async def admin_risk(request: Request, actor: str = Depends(admin_auth)):
        form = await _read_form(request)
        try:
            p = get_portfolio()
            before = _risk_snapshot(p)
            updated = set_risk_profile(
                p, RiskLevel(str(form["level"])), str(form.get("notes") or "") or None
            )
            persist(updated, p)
            record_update_audit(
                DEFAULT_PORTFOLIO,
                actor=actor,
                source=PortfolioAuditSource.WEB,
                action="risk_profile_set",
                entity_type=PortfolioAuditEntityType.RISK_PROFILE,
                entity_id=str(form["level"]),
                before=before,
                after=_risk_snapshot(updated),
                status=PortfolioAuditStatus.SUCCEEDED,
                summary=f"Set risk profile {str(form['level'])}",
            )
            return _redirect("/admin/settings", "Risk profile set")
        except Exception as exc:
            _audit_failure(
                actor,
                PortfolioAuditSource.WEB,
                "risk_profile_set",
                PortfolioAuditEntityType.RISK_PROFILE,
                str(form.get("level") or ""),
                "Failed risk profile update",
                exc,
            )
            return render_admin_template(
                request,
                "settings.html",
                title="Settings",
                active_nav="settings",
                flash=safe_error_message(exc),
                status_code=422,
            )

    return app


app = create_app()
