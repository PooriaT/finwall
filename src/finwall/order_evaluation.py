from dataclasses import asdict, dataclass
from decimal import Decimal

from finwall.models import OrderSide, OrderType, Portfolio, RiskLevel
from finwall.risk import RISK_RULES_BY_LEVEL
from finwall.snapshot import PortfolioSnapshot, format_decimal

ZERO = Decimal("0")
HUNDRED = Decimal("100")


@dataclass(frozen=True)
class ProposedOrder:
    ticker: str
    side: OrderSide
    order_type: OrderType
    entry_price: Decimal
    share_count: Decimal | None = None
    stop_price: Decimal | None = None
    limit_price: Decimal | None = None
    target_price: Decimal | None = None
    currency: str = "USD"


@dataclass(frozen=True)
class OrderEvaluation:
    ticker: str
    side: str
    order_type: str
    requested_share_count: str | None
    maximum_affordable_shares: str
    maximum_risk_allowed_shares: str | None
    suggested_maximum_shares: str
    estimated_total_cost: str | None
    estimated_total_proceeds: str | None
    maximum_capital_at_risk: str | None
    expected_upside: str | None
    expected_downside: str | None
    risk_reward_ratio: str | None
    cash_after_order: str | None
    cash_reserve_percent_after_order: str | None
    remaining_shares_after_sale: str | None
    valid: bool
    errors: tuple[str, ...]
    warnings: tuple[str, ...]

    def as_dict(self) -> dict[str, object]:
        return asdict(self)


def evaluate_proposed_order(
    portfolio: Portfolio,
    snapshot: PortfolioSnapshot,
    order: ProposedOrder,
) -> OrderEvaluation:
    errors: list[str] = []
    warnings: list[str] = [
        "This is an evaluation of the provided order, not a recommendation."
    ]
    _validate_order_type_requirements(order, errors)
    _validate_positive_values(order, errors)

    if order.side == OrderSide.BUY and order.order_type == OrderType.STOP_LOSS:
        errors.append("Buy stop-loss orders are not supported in this evaluation.")

    risk_level = (
        portfolio.risk_profile.level
        if portfolio.risk_profile is not None
        else RiskLevel.MODERATE
    )
    rules = RISK_RULES_BY_LEVEL[risk_level]

    cash_total = _get_cash_total_in_currency(portfolio, order.currency)
    requested = order.share_count if order.share_count is not None else ZERO

    max_by_cash = (
        _max_shares(cash_total, order.entry_price)
        if order.side == OrderSide.BUY
        else ZERO
    )
    reserve_amount = cash_total * (rules.min_cash_reserve_percent / HUNDRED)
    deployable = max(cash_total - reserve_amount, ZERO)
    max_by_reserve = (
        _max_shares(deployable, order.entry_price)
        if order.side == OrderSide.BUY
        else ZERO
    )

    max_by_risk: Decimal | None = None
    downside_per_share: Decimal | None = None
    if order.stop_price is None:
        warnings.append(
            "Stop price missing; expected downside and risk/reward are unavailable."
        )
    elif order.side == OrderSide.BUY:
        if order.stop_price >= order.entry_price:
            errors.append("For buy orders, stop_price must be below entry_price.")
        else:
            downside_per_share = order.entry_price - order.stop_price
            max_capital_at_risk = deployable * (
                rules.max_unrealized_loss_percent / HUNDRED
            )
            max_by_risk = _max_shares(max_capital_at_risk, downside_per_share)
    else:
        current = _find_holding_price(snapshot, order.ticker) or order.entry_price
        downside_per_share = (
            current - order.stop_price if order.stop_price is not None else None
        )

    if order.target_price is None:
        warnings.append(
            "Target price missing; expected upside and risk/reward are unavailable."
        )
    elif order.side == OrderSide.BUY and order.target_price <= order.entry_price:
        errors.append("For buy orders, target_price must be above entry_price.")

    if not portfolio.goals:
        warnings.append("No portfolio goal found.")
    elif portfolio.goals[0].target_amount is None:
        warnings.append("Portfolio goal exists, but target amount is missing.")

    if snapshot.valuation_status != "complete":
        warnings.append(
            (
                "Total portfolio valuation is unavailable or partial due to missing "
                "prices or unsupported multi-currency valuation."
            )
        )

    if order.side == OrderSide.BUY:
        suggested = min(max_by_cash, max_by_reserve)
        if max_by_risk is not None:
            suggested = min(suggested, max_by_risk)

        estimated_cost = requested * order.entry_price
        cash_after = cash_total - estimated_cost
        reserve_after = (
            (cash_after / cash_total) * HUNDRED if cash_total > ZERO else ZERO
        )
        if reserve_after < rules.min_cash_reserve_percent:
            warnings.append(
                "This proposed order exceeds the configured cash reserve rule."
            )
        else:
            warnings.append(
                "This proposed order fits the configured cash reserve rule."
            )
        if requested > suggested:
            warnings.append(
                "High severity: requested shares exceed the calculated risk-based safe maximum."
            )

        expected_upside = (
            (order.target_price - order.entry_price) * requested
            if order.target_price is not None and order.target_price > order.entry_price
            else None
        )
        expected_downside = (
            (order.entry_price - order.stop_price) * requested
            if order.stop_price is not None and order.stop_price < order.entry_price
            else None
        )
        rr = (
            expected_upside / expected_downside
            if expected_upside is not None and expected_downside not in {None, ZERO}
            else None
        )

        return OrderEvaluation(
            ticker=order.ticker,
            side=order.side.value,
            order_type=order.order_type.value,
            requested_share_count=format_decimal(requested)
            if order.share_count is not None
            else None,
            maximum_affordable_shares=format_decimal(max_by_cash),
            maximum_risk_allowed_shares=format_decimal(max_by_risk)
            if max_by_risk is not None
            else None,
            suggested_maximum_shares=format_decimal(suggested),
            estimated_total_cost=format_decimal(estimated_cost),
            estimated_total_proceeds=None,
            maximum_capital_at_risk=format_decimal(expected_downside)
            if expected_downside is not None
            else None,
            expected_upside=format_decimal(expected_upside)
            if expected_upside is not None
            else None,
            expected_downside=format_decimal(expected_downside)
            if expected_downside is not None
            else None,
            risk_reward_ratio=format_decimal(rr) if rr is not None else None,
            cash_after_order=format_decimal(cash_after),
            cash_reserve_percent_after_order=format_decimal(reserve_after),
            remaining_shares_after_sale=None,
            valid=not errors,
            errors=tuple(errors),
            warnings=tuple(warnings),
        )

    held = _held_shares(portfolio, order.ticker)
    if order.share_count is None:
        errors.append("Share count is required for sell order evaluation.")
    elif requested > held:
        errors.append("Cannot sell more shares than currently held.")

    proceeds = requested * order.entry_price
    return OrderEvaluation(
        ticker=order.ticker,
        side=order.side.value,
        order_type=order.order_type.value,
        requested_share_count=format_decimal(requested)
        if order.share_count is not None
        else None,
        maximum_affordable_shares="0.00",
        maximum_risk_allowed_shares=None,
        suggested_maximum_shares="0.00",
        estimated_total_cost=None,
        estimated_total_proceeds=format_decimal(proceeds),
        maximum_capital_at_risk=format_decimal(downside_per_share * requested)
        if downside_per_share is not None
        else None,
        expected_upside=None,
        expected_downside=None,
        risk_reward_ratio=None,
        cash_after_order=None,
        cash_reserve_percent_after_order=None,
        remaining_shares_after_sale=format_decimal(held - requested),
        valid=not errors,
        errors=tuple(errors),
        warnings=tuple(warnings),
    )


