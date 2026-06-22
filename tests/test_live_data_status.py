from finwall.fundamentals import FundamentalAnalysisReport, unavailable_snapshot
from finwall.live_data_status import (
    LiveDataAvailability,
    LiveDataDomain,
    diagnostics_status,
    fundamentals_status,
    market_price_status_from_snapshot,
    news_status,
)
from finwall.market_data_diagnostics import (
    MarketDataDiagnosticCheck,
    MarketDataDiagnosticResult,
)
from finwall.news import NewsReport
from finwall.snapshot import HoldingSnapshot, PortfolioSnapshot


def _snapshot(price_available=True):
    return PortfolioSnapshot(
        holdings=(
            HoldingSnapshot(
                ticker="AAPL",
                share_count="1",
                average_purchase_price="100",
                current_price="150" if price_available else None,
                estimated_value="150" if price_available else None,
                unrealized_gain_loss="50" if price_available else None,
                price_available=price_available,
                price_status="available" if price_available else "missing",
                missing_price_message=None if price_available else "AAPL: unavailable",
                allocation_in_total_percent="100" if price_available else None,
                allocation_in_invested_percent="100" if price_available else None,
            ),
        ),
        cash_balances={},
        active_orders=(),
        cash_balance="0",
        invested_value="150" if price_available else "0",
        total_portfolio_value="150" if price_available else None,
        cash_allocation_percent="0" if price_available else None,
        invested_allocation_percent="100" if price_available else None,
        valuation_status="complete" if price_available else "unavailable",
        price_completeness_status="complete" if price_available else "none",
        total_unrealized_gain_loss="50" if price_available else None,
        total_unrealized_gain_loss_percent="50" if price_available else None,
        multi_currency_cash=False,
        valuation_currency="USD",
    )


def test_live_data_status_serialization_is_json_safe_and_deterministic():
    status = market_price_status_from_snapshot(
        snapshot=_snapshot(),
        provider="yfinance",
        source="fallback:yfinance->static",
        warnings=(
            "market data fallback used: primary yfinance unavailable; "
            "fallback static succeeded",
        ),
        fallback_provider="static",
        last_attempted_at="2026-01-01T00:00:00+00:00",
    )

    assert status.as_dict() == {
        "domain": "market_prices",
        "provider": "yfinance",
        "source": "fallback:yfinance->static",
        "availability": "live",
        "last_attempted_at": "2026-01-01T00:00:00+00:00",
        "fallback_used": True,
        "fallback_provider": "static",
        "warnings": [
            "market data fallback used: primary yfinance unavailable; fallback static succeeded"
        ],
        "safe_error_messages": [],
        "metadata": {
            "price_completeness_status": "complete",
            "priced_holdings": 1,
            "total_holdings": 1,
            "valuation_status": "complete",
        },
    }


def test_market_price_status_unavailable_static_and_manual():
    unavailable = market_price_status_from_snapshot(
        snapshot=_snapshot(False), provider="yfinance", source="yfinance"
    )
    static = market_price_status_from_snapshot(
        snapshot=_snapshot(), provider="static", source="static"
    )
    manual = market_price_status_from_snapshot(
        snapshot=_snapshot(), provider="manual", source="manual"
    )

    assert unavailable.availability == LiveDataAvailability.UNAVAILABLE
    assert static.availability == LiveDataAvailability.STATIC
    assert manual.availability == LiveDataAvailability.MANUAL


def test_fundamentals_and_news_missing_reports_are_unavailable():
    fundamentals = FundamentalAnalysisReport(
        holdings=(unavailable_snapshot("AAPL"),),
        watchlist=(),
        summary="missing",
        limitations=("static fallback only",),
    )
    news = NewsReport((), (), (), (), "missing", (), ("provider unavailable",))

    assert fundamentals_status(fundamentals).domain == LiveDataDomain.FUNDAMENTALS
    assert fundamentals_status(fundamentals).availability == "static"
    assert news_status(news).availability == "unknown"


def test_diagnostics_status_marks_fallback_used_only_when_attempted():
    configured_only = MarketDataDiagnosticResult(
        ok=True,
        provider="yfinance",
        effective_provider="yfinance",
        timeout_seconds=1.0,
        sample_ticker="AAPL",
        historical_days=5,
        primary_provider="yfinance",
        fallback_provider="yahoo",
        checks=(
            MarketDataDiagnosticCheck(
                "latest_quote", True, "ok", {"fallback": {"fallback_attempted": False}}
            ),
            MarketDataDiagnosticCheck(
                "historical_prices",
                True,
                "ok",
                {"fallback": {"fallback_attempted": False}},
            ),
        ),
    )
    attempted = MarketDataDiagnosticResult(
        ok=True,
        provider="yfinance",
        effective_provider="yfinance",
        timeout_seconds=1.0,
        sample_ticker="AAPL",
        historical_days=5,
        primary_provider="yfinance",
        fallback_provider="yahoo",
        checks=(
            MarketDataDiagnosticCheck(
                "latest_quote", True, "ok", {"fallback": {"fallback_attempted": True}}
            ),
        ),
    )

    assert diagnostics_status(configured_only).fallback_used is False
    assert diagnostics_status(attempted).fallback_used is True
