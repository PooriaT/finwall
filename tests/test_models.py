from datetime import date
from decimal import Decimal

import pytest

from finwall.models import (
    ActiveOrder,
    Holding,
    OrderSide,
    OrderType,
    Portfolio,
    RiskLevel,
    RiskProfile,
    Timeline,
)


def test_holding_requires_positive_share_count() -> None:
    with pytest.raises(ValueError):
        Holding(
            ticker="AAPL",
            share_count=Decimal("0"),
            average_purchase_price=Decimal("100"),
        )


def test_holding_accepts_optional_sector() -> None:
    holding = Holding(
        ticker="MSFT",
        share_count=Decimal("10"),
        average_purchase_price=Decimal("250"),
        sector="Technology",
    )

    assert holding.sector == "Technology"


def test_limit_order_requires_limit_price() -> None:
    with pytest.raises(ValueError):
        ActiveOrder(
            ticker="NVDA",
            side=OrderSide.BUY,
            order_type=OrderType.LIMIT,
            share_count=Decimal("5"),
        )


def test_stop_loss_order_requires_stop_price() -> None:
    with pytest.raises(ValueError):
        ActiveOrder(
            ticker="TSLA",
            side=OrderSide.SELL,
            order_type=OrderType.STOP_LOSS,
            share_count=Decimal("3"),
        )


def test_stop_limit_order_requires_both_prices() -> None:
    with pytest.raises(ValueError):
        ActiveOrder(
            ticker="META",
            side=OrderSide.SELL,
            order_type=OrderType.STOP_LIMIT,
            share_count=Decimal("2"),
            stop_price=Decimal("500"),
        )


def test_active_order_rejects_unknown_order_type() -> None:
    with pytest.raises(ValueError):
        ActiveOrder(
            ticker="AMD",
            side=OrderSide.BUY,
            order_type="market",
            share_count=Decimal("1"),
        )


def test_risk_profile_supports_defined_levels() -> None:
    profile = RiskProfile(level=RiskLevel.MODERATE)

    assert profile.level == RiskLevel.MODERATE


def test_timeline_rejects_invalid_target_date() -> None:
    with pytest.raises(ValueError):
        Timeline(
            start_date=date(2026, 1, 10),
            target_date=date(2026, 1, 1),
        )


def test_portfolio_collections_are_immutable_snapshots() -> None:
    holdings = [
        Holding(
            ticker="AAPL",
            share_count=Decimal("2"),
            average_purchase_price=Decimal("180"),
        )
    ]

    portfolio = Portfolio(name="Core", holdings=holdings)

    holdings.append(
        Holding(
            ticker="MSFT",
            share_count=Decimal("1"),
            average_purchase_price=Decimal("400"),
        )
    )

    assert len(portfolio.holdings) == 1
    assert isinstance(portfolio.holdings, tuple)
