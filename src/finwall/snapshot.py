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
    price_status: str
    missing_price_message: str | None
    allocation_in_invested_percent: str | None
    allocation_in_total_percent: str | None


@dataclass(frozen=True)
class ActiveOrderSnapshot:
    ticker: str
    side: str
    order_type: str
    share_count: str
    limit_price: str | None
    stop_price: str | None
    description: str


@dataclass(frozen=True)
class PortfolioSnapshot:
    cash_balance: str
    cash_balances: dict[str, str]
    invested_value: str
    total_portfolio_value: str | None
    cash_allocation_percent: str | None
    invested_allocation_percent: str | None
    holdings: tuple[HoldingSnapshot, ...]
    active_orders: tuple[ActiveOrderSnapshot, ...]
    total_unrealized_gain_loss: str | None
    total_unrealized_gain_loss_percent: str | None
    price_completeness_status: str
    multi_currency_cash: bool
    valuation_currency: str | None
    valuation_status: str
    risk_assessment: dict[str, object] | None = None

    def to_json(self) -> str:
        return json.dumps(asdict(self), indent=2)


ZERO = Decimal("0")
HUNDRED = Decimal("100")


def generate_snapshot(
    portfolio: Portfolio,
    latest_prices: dict[str, Decimal] | None = None,
) -> PortfolioSnapshot:
    latest_prices = normalize_prices(latest_prices or {})
    cash_by_currency = build_cash_by_currency(portfolio)

    holdings = [
        build_holding_snapshot(holding, latest_prices.get(holding.ticker.upper()))
        for holding in portfolio.holdings
    ]

    invested_total = sum(
        (
            Decimal(item.estimated_value)
            for item in holdings
            if item.estimated_value is not None
        ),
        start=ZERO,
    )
    total_cost_basis = sum(
        (
            Decimal(item.average_purchase_price) * Decimal(item.share_count)
            for item in holdings
        ),
        start=ZERO,
    )

    cash_total = single_currency_cash_total(cash_by_currency)
    total_value = cash_total + invested_total if cash_total is not None else None

    cash_percent = (
        calculate_percentage(cash_total, total_value)
        if cash_total is not None and total_value is not None
        else None
    )
    invested_percent = (
        calculate_percentage(invested_total, total_value)
        if total_value is not None
        else None
    )

    for index, holding in enumerate(holdings):
        allocation_in_invested = (
            calculate_percentage(Decimal(holding.estimated_value), invested_total)
            if holding.estimated_value is not None
            else None
        )
        allocation_in_total = (
            calculate_percentage(Decimal(holding.estimated_value), total_value)
            if holding.estimated_value is not None and total_value is not None
            else None
        )
        holdings[index] = HoldingSnapshot(
            ticker=holding.ticker,
            share_count=holding.share_count,
            average_purchase_price=holding.average_purchase_price,
            current_price=holding.current_price,
            estimated_value=holding.estimated_value,
            unrealized_gain_loss=holding.unrealized_gain_loss,
            price_available=holding.price_available,
            price_status=holding.price_status,
            missing_price_message=holding.missing_price_message,
            allocation_in_invested_percent=format_decimal(allocation_in_invested)
            if allocation_in_invested is not None
            else None,
            allocation_in_total_percent=format_decimal(allocation_in_total)
            if allocation_in_total is not None
            else None,
        )

    available_holdings = [item for item in holdings if item.price_available]
    if not holdings:
        price_completeness_status = "complete"
    elif not available_holdings:
        price_completeness_status = "missing"
    elif len(available_holdings) == len(holdings):
        price_completeness_status = "complete"
    else:
        price_completeness_status = "partial"

    total_unrealized = sum(
        (
            Decimal(item.unrealized_gain_loss)
            for item in holdings
            if item.unrealized_gain_loss is not None
        ),
        start=ZERO,
    )
    total_unrealized_percent = (
        calculate_percentage(total_unrealized, total_cost_basis)
        if total_cost_basis != ZERO
        else None
    )

    active_orders = tuple(
        build_active_order_snapshot(order) for order in portfolio.active_orders
    )
    multi_currency_cash = len(cash_by_currency) > 1
    valuation_currency = (
        next(iter(cash_by_currency.keys()), None) if not multi_currency_cash else None
    )
    valuation_status = derive_valuation_status(
        multi_currency_cash, total_value, price_completeness_status
    )

    return PortfolioSnapshot(
        cash_balance=format_cash_balance(cash_by_currency),
        cash_balances={
            currency: format_decimal(amount)
            for currency, amount in cash_by_currency.items()
        },
        invested_value=format_decimal(invested_total),
        total_portfolio_value=format_decimal(total_value)
        if total_value is not None
        else None,
        cash_allocation_percent=format_decimal(cash_percent)
        if cash_percent is not None
        else None,
        invested_allocation_percent=format_decimal(invested_percent)
        if invested_percent is not None
        else None,
        holdings=tuple(holdings),
        active_orders=active_orders,
        total_unrealized_gain_loss=format_decimal(total_unrealized),
        total_unrealized_gain_loss_percent=format_decimal(total_unrealized_percent)
        if total_unrealized_percent is not None
        else None,
        price_completeness_status=price_completeness_status,
        multi_currency_cash=multi_currency_cash,
        valuation_currency=valuation_currency,
        valuation_status=valuation_status,
    )


