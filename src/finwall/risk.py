from dataclasses import asdict, dataclass
from decimal import Decimal

from finwall.models import OrderSide, OrderType, Portfolio, RiskLevel
from finwall.snapshot import PortfolioSnapshot


@dataclass(frozen=True)
class RiskRuleConfig:
    risk_level: RiskLevel
    max_single_position_percent: Decimal
    max_cash_deployment_percent: Decimal
    min_cash_reserve_percent: Decimal
    max_unrealized_loss_percent: Decimal
    stop_loss_required_above_position_percent: Decimal


@dataclass(frozen=True)
class RiskWarning:
    code: str
    severity: str
    message: str
    ticker: str | None = None
    value: str | None = None
    limit: str | None = None


@dataclass(frozen=True)
class RiskAssessment:
    risk_level: str
    rules: dict[str, str]
    warnings: tuple[RiskWarning, ...]
    summary: str
    has_high_risk_warning: bool

    def as_dict(self) -> dict[str, object]:
        payload = asdict(self)
        payload["warnings"] = [asdict(item) for item in self.warnings]
        return payload


RISK_RULES_BY_LEVEL: dict[RiskLevel, RiskRuleConfig] = {
    RiskLevel.CONSERVATIVE: RiskRuleConfig(
        risk_level=RiskLevel.CONSERVATIVE,
        max_single_position_percent=Decimal("20"),
        max_cash_deployment_percent=Decimal("80"),
        min_cash_reserve_percent=Decimal("20"),
        max_unrealized_loss_percent=Decimal("8"),
        stop_loss_required_above_position_percent=Decimal("10"),
    ),
    RiskLevel.MODERATE: RiskRuleConfig(
        risk_level=RiskLevel.MODERATE,
        max_single_position_percent=Decimal("30"),
        max_cash_deployment_percent=Decimal("90"),
        min_cash_reserve_percent=Decimal("10"),
        max_unrealized_loss_percent=Decimal("15"),
        stop_loss_required_above_position_percent=Decimal("15"),
    ),
    RiskLevel.AGGRESSIVE: RiskRuleConfig(
        risk_level=RiskLevel.AGGRESSIVE,
        max_single_position_percent=Decimal("45"),
        max_cash_deployment_percent=Decimal("97"),
        min_cash_reserve_percent=Decimal("3"),
        max_unrealized_loss_percent=Decimal("25"),
        stop_loss_required_above_position_percent=Decimal("25"),
    ),
}


