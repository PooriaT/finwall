from dataclasses import asdict, replace
from datetime import date
from decimal import Decimal, InvalidOperation

from fastapi import Depends, FastAPI, Header, HTTPException, Request
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

    def auth(request: Request, authorization: str | None = Header(default=None)) -> str:
        token = request.app.state.settings.api_token
        if not token:
            raise HTTPException(401, detail="authentication is not configured")
        if authorization is None or not authorization.startswith("Bearer "):
            raise HTTPException(401, detail="invalid authentication credentials")
        if authorization.removeprefix("Bearer ").strip() != token:
            raise HTTPException(401, detail="invalid authentication credentials")
        return "api-admin"

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

    return app


app = create_app()