def derive_valuation_status(
    multi_currency_cash: bool,
    total_value: Decimal | None,
    price_completeness_status: str,
) -> str:
    if multi_currency_cash:
        return "multi_currency_cash_unsupported"
    if total_value is None:
        return "missing_prices"
    if price_completeness_status != "complete":
        return "missing_prices"
    return "complete"


def build_cash_by_currency(portfolio: Portfolio) -> dict[str, Decimal]:
    cash_by_currency: dict[str, Decimal] = {}
    for balance in portfolio.cash_balances:
        currency = balance.currency.upper()
        cash_by_currency[currency] = (
            cash_by_currency.get(currency, ZERO) + balance.amount
        )
    return cash_by_currency


def single_currency_cash_total(cash_by_currency: dict[str, Decimal]) -> Decimal | None:
    if len(cash_by_currency) > 1:
        return None
    return next(iter(cash_by_currency.values()), ZERO)


def format_cash_balance(cash_by_currency: dict[str, Decimal]) -> str:
    if not cash_by_currency:
        return format_decimal(ZERO)
    return ", ".join(
        f"{currency} {format_decimal(amount)}"
        for currency, amount in sorted(cash_by_currency.items())
    )


def normalize_prices(latest_prices: dict[str, Decimal]) -> dict[str, Decimal]:
    return {ticker.upper(): price for ticker, price in latest_prices.items()}


def build_holding_snapshot(
    holding: Holding,
    current_price: Decimal | None,
) -> HoldingSnapshot:
    if current_price is None:
        return HoldingSnapshot(
            ticker=holding.ticker,
            share_count=format_decimal(holding.share_count),
            average_purchase_price=format_decimal(holding.average_purchase_price),
            current_price=None,
            estimated_value=None,
            unrealized_gain_loss=None,
            price_available=False,
            price_status="missing",
            missing_price_message=(
                f"Price unavailable for {holding.ticker}; provide --price or use --live-prices."
            ),
            allocation_in_invested_percent=None,
            allocation_in_total_percent=None,
        )

    estimated_value = holding.share_count * current_price
    unrealized_gain_loss = (
        current_price - holding.average_purchase_price
    ) * holding.share_count

    return HoldingSnapshot(
        ticker=holding.ticker,
        share_count=format_decimal(holding.share_count),
        average_purchase_price=format_decimal(holding.average_purchase_price),
        current_price=format_decimal(current_price),
        estimated_value=format_decimal(estimated_value),
        unrealized_gain_loss=format_decimal(unrealized_gain_loss),
        price_available=True,
        price_status="available",
        missing_price_message=None,
        allocation_in_invested_percent=None,
        allocation_in_total_percent=None,
    )


def calculate_percentage(value: Decimal, total: Decimal) -> Decimal:
    if total == ZERO:
        return ZERO
    return (value / total) * HUNDRED


def build_active_order_snapshot(order: ActiveOrder) -> ActiveOrderSnapshot:
    return ActiveOrderSnapshot(
        ticker=order.ticker,
        side=order.side.value,
        order_type=order.order_type.value,
        share_count=format_decimal(order.share_count),
        limit_price=format_decimal(order.limit_price)
        if order.limit_price is not None
        else None,
        stop_price=format_decimal(order.stop_price)
        if order.stop_price is not None
        else None,
        description=format_order(order),
    )


def format_order(order: ActiveOrder) -> str:
    details = [
        f"{order.ticker} {order.side.value} {order.order_type.value}",
        f"shares={format_decimal(order.share_count)}",
    ]
    if order.limit_price is not None:
        details.append(f"limit={format_decimal(order.limit_price)}")
    if order.stop_price is not None:
        details.append(f"stop={format_decimal(order.stop_price)}")
    return " ".join(details)


def format_decimal(value: Decimal) -> str:
    return f"{value.quantize(Decimal('0.01'))}"
