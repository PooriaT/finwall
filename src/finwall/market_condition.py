from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from decimal import ROUND_HALF_UP, Decimal
from enum import StrEnum

from finwall.market_data import INDEX_SYMBOL_MAP, HistoricalPriceBar, MarketDataProvider
from finwall.technical_analysis import build_technical_indicator_snapshot

VOLATILITY_RISK_THRESHOLD = Decimal("3.00")


class MarketConditionStatus(StrEnum):
    FAVORABLE = "favorable"
    NEUTRAL = "neutral"
    RISKY = "risky"
    INSUFFICIENT_DATA = "insufficient_data"


@dataclass(frozen=True)
class IndexTrendSnapshot:
    symbol: str
    provider_symbol: str
    source: str
    data_status: str
    latest_close: str | None
    sma_20: str | None
    sma_50: str | None
    sma_200: str | None
    rsi_14: str | None
    recent_high: str | None
    recent_low: str | None
    above_sma_20: bool | None
    above_sma_50: bool | None
    above_sma_200: bool | None
    trend_status: str
    volatility_proxy: str | None
    warnings: tuple[str, ...]


@dataclass(frozen=True)
class MarketConditionReport:
    status: MarketConditionStatus
    primary_index: IndexTrendSnapshot | None
    secondary_indexes: tuple[IndexTrendSnapshot, ...]
    summary: str
    reasoning_inputs: tuple[str, ...]
    warnings: tuple[str, ...]
    limitations: tuple[str, ...]

    def as_dict(self) -> dict[str, object]:
        return asdict(self)

    def to_json(self) -> str:
        return json.dumps(self.as_dict(), indent=2)


def _to_decimal(value: str | None) -> Decimal | None:
    return Decimal(value) if value is not None else None


def _fmt_pct(value: Decimal) -> str:
    return f"{value.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)}%"


def _avg_abs_daily_return(closes: list[Decimal]) -> Decimal | None:
    if len(closes) < 21:
        return None
    changes = []
    for i in range(len(closes) - 20, len(closes)):
        prev = closes[i - 1]
        curr = closes[i]
        if prev == Decimal("0"):
            continue
        changes.append(abs((curr - prev) / prev * Decimal("100")))
    if not changes:
        return None
    return sum(changes) / Decimal(len(changes))


def _build_index_snapshot(
    symbol: str, provider_symbol: str, bars: tuple[HistoricalPriceBar, ...]
) -> IndexTrendSnapshot:
    technical = build_technical_indicator_snapshot(symbol, bars)
    warnings = list(technical.warnings)
    closes = [
        bar.close for bar in sorted(bars, key=lambda b: b.date) if bar.close is not None
    ]

    vol = _avg_abs_daily_return(closes)
    volatility_proxy = _fmt_pct(vol) if vol is not None else None
    if vol is not None and vol >= VOLATILITY_RISK_THRESHOLD:
        warnings.append(
            "volatility proxy elevated: average absolute daily move is "
            f"{volatility_proxy} (>= {VOLATILITY_RISK_THRESHOLD}%)"
        )

    latest = _to_decimal(technical.latest_close)
    sma20 = _to_decimal(technical.moving_averages.sma_20)
    sma50 = _to_decimal(technical.moving_averages.sma_50)
    sma200 = _to_decimal(technical.moving_averages.sma_200)

    trend_status = "mixed"
    if latest is None or sma50 is None or sma200 is None:
        trend_status = "insufficient_data"
    elif latest < sma200 or sma50 < sma200:
        trend_status = "risky"
    elif latest > sma50 and latest > sma200 and sma50 >= sma200:
        trend_status = "favorable"

    return IndexTrendSnapshot(
        symbol=symbol,
        provider_symbol=provider_symbol,
        source=technical.source,
        data_status=technical.data_status,
        latest_close=technical.latest_close,
        sma_20=technical.moving_averages.sma_20,
        sma_50=technical.moving_averages.sma_50,
        sma_200=technical.moving_averages.sma_200,
        rsi_14=technical.rsi_14,
        recent_high=technical.recent_high,
        recent_low=technical.recent_low,
        above_sma_20=(latest > sma20)
        if latest is not None and sma20 is not None
        else None,
        above_sma_50=(latest > sma50)
        if latest is not None and sma50 is not None
        else None,
        above_sma_200=(latest > sma200)
        if latest is not None and sma200 is not None
        else None,
        trend_status=trend_status,
        volatility_proxy=volatility_proxy,
        warnings=tuple(warnings),
    )


def _fetch_snapshot(
    provider: MarketDataProvider, symbol: str, days: int
) -> IndexTrendSnapshot:
    provider_symbol = INDEX_SYMBOL_MAP.get(symbol.upper(), symbol)
    bars = provider.get_historical_prices(provider_symbol, days)
    return _build_index_snapshot(symbol.upper(), provider_symbol, bars)


def classify_market_condition(
    provider: MarketDataProvider,
    primary_symbol: str = "SP500",
    include_nasdaq: bool = False,
    days: int = 250,
) -> MarketConditionReport:
    primary = _fetch_snapshot(provider, primary_symbol, days)
    secondary: tuple[IndexTrendSnapshot, ...] = ()
    if include_nasdaq and primary_symbol.upper() != "NASDAQ":
        secondary = (_fetch_snapshot(provider, "NASDAQ", days),)

    warnings = list(primary.warnings)
    for snapshot in secondary:
        warnings.extend(snapshot.warnings)

    reasons = [
        f"primary_symbol={primary.symbol}",
        f"primary_trend_status={primary.trend_status}",
        f"primary_above_sma50={primary.above_sma_50}",
        f"primary_above_sma200={primary.above_sma_200}",
    ]

    if (
        primary.latest_close is None
        or primary.sma_50 is None
        or primary.sma_200 is None
    ):
        status = MarketConditionStatus.INSUFFICIENT_DATA
        summary = (
            "Insufficient primary index history for deterministic trend classification."
        )
    else:
        primary_latest = Decimal(primary.latest_close)
        primary_sma50 = Decimal(primary.sma_50)
        primary_sma200 = Decimal(primary.sma_200)
        primary_risky = (
            primary_latest < primary_sma200 or primary_sma50 < primary_sma200
        )
        volatility_risk = any(
            "volatility proxy elevated" in w for w in primary.warnings
        )
        nasdaq_risky = any(item.trend_status == "risky" for item in secondary)

        if (
            primary_risky
            or volatility_risk
            or (primary_latest < primary_sma50 and nasdaq_risky)
        ):
            status = MarketConditionStatus.RISKY
            summary = (
                "Risk signals are active in broad index trend and/or recent volatility."
            )
        elif (
            primary_latest > primary_sma50
            and primary_latest > primary_sma200
            and primary_sma50 >= primary_sma200
            and not volatility_risk
            and not nasdaq_risky
        ):
            status = MarketConditionStatus.FAVORABLE
            summary = (
                "Primary index trend is favorable with sufficient history "
                "and no severe risk warning."
            )
        else:
            status = MarketConditionStatus.NEUTRAL
            summary = "Market signals are mixed across trend and confirmation inputs."

    if secondary:
        reasons.append(
            f"secondary_trend_statuses={[item.trend_status for item in secondary]}"
        )
    limitations = (
        "Deterministic trend classification from historical index prices only.",
        "Decision-support output only, not financial advice or guaranteed outcomes.",
    )
    return MarketConditionReport(
        status=status,
        primary_index=primary,
        secondary_indexes=secondary,
        summary=summary,
        reasoning_inputs=tuple(reasons),
        warnings=tuple(dict.fromkeys(warnings)),
        limitations=limitations,
    )
