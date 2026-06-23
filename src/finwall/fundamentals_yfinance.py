from __future__ import annotations

import queue
import threading
from collections.abc import Callable, Mapping
from math import isfinite
from numbers import Real
from typing import Any

from finwall.fundamentals import (
    CompanyProfile,
    FundamentalMetric,
    FundamentalSnapshot,
    _normalize_snapshot,
)

SOURCE = "yfinance"


def _safe_ticker(ticker: str) -> str:
    return ticker.strip().upper()


def _unavailable_metric(name: str, error: str | None = None) -> FundamentalMetric:
    return FundamentalMetric(
        name=name, value=None, available=False, source=SOURCE, error=error
    )


def _coerce_number(raw: Any) -> float | None:
    if raw is None or isinstance(raw, bool):
        return None
    parsed: float
    if isinstance(raw, Real):
        parsed = float(raw)
    elif isinstance(raw, str):
        value = raw.strip().replace(",", "")
        if not value or value.lower() in {"none", "nan", "n/a", "null"}:
            return None
        try:
            parsed = float(value)
        except ValueError:
            return None
    else:
        return None
    return parsed if isfinite(parsed) else None


def _format_decimal(raw: Any) -> str | None:
    value = _coerce_number(raw)
    if value is None:
        return None
    return f"{value:.2f}".rstrip("0").rstrip(".")


def _format_percent(raw: Any) -> str | None:
    value = _coerce_number(raw)
    if value is None:
        return None
    return f"{value * 100:.2f}%".replace(".00%", "%")


def _metric(
    info: Mapping[str, Any],
    name: str,
    key: str,
    percent: bool = False,
    scale: float = 1.0,
) -> FundamentalMetric:
    raw_value = info.get(key)
    if scale != 1.0:
        number = _coerce_number(raw_value)
        raw_value = None if number is None else number * scale
    formatter = _format_percent if percent else _format_decimal
    value = formatter(raw_value)
    if value is None:
        return _unavailable_metric(name, "metric unavailable")
    return FundamentalMetric(name=name, value=value, available=True, source=SOURCE)


class YFinanceFundamentalDataProvider:
    """Small, defensive fundamentals provider backed by yfinance ticker metadata."""

    def __init__(self, timeout_seconds: float = 5.0) -> None:
        self.timeout_seconds = timeout_seconds

    def get_fundamentals(self, ticker: str) -> FundamentalSnapshot:
        symbol = _safe_ticker(ticker)
        try:
            info = self._load_info(symbol)
        except ImportError:
            return self._missing_snapshot(symbol, "yfinance is not installed")
        except TimeoutError:
            return self._missing_snapshot(symbol, "provider request timed out")
        except Exception:
            return self._missing_snapshot(symbol, "provider request failed")

        if not info:
            return self._missing_snapshot(symbol, "ticker fundamentals unavailable")

        snapshot = FundamentalSnapshot(
            ticker=symbol,
            source=SOURCE,
            data_status="partial",
            profile=self._profile(symbol, info),
            revenue_growth=_metric(
                info, "revenue_growth", "revenueGrowth", percent=True
            ),
            earnings_growth=_metric(
                info, "earnings_growth", "earningsGrowth", percent=True
            ),
            profitability=(
                _metric(info, "gross_margin", "grossMargins", percent=True),
                _metric(info, "operating_margin", "operatingMargins", percent=True),
                _metric(info, "net_margin", "profitMargins", percent=True),
                _metric(info, "return_on_equity", "returnOnEquity", percent=True),
                _metric(info, "return_on_assets", "returnOnAssets", percent=True),
            ),
            debt=(
                _metric(info, "debt_to_equity", "debtToEquity", scale=0.01),
                _metric(info, "current_ratio", "currentRatio"),
            ),
            valuation=(
                _metric(info, "pe_ratio", "trailingPE"),
                _metric(info, "forward_pe", "forwardPE"),
                _metric(info, "price_to_sales", "priceToSalesTrailing12Months"),
                _metric(info, "price_to_book", "priceToBook"),
            ),
            warnings=(),
        )
        return _normalize_snapshot(snapshot)

    def _load_info(self, ticker: str) -> Mapping[str, Any]:
        import yfinance as yf

        yfinance_ticker = yf.Ticker(ticker)
        raw_info = _get_ticker_info(yfinance_ticker, self.timeout_seconds)
        return raw_info if isinstance(raw_info, Mapping) else {}

    def _profile(self, ticker: str, info: Mapping[str, Any]) -> CompanyProfile:
        company_name = self._optional_string(info, "longName") or self._optional_string(
            info, "shortName"
        )
        profile = CompanyProfile(
            ticker=ticker,
            company_name=company_name,
            sector=self._optional_string(info, "sector"),
            industry=self._optional_string(info, "industry"),
            country=self._optional_string(info, "country"),
            website=self._optional_string(info, "website"),
            source=SOURCE,
            available=company_name is not None,
        )
        return profile

    @staticmethod
    def _optional_string(info: Mapping[str, Any], key: str) -> str | None:
        value = info.get(key)
        if not isinstance(value, str):
            return None
        stripped = value.strip()
        return stripped or None

    @staticmethod
    def _missing_snapshot(ticker: str, error: str) -> FundamentalSnapshot:
        snapshot = FundamentalSnapshot(
            ticker=ticker,
            source=SOURCE,
            data_status="missing_data",
            profile=CompanyProfile(
                ticker, None, None, None, None, None, SOURCE, False, error
            ),
            revenue_growth=_unavailable_metric("revenue_growth", error),
            earnings_growth=_unavailable_metric("earnings_growth", error),
            profitability=(),
            debt=(),
            valuation=(),
            warnings=(error,),
        )
        return _normalize_snapshot(snapshot)


def _get_ticker_info(ticker_data: object, timeout_seconds: float) -> object:
    def fetch() -> object:
        get_info = getattr(ticker_data, "get_info", None)
        if callable(get_info):
            return get_info()
        return getattr(ticker_data, "info", {})

    return _call_with_timeout(fetch, timeout_seconds)


def _call_with_timeout(
    callback: Callable[[], object], timeout_seconds: float
) -> object:
    result_queue: queue.Queue[tuple[bool, object]] = queue.Queue(maxsize=1)

    def target() -> None:
        try:
            result_queue.put((True, callback()))
        except Exception as exc:
            result_queue.put((False, exc))

    worker = threading.Thread(target=target, daemon=True)
    worker.start()
    try:
        success, value = result_queue.get(timeout=timeout_seconds)
    except queue.Empty as exc:
        raise TimeoutError("yfinance fundamentals request timed out") from exc
    if success:
        return value
    if isinstance(value, Exception):
        raise value
    raise RuntimeError("yfinance fundamentals request failed")
