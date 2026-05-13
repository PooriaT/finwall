from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from enum import StrEnum


class OrderType(StrEnum):
    LIMIT = "limit"
    STOP_LOSS = "stop_loss"
    STOP_LIMIT = "stop_limit"


class OrderSide(StrEnum):
    BUY = "buy"
    SELL = "sell"


class TradeSide(StrEnum):
    BUY = "buy"
    SELL = "sell"


class RiskLevel(StrEnum):
    CONSERVATIVE = "conservative"
    MODERATE = "moderate"
    AGGRESSIVE = "aggressive"


def _require_non_empty(value: str, field_name: str) -> None:
    if not value.strip():
        raise ValueError(f"{field_name} must not be empty")


def _require_positive(value: Decimal, field_name: str) -> None:
    if value <= Decimal("0"):
        raise ValueError(f"{field_name} must be greater than zero")


def _require_non_negative(value: Decimal, field_name: str) -> None:
    if value < Decimal("0"):
        raise ValueError(f"{field_name} must not be negative")


@dataclass(frozen=True)
class CashBalance:
    currency: str
    amount: Decimal

    def __post_init__(self) -> None:
        _require_non_empty(self.currency, "currency")
        _require_non_negative(self.amount, "amount")


@dataclass(frozen=True)
class Holding:
    ticker: str
    share_count: Decimal
    average_purchase_price: Decimal
    sector: str | None = None

    def __post_init__(self) -> None:
        _require_non_empty(self.ticker, "ticker")
        _require_positive(self.share_count, "share_count")
        _require_non_negative(self.average_purchase_price, "average_purchase_price")
        if self.sector is not None:
            _require_non_empty(self.sector, "sector")


@dataclass(frozen=True)
class TradeTransaction:
    ticker: str
    side: TradeSide
    share_count: Decimal
    price: Decimal
    traded_on: date
    fees: Decimal = Decimal("0")

    def __post_init__(self) -> None:
        _require_non_empty(self.ticker, "ticker")
        _require_positive(self.share_count, "share_count")
        _require_positive(self.price, "price")
        _require_non_negative(self.fees, "fees")


@dataclass(frozen=True)
class ActiveOrder:
    ticker: str
    side: OrderSide
    order_type: OrderType
    share_count: Decimal
    limit_price: Decimal | None = None
    stop_price: Decimal | None = None

    def __post_init__(self) -> None:
        _require_non_empty(self.ticker, "ticker")
        _require_positive(self.share_count, "share_count")

        if self.limit_price is not None:
            _require_positive(self.limit_price, "limit_price")
        if self.stop_price is not None:
            _require_positive(self.stop_price, "stop_price")

        if self.order_type == OrderType.LIMIT and self.limit_price is None:
            raise ValueError("limit orders require limit_price")
        if self.order_type == OrderType.STOP_LOSS and self.stop_price is None:
            raise ValueError("stop-loss orders require stop_price")
        if self.order_type == OrderType.STOP_LIMIT:
            if self.limit_price is None or self.stop_price is None:
                raise ValueError("stop-limit orders require limit_price and stop_price")


@dataclass(frozen=True)
class WatchlistItem:
    ticker: str
    note: str | None = None

    def __post_init__(self) -> None:
        _require_non_empty(self.ticker, "ticker")
        if self.note is not None:
            _require_non_empty(self.note, "note")


@dataclass(frozen=True)
class Timeline:
    start_date: date
    target_date: date | None = None

    def __post_init__(self) -> None:
        if self.target_date is not None and self.target_date < self.start_date:
            raise ValueError("target_date must not be earlier than start_date")


@dataclass(frozen=True)
class InvestmentGoal:
    name: str
    target_amount: Decimal | None = None
    timeline: Timeline | None = None

    def __post_init__(self) -> None:
        _require_non_empty(self.name, "name")
        if self.target_amount is not None:
            _require_positive(self.target_amount, "target_amount")


@dataclass(frozen=True)
class RiskProfile:
    level: RiskLevel
    notes: str | None = None

    def __post_init__(self) -> None:
        if self.notes is not None:
            _require_non_empty(self.notes, "notes")


@dataclass(frozen=True)
class RecommendationRecord:
    title: str
    summary: str
    created_on: date

    def __post_init__(self) -> None:
        _require_non_empty(self.title, "title")
        _require_non_empty(self.summary, "summary")


@dataclass(frozen=True)
class Portfolio:
    name: str
    cash_balances: list[CashBalance] = field(default_factory=list)
    holdings: list[Holding] = field(default_factory=list)
    transactions: list[TradeTransaction] = field(default_factory=list)
    active_orders: list[ActiveOrder] = field(default_factory=list)
    watchlist: list[WatchlistItem] = field(default_factory=list)
    goals: list[InvestmentGoal] = field(default_factory=list)
    risk_profile: RiskProfile | None = None
    recommendations: list[RecommendationRecord] = field(default_factory=list)

    def __post_init__(self) -> None:
        _require_non_empty(self.name, "name")