def _max_shares(cash: Decimal, price: Decimal) -> Decimal:
    return (
        (cash / price).to_integral_value(rounding="ROUND_FLOOR")
        if price > ZERO
        else ZERO
    )


def _get_cash_total_in_currency(portfolio: Portfolio, currency: str) -> Decimal:
    return sum(
        (
            b.amount
            for b in portfolio.cash_balances
            if b.currency.upper() == currency.upper()
        ),
        start=ZERO,
    )


def _held_shares(portfolio: Portfolio, ticker: str) -> Decimal:
    holding = next(
        (item for item in portfolio.holdings if item.ticker.upper() == ticker.upper()),
        None,
    )
    return holding.share_count if holding is not None else ZERO


def _find_holding_price(snapshot: PortfolioSnapshot, ticker: str) -> Decimal | None:
    item = next(
        (h for h in snapshot.holdings if h.ticker.upper() == ticker.upper()), None
    )
    return (
        Decimal(item.current_price)
        if item is not None and item.current_price is not None
        else None
    )


def _validate_order_type_requirements(order: ProposedOrder, errors: list[str]) -> None:
    if order.order_type == OrderType.LIMIT and order.limit_price is None:
        errors.append("Limit orders require limit_price.")
    if order.order_type == OrderType.STOP_LOSS and order.stop_price is None:
        errors.append("Stop-loss orders require stop_price.")
    if order.order_type == OrderType.STOP_LIMIT and (
        order.stop_price is None or order.limit_price is None
    ):
        errors.append("Stop-limit orders require both stop_price and limit_price.")


def _validate_positive_values(order: ProposedOrder, errors: list[str]) -> None:
    if order.entry_price <= ZERO:
        errors.append("entry_price must be greater than zero.")
    if order.share_count is not None and order.share_count <= ZERO:
        errors.append("share_count must be greater than zero when provided.")
