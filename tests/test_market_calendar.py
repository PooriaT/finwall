from datetime import date

from finwall.market_calendar import TradingDayStatus, evaluate_us_trading_day


def test_weekday_trading_day() -> None:
    decision = evaluate_us_trading_day(date(2026, 5, 20))
    assert decision.status == TradingDayStatus.TRADING_DAY


def test_saturday_weekend() -> None:
    assert evaluate_us_trading_day(date(2026, 5, 23)).status == TradingDayStatus.WEEKEND


def test_sunday_weekend() -> None:
    assert evaluate_us_trading_day(date(2026, 5, 24)).status == TradingDayStatus.WEEKEND


def test_observed_market_holiday() -> None:
    decision = evaluate_us_trading_day(date(2026, 7, 3))
    assert decision.status == TradingDayStatus.MARKET_HOLIDAY


def test_good_friday_holiday() -> None:
    decision = evaluate_us_trading_day(date(2026, 4, 3))
    assert decision.status == TradingDayStatus.MARKET_HOLIDAY
    assert decision.holiday_name == "Good Friday"


def test_prior_year_observed_new_year_holiday() -> None:
    decision = evaluate_us_trading_day(date(2021, 12, 31))
    assert decision.status == TradingDayStatus.MARKET_HOLIDAY
    assert decision.holiday_name == "New Year's Day"
