from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from enum import StrEnum


class TradingDayStatus(StrEnum):
    TRADING_DAY = "trading_day"
    WEEKEND = "weekend"
    MARKET_HOLIDAY = "market_holiday"


@dataclass(frozen=True)
class TradingDayDecision:
    calendar_date: str
    status: TradingDayStatus
    is_trading_day: bool
    reason: str
    holiday_name: str | None = None

    def as_dict(self) -> dict[str, object]:
        return {
            "calendar_date": self.calendar_date,
            "status": self.status.value,
            "is_trading_day": self.is_trading_day,
            "reason": self.reason,
            "holiday_name": self.holiday_name,
        }


def _nth_weekday(year: int, month: int, weekday: int, n: int) -> date:
    d = date(year, month, 1)
    while d.weekday() != weekday:
        d += timedelta(days=1)
    return d + timedelta(days=7 * (n - 1))


def _last_weekday(year: int, month: int, weekday: int) -> date:
    if month == 12:
        d = date(year + 1, 1, 1) - timedelta(days=1)
    else:
        d = date(year, month + 1, 1) - timedelta(days=1)
    while d.weekday() != weekday:
        d -= timedelta(days=1)
    return d


def _observed_fixed_holiday(year: int, month: int, day: int) -> date:
    holiday = date(year, month, day)
    if holiday.weekday() == 5:
        return holiday - timedelta(days=1)
    if holiday.weekday() == 6:
        return holiday + timedelta(days=1)
    return holiday


def _easter_sunday(year: int) -> date:
    a = year % 19
    b = year // 100
    c = year % 100
    d = b // 4
    e = b % 4
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i = c // 4
    k = c % 4
    leap = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * leap) // 451
    month = (h + leap - 7 * m + 114) // 31
    day = ((h + leap - 7 * m + 114) % 31) + 1
    return date(year, month, day)


def _us_market_holidays(year: int) -> dict[date, str]:
    easter = _easter_sunday(year)
    return {
        _observed_fixed_holiday(year, 1, 1): "New Year's Day",
        _nth_weekday(year, 1, 0, 3): "Martin Luther King Jr. Day",
        _nth_weekday(year, 2, 0, 3): "Presidents' Day",
        easter - timedelta(days=2): "Good Friday",
        _last_weekday(year, 5, 0): "Memorial Day",
        _observed_fixed_holiday(year, 6, 19): "Juneteenth",
        _observed_fixed_holiday(year, 7, 4): "Independence Day",
        _nth_weekday(year, 9, 0, 1): "Labor Day",
        _nth_weekday(year, 11, 3, 4): "Thanksgiving Day",
        _observed_fixed_holiday(year, 12, 25): "Christmas Day",
    }


def evaluate_us_trading_day(day: date) -> TradingDayDecision:
    if day.weekday() >= 5:
        return TradingDayDecision(
            calendar_date=day.isoformat(),
            status=TradingDayStatus.WEEKEND,
            is_trading_day=False,
            reason="Weekend; US equity markets are closed.",
        )

    holidays = _us_market_holidays(day.year)
    holiday_name = holidays.get(day)
    if holiday_name:
        return TradingDayDecision(
            calendar_date=day.isoformat(),
            status=TradingDayStatus.MARKET_HOLIDAY,
            is_trading_day=False,
            reason="US equity market holiday.",
            holiday_name=holiday_name,
        )

    return TradingDayDecision(
        calendar_date=day.isoformat(),
        status=TradingDayStatus.TRADING_DAY,
        is_trading_day=True,
        reason="Trading day based on deterministic local US market calendar rules.",
    )
