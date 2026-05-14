import json
from dataclasses import asdict, dataclass
from decimal import Decimal

from finwall.models import ActiveOrder, Holding, Portfolio


@dataclass(frozen=True)
class HoldingSnapshot:
    ticker: str
    share_count: str
    average_purchase_price: str
    current_price: str | None
    estimated_value: str | None
    unrealized_gain_loss: str | None
    price_available: bool


@dataclass(frozen=True)
class PortfolioSnapshot:
    cash_balance: str
    invested_value: str
    total_portfolio_value: str
    cash_allocation_percent: str
    invested_allocation_percent: str
    holdings: tuple[HoldingSnapshot, ...]
    active_orders: tuple[str, ...]

    def to_json(self) -> str:
        return json.dumps(asdict(self), indent=2)


ZERO = Decimal("0")
HUNDRED = Decimal("100")


def generate_snapshot(
    portfolio: Portfolio,
    latest_prices: dict[str, Decimal] | None = None,
) -> PortfolioSnapshot:
    latest_prices = latest_prices or {}

    cash_total = sum(
        (balance.amount for balance in portfolio.cash_balances),
        start=ZERO,
    )

    holdings = tuple(
        build_holding_snapshot(holding, latest_prices.get(holding.ticker))
        for holding in portfolio.holdings
    )

    invested_total = sum(
        (
            Decimal(item.estimated_value)
            for item in holdings
            if item.estimated_value is not None
        ),
        start=ZERO,
    )

    total_value = cash_total + invested_total

    cash_percent = calculate_percentage(cash_total, total_value)
    invested_percent = calculate_percentage(invested_total, total_value)

    active_orders = tuple(format_order(order) for order in portfolio.active_orders)

    return PortfolioSnapshot(
        cash_balance=format_decimal(cash_total),
        invested_value=format_decimal(invested_total),
        total_portfolio_value=format_decimal(total_value),
        cash_allocation_percent=format_decimal(cash_percent),
        invested_allocation_percent=format_decimal(invested_percent),
        holdings=holdings,
        active_orders=active_orders,
    )


def build_holding_snapshot(
    holding: Holding,
    current_price: Decimal | None,
) -> HoldingSnapshot:
    if current_price is None:
        return HoldingSnapshot(
            ticker=holding.ticker,
            share_count=format_decimal(holding.share_count),
            average_purchase_price=format_decimal(
                holding.average_purchase_price
            ),
            current_price=None,
            estimated_value=None,
            unrealized_gain_loss=None,
            price_available=False,
        )

    estimated_value = holding.share_count * current_price
    unrealized_gain_loss = (
        current_price - holding.average_purchase_price
    ) * holding.share_count

    return HoldingSnapshot(
        ticker=holding.ticker,
        share_count=format_decimal(holding.share_count),
        average_purchase_price=format_decimal(
            holding.average_purchase_price
        ),
        current_price=format_decimal(current_price),
        estimated_value=format_decimal(estimated_value),
        unrealized_gain_loss=format_decimal(unrealized_gain_loss),
        price_available=True,
    )


def calculate_percentage(value: Decimal, total: Decimal) -> Decimal:
    if total == ZERO:
        return ZERO
    return (value / total) * HUNDRED


def format_order(order: ActiveOrder) -> str:
    return (
        f"{order.ticker} {order.side.value} {order.order_type.value} "
        f"shares={format_decimal(order.share_count)}"
    )


def format_decimal(value: Decimal) -> str:
    return f"{value.quantize(Decimal('0.01'))}"
