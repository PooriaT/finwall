from dataclasses import asdict, replace
from datetime import date
from decimal import Decimal, InvalidOperation
from html import escape

from fastapi import Depends, FastAPI, Header, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from pydantic import BaseModel

from finwall.config import Settings, settings
from finwall.models import ActiveOrder, OrderSide, OrderType, Portfolio, RiskLevel
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


def create_app(app_settings: Settings = settings) -> FastAPI:
    app = FastAPI(title="Finwall API")
    app.state.settings = app_settings
    app.state.store = build_portfolio_store(
        backend=app_settings.storage_backend,
        database_path=app_settings.database_path,
        database_url=app_settings.database_url,
    )
    app.state.store.initialize()

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

    def _layout(title: str, body: str, message: str | None = None) -> str:
        flash = f"<p><strong>{escape(message)}</strong></p>" if message else ""
        return (
            "<!doctype html><html><head><meta charset='utf-8'><title>"
            f"{escape(title)}</title></head><body>"
            "<nav><a href='/admin'>Admin Home</a> | <a href='/admin/portfolio'>Portfolio</a> | "
            "<a href='/admin/cash'>Cash</a> | <a href='/admin/holdings'>Holdings</a> | "
            "<a href='/admin/trades'>Trades</a> | <a href='/admin/orders'>Orders</a> | "
            "<a href='/admin/watchlist'>Watchlist</a> | <a href='/admin/settings'>Settings</a> "
            "<form style='display:inline' method='post' action='/admin/logout'>"
            "<button type='submit'>Logout</button></form></nav><hr/>"
            f"{flash}{body}</body></html>"
        )

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

    @app.get("/admin/login", response_class=HTMLResponse)
    def admin_login_get(request: Request):
        msg = request.query_params.get("msg")
        html = (
            "<h1>Finwall Admin Login</h1>"
            "<form method='post' action='/admin/login'>"
            "<label>API token <input type='password' name='token' required></label>"
            "<button type='submit'>Login</button></form>"
        )
        return HTMLResponse(_layout("Admin Login", html, msg))

    @app.post("/admin/login")
    async def admin_login_post(request: Request):
        form = await request.form()
        token = str(form.get("token", "")).strip()
        if not _token_is_valid(token):
            return HTMLResponse(
                _layout("Admin Login", "<h1>Finwall Admin Login</h1>", "Invalid token"),
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
        goal = portfolio.goals[-1].name if portfolio.goals else "N/A"
        risk = portfolio.risk_profile.level if portfolio.risk_profile else "N/A"
        summary = (
            f"<h1>Admin Home</h1><p>Cash balances: {len(portfolio.cash_balances)}</p>"
            f"<p>Holdings: {len(portfolio.holdings)}</p>"
            f"<p>Active orders: {len(portfolio.active_orders)}</p>"
            f"<p>Watchlist items: {len(portfolio.watchlist)}</p>"
            f"<p>Current goal: {escape(str(goal))}</p>"
            f"<p>Risk profile: {escape(str(risk))}</p>"
        )
        return HTMLResponse(
            _layout("Admin Home", summary, request.query_params.get("msg"))
        )

    @app.get("/api/v1/portfolio")
    def read_portfolio(_: str = Depends(auth)):
        return asdict(get_portfolio())

    @app.post("/api/v1/portfolio/cash/add")
    def cash_add(payload: CashRequest, _: str = Depends(auth)):
        portfolio = get_portfolio()
        updated = upsert_cash(
            portfolio, payload.currency, _to_decimal(payload.amount, "amount")
        )
        return persist(updated, portfolio)

    @app.post("/api/v1/portfolio/cash/withdraw")
    def cash_withdraw(payload: CashRequest, _: str = Depends(auth)):
        portfolio = get_portfolio()
        amount = _to_decimal(payload.amount, "amount")
        updated = upsert_cash(portfolio, payload.currency, -amount)
        return persist(updated, portfolio)

    @app.post("/api/v1/portfolio/holdings")
    def holdings_upsert(payload: HoldingRequest, _: str = Depends(auth)):
        portfolio = get_portfolio()
        updated = add_holding(
            portfolio,
            payload.ticker,
            _to_decimal(payload.shares, "shares"),
            _to_decimal(payload.average_price, "average_price"),
            payload.sector,
        )
        return persist(updated, portfolio)

    @app.delete("/api/v1/portfolio/holdings/{ticker}")
    def holdings_remove(ticker: str, _: str = Depends(auth)):
        portfolio = get_portfolio()
        filtered = tuple(item for item in portfolio.holdings if item.ticker != ticker)
        return persist(replace(portfolio, holdings=filtered), portfolio)

    @app.post("/api/v1/portfolio/trades/buy")
    def trade_buy(payload: TradeRequest, _: str = Depends(auth)):
        portfolio = get_portfolio()
        updated = record_buy(
            portfolio,
            payload.ticker,
            _to_decimal(payload.shares, "shares"),
            _to_decimal(payload.price, "price"),
            payload.currency,
            payload.trade_date or date.today(),
        )
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
            raise HTTPException(400, detail=str(exc)) from exc
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
            raise HTTPException(422, detail=str(exc)) from exc
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
            raise HTTPException(422, detail=str(exc)) from exc
        return persist(updated, portfolio)

    @app.put("/api/v1/portfolio/risk-profile")
    def risk_set(payload: RiskProfileRequest, _: str = Depends(auth)):
        portfolio = get_portfolio()
        return persist(
            set_risk_profile(portfolio, payload.level, payload.notes), portfolio
        )

    @app.get("/admin/portfolio", response_class=HTMLResponse)
    def admin_portfolio(_: str = Depends(admin_auth)):
        return HTMLResponse(
            _layout("Portfolio", f"<pre>{escape(str(asdict(get_portfolio())))}</pre>")
        )

    @app.get("/admin/cash", response_class=HTMLResponse)
    def admin_cash(request: Request, _: str = Depends(admin_auth)):
        body = (
            "<h1>Cash</h1><form method='post' action='/admin/cash/add'>"
            "<input name='currency' placeholder='USD' required><input name='amount' required>"
            "<button>Add cash</button></form>"
            "<form method='post' action='/admin/cash/withdraw'>"
            "<input name='currency' placeholder='USD' required><input name='amount' required>"
            "<button>Withdraw cash</button></form>"
        )
        return HTMLResponse(_layout("Cash", body, request.query_params.get("msg")))

    @app.post("/admin/cash/add")
    async def admin_cash_add(request: Request, _: str = Depends(admin_auth)):
        form = await request.form()
        try:
            portfolio = get_portfolio()
            updated = upsert_cash(
                portfolio,
                str(form["currency"]),
                _to_decimal(str(form["amount"]), "amount"),
            )
            persist(updated, portfolio)
            return _redirect("/admin/cash", "Cash updated")
        except Exception as exc:
            return HTMLResponse(
                _layout("Cash", "<h1>Cash</h1>", str(exc)), status_code=422
            )

    @app.post("/admin/cash/withdraw")
    async def admin_cash_withdraw(request: Request, _: str = Depends(admin_auth)):
        form = await request.form()
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
            return HTMLResponse(
                _layout("Cash", "<h1>Cash</h1>", str(exc)), status_code=422
            )

    @app.get("/admin/holdings", response_class=HTMLResponse)
    def admin_holdings(request: Request, _: str = Depends(admin_auth)):
        body = (
            "<h1>Holdings</h1>"
            "<form method='post' action='/admin/holdings'>"
            "<input name='ticker' required><input name='shares' required>"
            "<input name='average_price' required><input name='sector'>"
            "<button>Save holding</button></form>"
            "<form method='post' action='/admin/holdings/delete'>"
            "<input name='ticker' required><button>Delete holding</button></form>"
        )
        return HTMLResponse(_layout("Holdings", body, request.query_params.get("msg")))

    @app.post("/admin/holdings")
    async def admin_holdings_upsert(request: Request, _: str = Depends(admin_auth)):
        form = await request.form()
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
            return HTMLResponse(
                _layout("Holdings", "<h1>Holdings</h1>", str(exc)), status_code=422
            )

    @app.post("/admin/holdings/delete")
    async def admin_holdings_delete(request: Request, _: str = Depends(admin_auth)):
        form = await request.form()
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

    @app.get("/admin/trades", response_class=HTMLResponse)
    def admin_trades(request: Request, _: str = Depends(admin_auth)):
        body = (
            "<h1>Trades</h1>"
            "<form method='post' action='/admin/trades/buy'>"
            "<input name='ticker' required><input name='shares' required>"
            "<input name='price' required><input name='currency' required>"
            "<input name='trade_date'><button>Buy</button></form>"
            "<form method='post' action='/admin/trades/sell'>"
            "<input name='ticker' required><input name='shares' required>"
            "<input name='price' required><input name='currency' required>"
            "<input name='trade_date'><button>Sell</button></form>"
        )
        return HTMLResponse(_layout("Trades", body, request.query_params.get("msg")))

    async def _trade(request: Request, side: str):
        form = await request.form()
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
            return HTMLResponse(
                _layout("Trades", "<h1>Trades</h1>", str(exc)), status_code=422
            )

    @app.post("/admin/trades/sell")
    async def admin_trade_sell(request: Request, _: str = Depends(admin_auth)):
        try:
            return await _trade(request, "sell")
        except Exception as exc:
            return HTMLResponse(
                _layout("Trades", "<h1>Trades</h1>", str(exc)), status_code=422
            )

    @app.get("/admin/orders", response_class=HTMLResponse)
    def admin_orders(request: Request, _: str = Depends(admin_auth)):
        body = (
            "<h1>Orders</h1><form method='post' action='/admin/orders'>"
            "<input name='ticker' required><input name='side' required>"
            "<input name='order_type' required><input name='shares' required>"
            "<input name='limit_price'><input name='stop_price'>"
            "<button>Save order</button></form>"
            "<form method='post' action='/admin/orders/delete'>"
            "<input name='ticker' required><button>Delete order</button></form>"
        )
        return HTMLResponse(_layout("Orders", body, request.query_params.get("msg")))

    @app.post("/admin/orders")
    async def admin_orders_upsert(request: Request, _: str = Depends(admin_auth)):
        form = await request.form()
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
            return HTMLResponse(
                _layout("Orders", "<h1>Orders</h1>", str(exc)), status_code=422
            )

    @app.post("/admin/orders/delete")
    async def admin_orders_delete(request: Request, _: str = Depends(admin_auth)):
        form = await request.form()
        p = get_portfolio()
        persist(remove_order(p, str(form["ticker"])), p)
        return _redirect("/admin/orders", "Order deleted")

    @app.get("/admin/watchlist", response_class=HTMLResponse)
    def admin_watchlist(request: Request, _: str = Depends(admin_auth)):
        body = (
            "<h1>Watchlist</h1><form method='post' action='/admin/watchlist'>"
            "<input name='ticker' required><input name='note'>"
            "<button>Save item</button></form>"
            "<form method='post' action='/admin/watchlist/delete'>"
            "<input name='ticker' required><button>Delete item</button></form>"
        )
        return HTMLResponse(_layout("Watchlist", body, request.query_params.get("msg")))

    @app.post("/admin/watchlist")
    async def admin_watchlist_upsert(request: Request, _: str = Depends(admin_auth)):
        form = await request.form()
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
        form = await request.form()
        p = get_portfolio()
        persist(remove_watchlist_item(p, str(form["ticker"])), p)
        return _redirect("/admin/watchlist", "Watchlist item removed")

    @app.get("/admin/settings", response_class=HTMLResponse)
    def admin_settings(request: Request, _: str = Depends(admin_auth)):
        body = (
            "<h1>Settings</h1><form method='post' action='/admin/goal'>"
            "<input name='name' required><input name='target_amount'>"
            "<button>Set goal</button></form>"
            "<form method='post' action='/admin/timeline'>"
            "<input name='start_date' required><input name='target_date'>"
            "<button>Set timeline</button></form>"
            "<form method='post' action='/admin/risk-profile'>"
            "<input name='level' required><input name='notes'>"
            "<button>Set risk profile</button></form>"
        )
        return HTMLResponse(_layout("Settings", body, request.query_params.get("msg")))

    @app.post("/admin/goal")
    async def admin_goal(request: Request, _: str = Depends(admin_auth)):
        form = await request.form()
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
        form = await request.form()
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
            return HTMLResponse(
                _layout("Settings", "<h1>Settings</h1>", str(exc)), status_code=422
            )

    @app.post("/admin/risk-profile")
    async def admin_risk(request: Request, _: str = Depends(admin_auth)):
        form = await request.form()
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