def assess_portfolio_risk(
    portfolio: Portfolio, snapshot: PortfolioSnapshot
) -> RiskAssessment:
    warnings: list[RiskWarning] = []

    if portfolio.risk_profile is None:
        level = RiskLevel.MODERATE
        warnings.append(
            RiskWarning(
                code="RISK_PROFILE_DEFAULTED",
                severity="medium",
                message="No saved risk profile found; moderate defaults were used.",
            )
        )
    else:
        level = portfolio.risk_profile.level

    rules = RISK_RULES_BY_LEVEL[level]

    if snapshot.price_completeness_status != "complete":
        warnings.append(
            RiskWarning(
                code="PRICE_DATA_INCOMPLETE",
                severity="medium",
                message=(
                    "Price data is incomplete; concentration, loss, and stop "
                    "protection checks may be partial."
                ),
            )
        )

    if snapshot.multi_currency_cash:
        warnings.append(
            RiskWarning(
                code="MULTI_CURRENCY_VALUATION_UNAVAILABLE",
                severity="medium",
                message=(
                    "Total valuation is unavailable because cash is held in "
                    "multiple currencies and FX conversion is not implemented."
                ),
            )
        )

    if snapshot.valuation_status == "missing_prices":
        warnings.append(
            RiskWarning(
                code="VALUATION_UNAVAILABLE_MISSING_PRICES",
                severity="medium",
                message=(
                    "Total valuation is unavailable because one or more holding "
                    "prices are missing."
                ),
            )
        )

    cash_pct = _to_decimal(snapshot.cash_allocation_percent)
    invested_pct = _to_decimal(snapshot.invested_allocation_percent)

    if cash_pct is not None and cash_pct < rules.min_cash_reserve_percent:
        warnings.append(
            RiskWarning(
                code="LOW_CASH_RESERVE",
                severity="high",
                message="Cash reserve is below the configured minimum.",
                value=f"{cash_pct:.2f}",
                limit=f"{rules.min_cash_reserve_percent:.2f}",
            )
        )

    if (
        invested_pct is not None
        and cash_pct is not None
        and invested_pct > rules.max_cash_deployment_percent
        and cash_pct < rules.min_cash_reserve_percent
    ):
        warnings.append(
            RiskWarning(
                code="HIGH_CASH_DEPLOYMENT",
                severity="high",
                message=(
                    "Invested allocation is above the configured deployment "
                    "limit while cash reserve is below the minimum."
                ),
                value=f"{invested_pct:.2f}",
                limit=f"{rules.max_cash_deployment_percent:.2f}",
            )
        )

    total_unrealized_pct = _to_decimal(snapshot.total_unrealized_gain_loss_percent)
    if (
        total_unrealized_pct is not None
        and total_unrealized_pct < -rules.max_unrealized_loss_percent
    ):
        warnings.append(
            RiskWarning(
                code="PORTFOLIO_UNREALIZED_LOSS_LIMIT",
                severity="high",
                message="Portfolio unrealized loss exceeds the configured threshold.",
                value=f"{total_unrealized_pct:.2f}",
                limit=f"-{rules.max_unrealized_loss_percent:.2f}",
            )
        )

    orders_by_ticker = {item.ticker.upper(): item for item in portfolio.active_orders}

    for holding in snapshot.holdings:
        alloc_total = _to_decimal(holding.allocation_in_total_percent)
        unrealized = _to_decimal(holding.unrealized_gain_loss)
        shares = _to_decimal(holding.share_count)
        avg_price = _to_decimal(holding.average_purchase_price)

        if alloc_total is not None and alloc_total > rules.max_single_position_percent:
            warnings.append(
                RiskWarning(
                    code="POSITION_CONCENTRATION_LIMIT",
                    severity="high",
                    message="Single-position allocation exceeds the configured maximum.",
                    ticker=holding.ticker,
                    value=f"{alloc_total:.2f}",
                    limit=f"{rules.max_single_position_percent:.2f}",
                )
            )

        cost_basis = (
            avg_price * shares if avg_price is not None and shares is not None else None
        )
        if (
            unrealized is not None
            and cost_basis is not None
            and cost_basis != Decimal("0")
        ):
            holding_loss_pct = (unrealized / cost_basis) * Decimal("100")
            if holding_loss_pct < -rules.max_unrealized_loss_percent:
                warnings.append(
                    RiskWarning(
                        code="HOLDING_UNREALIZED_LOSS_LIMIT",
                        severity="medium",
                        message="Holding unrealized loss exceeds the configured threshold.",
                        ticker=holding.ticker,
                        value=f"{holding_loss_pct:.2f}",
                        limit=f"-{rules.max_unrealized_loss_percent:.2f}",
                    )
                )

        if alloc_total is None:
            continue
        if alloc_total < rules.stop_loss_required_above_position_percent:
            continue

        if not holding.price_available or avg_price is None or shares is None:
            warnings.append(
                RiskWarning(
                    code="STOP_PROTECTION_UNEVALUATED",
                    severity="medium",
                    message=(
                        "Stop protection cannot be fully evaluated because "
                        "price data is missing."
                    ),
                    ticker=holding.ticker,
                )
            )
            continue

        order = orders_by_ticker.get(holding.ticker.upper())
        if order is None:
            warnings.append(
                RiskWarning(
                    code="STOP_PROTECTION_MISSING",
                    severity="high",
                    message=(
                        "Large holding has no active sell stop-loss or "
                        "sell stop-limit protection order."
                    ),
                    ticker=holding.ticker,
                )
            )
            continue

        if not (
            order.side == OrderSide.SELL
            and order.order_type in {OrderType.STOP_LOSS, OrderType.STOP_LIMIT}
        ):
            warnings.append(
                RiskWarning(
                    code="STOP_PROTECTION_INVALID_ORDER",
                    severity="medium",
                    message=(
                        "Active order exists but does not provide sell stop-loss "
                        "or stop-limit protection."
                    ),
                    ticker=holding.ticker,
                )
            )

    high_risk = any(item.severity == "high" for item in warnings)
    summary = (
        f"{len(warnings)} warning(s) using {level.value} risk rules."
        if warnings
        else f"No risk warnings using {level.value} risk rules."
    )
    return RiskAssessment(
        risk_level=level.value,
        rules={
            "max_single_position_percent": f"{rules.max_single_position_percent:.2f}",
            "max_cash_deployment_percent": f"{rules.max_cash_deployment_percent:.2f}",
            "min_cash_reserve_percent": f"{rules.min_cash_reserve_percent:.2f}",
            "max_unrealized_loss_percent": f"{rules.max_unrealized_loss_percent:.2f}",
            "stop_loss_required_above_position_percent": (
                f"{rules.stop_loss_required_above_position_percent:.2f}"
            ),
        },
        warnings=tuple(warnings),
        summary=summary,
        has_high_risk_warning=high_risk,
    )


def _to_decimal(value: str | None) -> Decimal | None:
    return Decimal(value) if value is not None else None
