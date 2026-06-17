import json
import logging
from dataclasses import asdict, replace
from datetime import date
from decimal import Decimal, InvalidOperation
from urllib.parse import parse_qs

from fastapi import Depends, FastAPI, Header, HTTPException, Request
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from finwall.admin_dashboard import build_dashboard_view
from finwall.admin_ui import ADMIN_STATIC_DIR, render_admin_template
from finwall.config import Settings, settings
from finwall.models import ActiveOrder, OrderSide, OrderType, Portfolio, RiskLevel
from finwall.portfolio_audit import (
    PortfolioAuditEntityType,
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

    def auth(request: Request, authorization: str | None = Header(default=None)) -> str:
        token = request.app.state.settings.api_token
        if not token:
            raise HTTPException(401, detail="authentication is not configured")
        if authorization is None or not authorization.startswith("Bearer "):
            raise HTTPException(401, detail="invalid authentication credentials")
        if authorization.removeprefix("Bearer ").strip() != token:
            raise HTTPException(401, detail="invalid authentication credentials")
        return "api-admin"

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

    @app.get("/api/v1/portfolio")
    def read_portfolio(_: str = Depends(auth)):
        return asdict(get_portfolio())

    @app.get("/api/v1/portfolio/audit")
    def read_portfolio_audit(limit: int = 50, _: str = Depends(auth)):
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
    def cash_withdraw(payload: CashRequest, _: str = Depends(auth)):
        portfolio = get_portfolio()
        amount = _to_decimal(payload.amount, "amount")
        try:
            updated = upsert_cash(portfolio, payload.currency, -amount)
        except ValueError as exc:
            raise HTTPException(400, detail=safe_error_message(exc)) from exc
        return persist(updated, portfolio)

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
    def holdings_remove(ticker: str, _: str = Depends(auth)):
        portfolio = get_portfolio()
        filtered = tuple(item for item in portfolio.holdings if item.ticker != ticker)
        return persist(replace(portfolio, holdings=filtered), portfolio)

    @app.post("/api/v1/portfolio/trades/buy")
    def trade_buy(payload: TradeRequest, _: str = Depends(auth)):
        portfolio = get_portfolio()
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
            raise HTTPException(400, detail=safe_error_message(exc)) from exc
        return persist(updated, portfolio)

    @app.post("/api/v1/portfolio/trades/sell")
    def trade_sell(payload: TradeRequest, _: str = Depends(auth)):
        portfolio = get_portfolio()
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
            raise HTTPException(400, detail=safe_error_message(exc)) from exc
        return persist(updated, portfolio)

    @app.post("/api/v1/portfolio/orders")
    def orders_upsert(payload: OrderRequest, _: str = Depends(auth)):
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
        except ValueError as exc:
            raise HTTPException(422, detail=safe_error_message(exc)) from exc
        portfolio = get_portfolio()
        return persist(add_or_update_order(portfolio, order), portfolio)

    @app.delete("/api/v1/portfolio/orders/{ticker}")
    def orders_remove(ticker: str, _: str = Depends(auth)):
        portfolio = get_portfolio()
        return persist(remove_order(portfolio, ticker), portfolio)

    @app.post("/api/v1/portfolio/watchlist")
    def watchlist_upsert(payload: WatchlistRequest, _: str = Depends(auth)):
        portfolio = get_portfolio()
        return persist(
            add_watchlist_item(portfolio, payload.ticker, payload.note), portfolio
        )

    @app.delete("/api/v1/portfolio/watchlist/{ticker}")
    def watchlist_remove(ticker: str, _: str = Depends(auth)):
        portfolio = get_portfolio()
        return persist(remove_watchlist_item(portfolio, ticker), portfolio)

    @app.put("/api/v1/portfolio/goal")
    def goal_set(payload: GoalRequest, _: str = Depends(auth)):
        portfolio = get_portfolio()
        target = (
            _to_decimal(payload.target_amount, "target_amount")
            if payload.target_amount
            else None
        )
        return persist(set_goal(portfolio, payload.name, target), portfolio)

    @app.put("/api/v1/portfolio/timeline")
    def timeline_set(payload: TimelineRequest, _: str = Depends(auth)):
        portfolio = get_portfolio()
        try:
            updated = set_timeline(portfolio, payload.start_date, payload.target_date)
        except ValueError as exc:
            raise HTTPException(422, detail=safe_error_message(exc)) from exc
        return persist(updated, portfolio)

    @app.put("/api/v1/portfolio/risk-profile")
    def risk_set(payload: RiskProfileRequest, _: str = Depends(auth)):
        portfolio = get_portfolio()
        return persist(
            set_risk_profile(portfolio, payload.level, payload.notes), portfolio
        )

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
    async def admin_cash_add(request: Request, _: str = Depends(admin_auth)):
        form = await _read_form(request)
        try:
            portfolio = get_portfolio()
            updated = upsert_cash(
                portfolio,
                str(form["currency"]),
                _to_decimal(str(form["amount"]), "amount"),
            )
            persist(updated, portfolio)
            record_update_audit(
                DEFAULT_PORTFOLIO,
                actor="web-admin",
                source=PortfolioAuditSource.WEB,
                action="cash_add",
                entity_type=PortfolioAuditEntityType.CASH,
                entity_id=str(form["currency"]),
                before=None,
                after=None,
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
    async def admin_cash_withdraw(request: Request, _: str = Depends(admin_auth)):
        form = await _read_form(request)
        try:
            portfolio = get_portfolio()
            updated = upsert_cash(
                portfolio,
                str(form["currency"]),
                -_to_decimal(str(form["amount"]), "amount"),
            )
            persist(updated, portfolio)
            return _redirect("/admin/cash", "Cash withdrawn")
        except Exception as exc:
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
    async def admin_holdings_upsert(request: Request, _: str = Depends(admin_auth)):
        form = await _read_form(request)
        try:
            p = get_portfolio()
            updated = add_holding(
                p,
                str(form["ticker"]),
                _to_decimal(str(form["shares"]), "shares"),
                _to_decimal(str(form["average_price"]), "average_price"),
                str(form.get("sector") or "") or None,
            )
            persist(updated, p)
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
    async def admin_holdings_delete(request: Request, _: str = Depends(admin_auth)):
        form = await _read_form(request)
        p = get_portfolio()
        persist(
            replace(
                p,
                holdings=tuple(
                    item for item in p.holdings if item.ticker != str(form["ticker"])
                ),
            ),
            p,
        )
        return _redirect("/admin/holdings", "Holding deleted")

    @app.get("/admin/trades")
    def admin_trades(request: Request, _: str = Depends(admin_auth)):
        return render_admin_template(
            request, "trades.html", title="Trades", active_nav="trades"
        )

    async def _trade(request: Request, side: str):
        form = await _read_form(request)
        p = get_portfolio()
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
        persist(updated, p)
        return _redirect("/admin/trades", f"Trade {side} recorded")

    @app.post("/admin/trades/buy")
    async def admin_trade_buy(request: Request, _: str = Depends(admin_auth)):
        try:
            return await _trade(request, "buy")
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
    async def admin_trade_sell(request: Request, _: str = Depends(admin_auth)):
        try:
            return await _trade(request, "sell")
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
    async def admin_orders_upsert(request: Request, _: str = Depends(admin_auth)):
        form = await _read_form(request)
        try:
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
            p = get_portfolio()
            persist(add_or_update_order(p, order), p)
            return _redirect("/admin/orders", "Order saved")
        except Exception as exc:
            return render_admin_template(
                request,
                "orders.html",
                title="Orders",
                active_nav="orders",
                flash=safe_error_message(exc),
                status_code=422,
            )

    @app.post("/admin/orders/delete")
    async def admin_orders_delete(request: Request, _: str = Depends(admin_auth)):
        form = await _read_form(request)
        p = get_portfolio()
        persist(remove_order(p, str(form["ticker"])), p)
        return _redirect("/admin/orders", "Order deleted")

    @app.get("/admin/watchlist")
    def admin_watchlist(request: Request, _: str = Depends(admin_auth)):
        return render_admin_template(
            request, "watchlist.html", title="Watchlist", active_nav="watchlist"
        )

    @app.post("/admin/watchlist")
    async def admin_watchlist_upsert(request: Request, _: str = Depends(admin_auth)):
        form = await _read_form(request)
        p = get_portfolio()
        persist(
            add_watchlist_item(
                p, str(form["ticker"]), str(form.get("note") or "") or None
            ),
            p,
        )
        return _redirect("/admin/watchlist", "Watchlist updated")

    @app.post("/admin/watchlist/delete")
    async def admin_watchlist_delete(request: Request, _: str = Depends(admin_auth)):
        form = await _read_form(request)
        p = get_portfolio()
        persist(remove_watchlist_item(p, str(form["ticker"])), p)
        return _redirect("/admin/watchlist", "Watchlist item removed")

    @app.get("/admin/settings")
    def admin_settings(request: Request, _: str = Depends(admin_auth)):
        return render_admin_template(
            request, "settings.html", title="Settings", active_nav="settings"
        )

    @app.post("/admin/goal")
    async def admin_goal(request: Request, _: str = Depends(admin_auth)):
        form = await _read_form(request)
        p = get_portfolio()
        persist(
            set_goal(
                p,
                str(form["name"]),
                _to_decimal(str(form["target_amount"]), "target_amount")
                if form.get("target_amount")
                else None,
            ),
            p,
        )
        return _redirect("/admin/settings", "Goal set")

    @app.post("/admin/timeline")
    async def admin_timeline(request: Request, _: str = Depends(admin_auth)):
        form = await _read_form(request)
        try:
            p = get_portfolio()
            persist(
                set_timeline(
                    p,
                    date.fromisoformat(str(form["start_date"])),
                    date.fromisoformat(str(form["target_date"]))
                    if form.get("target_date")
                    else None,
                ),
                p,
            )
            return _redirect("/admin/settings", "Timeline set")
        except Exception as exc:
            return render_admin_template(
                request,
                "settings.html",
                title="Settings",
                active_nav="settings",
                flash=safe_error_message(exc),
                status_code=422,
            )

    @app.post("/admin/risk-profile")
    async def admin_risk(request: Request, _: str = Depends(admin_auth)):
        form = await _read_form(request)
        p = get_portfolio()
        persist(
            set_risk_profile(
                p, RiskLevel(str(form["level"])), str(form.get("notes") or "") or None
            ),
            p,
        )
        return _redirect("/admin/settings", "Risk profile set")

    return app


app = create_app()
