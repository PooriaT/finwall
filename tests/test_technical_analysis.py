from datetime import date, timedelta
from decimal import Decimal

from finwall.market_data import HistoricalPriceBar, StaticMarketDataProvider
from finwall.models import Holding, Portfolio, WatchlistItem
from finwall.technical_analysis import (
    build_technical_analysis_report,
    build_technical_indicator_snapshot,
)


def make_bars(
    ticker: str, count: int, base: Decimal = Decimal("100")
) -> tuple[HistoricalPriceBar, ...]:
    start = date(2025, 1, 1)
    bars = []
    for idx in range(count):
        bars.append(
            HistoricalPriceBar(
                ticker=ticker,
                date=(start + timedelta(days=idx)).isoformat(),
                close=base + Decimal(idx),
                volume=1000 + idx,
                source="static",
            )
        )
    return tuple(bars)


def test_indicator_snapshot_calculates_sma_rsi_high_low_volume() -> None:
    snap = build_technical_indicator_snapshot("NVDA", make_bars("NVDA", 220))
    assert snap.moving_averages.sma_20 is not None
    assert snap.moving_averages.sma_50 is not None
    assert snap.moving_averages.sma_200 is not None
    assert snap.rsi_14 is not None
    assert snap.recent_high == "319.00"
    assert snap.recent_low == "100.00"
    assert snap.volume_trend.status in {"increasing", "decreasing", "flat"}


def test_rsi_insufficient_data() -> None:
    snap = build_technical_indicator_snapshot("NVDA", make_bars("NVDA", 10))
    assert snap.rsi_14 is None
    assert "insufficient data for RSI 14" in snap.warnings


def test_sorted_by_date_before_calculation() -> None:
    bars = list(make_bars("NVDA", 20))
    bars.reverse()
    snap = build_technical_indicator_snapshot("NVDA", tuple(bars))
    assert snap.latest_close == "119.00"


def test_missing_historical_data_warning() -> None:
    snap = build_technical_indicator_snapshot("NVDA", ())
    assert snap.data_status == "missing_data"
    assert snap.warnings


def test_report_holdings_watchlist_and_dedup() -> None:
    portfolio = Portfolio(
        name="Primary",
        holdings=(Holding("NVDA", Decimal("1"), Decimal("100")),),
        watchlist=(WatchlistItem("NVDA"), WatchlistItem("MSFT")),
    )
    provider = StaticMarketDataProvider(
        historical_prices={
            "NVDA": make_bars("NVDA", 220),
            "MSFT": make_bars("MSFT", 50),
        }
    )
    report = build_technical_analysis_report(portfolio, provider)
    assert len(report.holdings) == 1
    assert len(report.watchlist) == 2
    assert report.holdings[0].ticker == "NVDA"


def test_report_empty_portfolio_and_json() -> None:
    report = build_technical_analysis_report(
        Portfolio(name="Primary"), StaticMarketDataProvider()
    )
    assert report.holdings == ()
    assert report.watchlist == ()
    assert '"holdings": []' in report.to_json()
