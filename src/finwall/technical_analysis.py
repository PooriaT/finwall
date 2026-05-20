from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from decimal import ROUND_HALF_UP, Decimal

from finwall.market_data import HistoricalPriceBar, MarketDataProvider
from finwall.models import Portfolio


@dataclass(frozen=True)
class MovingAverageSet:
    sma_20: str | None
    sma_50: str | None
    sma_200: str | None


@dataclass(frozen=True)
class VolumeTrend:
    status: str
    recent_average_volume: str | None
    previous_average_volume: str | None
    message: str | None


@dataclass(frozen=True)
class MacdSnapshot:
    macd: str | None
    signal: str | None
    histogram: str | None
    available: bool


@dataclass(frozen=True)
class TechnicalIndicatorSnapshot:
    ticker: str
    source: str
    data_status: str
    latest_close: str | None
    moving_averages: MovingAverageSet
    rsi_14: str | None
    recent_high: str | None
    recent_low: str | None
    volume_trend: VolumeTrend
    macd: MacdSnapshot | None
    warnings: tuple[str, ...]


@dataclass(frozen=True)
class TechnicalAnalysisReport:
    holdings: tuple[TechnicalIndicatorSnapshot, ...]
    watchlist: tuple[TechnicalIndicatorSnapshot, ...]
    summary: str
    limitations: tuple[str, ...]

    def as_dict(self) -> dict[str, object]:
        return asdict(self)

    def to_json(self) -> str:
        return json.dumps(self.as_dict(), indent=2)


def _fmt(value: Decimal | None) -> str | None:
    if value is None:
        return None
    return str(value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


def _sorted_valid_closes(bars: tuple[HistoricalPriceBar, ...]) -> list[Decimal]:
    ordered = sorted(bars, key=lambda bar: bar.date)
    return [bar.close for bar in ordered if bar.close is not None]


def _sma(closes: list[Decimal], length: int) -> str | None:
    if len(closes) < length:
        return None
    return _fmt(sum(closes[-length:]) / Decimal(length))


def _rsi_14(closes: list[Decimal]) -> str | None:
    if len(closes) < 15:
        return None
    changes = [closes[idx] - closes[idx - 1] for idx in range(1, len(closes))]
    gains = [max(change, Decimal("0")) for change in changes]
    losses = [abs(min(change, Decimal("0"))) for change in changes]
    avg_gain = sum(gains[-14:]) / Decimal("14")
    avg_loss = sum(losses[-14:]) / Decimal("14")
    if avg_loss == Decimal("0"):
        return "100.00"
    rs = avg_gain / avg_loss
    rsi = Decimal("100") - (Decimal("100") / (Decimal("1") + rs))
    return _fmt(rsi)


def _volume_trend(bars: tuple[HistoricalPriceBar, ...]) -> VolumeTrend:
    ordered = sorted(bars, key=lambda bar: bar.date)
    volumes = [bar.volume for bar in ordered if bar.volume is not None]
    if len(volumes) < 20:
        return VolumeTrend("unavailable", None, None, "insufficient volume history")
    recent = volumes[-10:]
    previous = volumes[-20:-10]
    recent_avg = Decimal(sum(recent)) / Decimal(len(recent))
    previous_avg = Decimal(sum(previous)) / Decimal(len(previous))
    if previous_avg == Decimal("0"):
        status = "flat"
        message = "previous average volume is zero"
    elif recent_avg > previous_avg:
        status = "increasing"
        message = "recent average volume is above previous average"
    elif recent_avg < previous_avg:
        status = "decreasing"
        message = "recent average volume is below previous average"
    else:
        status = "flat"
        message = "recent average volume matches previous average"
    return VolumeTrend(status, _fmt(recent_avg), _fmt(previous_avg), message)


def build_technical_indicator_snapshot(
    ticker: str,
    bars: tuple[HistoricalPriceBar, ...],
) -> TechnicalIndicatorSnapshot:
    if not bars:
        return TechnicalIndicatorSnapshot(
            ticker=ticker,
            source="unavailable",
            data_status="missing_data",
            latest_close=None,
            moving_averages=MovingAverageSet(None, None, None),
            rsi_14=None,
            recent_high=None,
            recent_low=None,
            volume_trend=VolumeTrend("unavailable", None, None, "no historical data"),
            macd=None,
            warnings=("historical price data unavailable",),
        )

    closes = _sorted_valid_closes(bars)
    warnings: list[str] = []
    if not closes:
        return TechnicalIndicatorSnapshot(
            ticker=ticker,
            source=bars[0].source,
            data_status="missing_data",
            latest_close=None,
            moving_averages=MovingAverageSet(None, None, None),
            rsi_14=None,
            recent_high=None,
            recent_low=None,
            volume_trend=_volume_trend(bars),
            macd=None,
            warnings=("historical bars are missing close prices",),
        )

    data_status = "complete"
    if len(closes) < 200:
        data_status = "insufficient_data"
        warnings.append("fewer than 200 close prices available")

    moving = MovingAverageSet(_sma(closes, 20), _sma(closes, 50), _sma(closes, 200))
    rsi_14 = _rsi_14(closes)
    if rsi_14 is None:
        warnings.append("insufficient data for RSI 14")
    if moving.sma_20 is None or moving.sma_50 is None or moving.sma_200 is None:
        data_status = "partial" if len(closes) >= 20 else "insufficient_data"

    return TechnicalIndicatorSnapshot(
        ticker=ticker,
        source=bars[0].source,
        data_status=data_status,
        latest_close=_fmt(closes[-1]),
        moving_averages=moving,
        rsi_14=rsi_14,
        recent_high=_fmt(max(closes)),
        recent_low=_fmt(min(closes)),
        volume_trend=_volume_trend(bars),
        macd=None,
        warnings=tuple(warnings),
    )


def build_technical_analysis_report(
    portfolio: Portfolio,
    provider: MarketDataProvider,
    days: int = 250,
) -> TechnicalAnalysisReport:
    holding_tickers = tuple(
        sorted({item.ticker.upper() for item in portfolio.holdings})
    )
    watchlist_tickers = tuple(
        sorted({item.ticker.upper() for item in portfolio.watchlist})
    )
    all_tickers = tuple(sorted(set(holding_tickers) | set(watchlist_tickers)))

    snapshots = {
        ticker: build_technical_indicator_snapshot(
            ticker,
            provider.get_historical_prices(ticker, days),
        )
        for ticker in all_tickers
    }

    holdings = tuple(snapshots[ticker] for ticker in holding_tickers)
    watchlist = tuple(snapshots[ticker] for ticker in watchlist_tickers)
    limitations = (
        "Technical indicators are deterministic calculations from historical prices only.",
        "Indicators are decision-support inputs and not recommendations.",
    )
    return TechnicalAnalysisReport(
        holdings=holdings,
        watchlist=watchlist,
        summary=(
            f"Generated technical indicator snapshots for {len(holdings)} holdings "
            f"and {len(watchlist)} watchlist tickers."
        ),
        limitations=limitations,
    )
