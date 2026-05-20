from decimal import Decimal

from finwall.fundamentals import (
    CompanyProfile,
    FundamentalMetric,
    FundamentalSnapshot,
    StaticFundamentalDataProvider,
    build_fundamental_analysis_report,
)
from finwall.models import Holding, Portfolio, WatchlistItem


def make_snapshot(ticker: str) -> FundamentalSnapshot:
    return FundamentalSnapshot(
        ticker=ticker,
        source="static",
        data_status="available",
        profile=CompanyProfile(
            ticker, f"{ticker} Inc", "Tech", "Software", None, None, "static", True
        ),
        revenue_growth=FundamentalMetric("revenue_growth", "12%", True, "static"),
        earnings_growth=FundamentalMetric("earnings_growth", "10%", True, "static"),
        profitability=(FundamentalMetric("net_margin", "20%", True, "static"),),
        debt=(FundamentalMetric("debt_to_equity", "0.4", True, "static"),),
        valuation=(FundamentalMetric("pe_ratio", "25", True, "static"),),
        warnings=(),
    )


def test_static_provider_configured_and_unknown() -> None:
    provider = StaticFundamentalDataProvider({"NVDA": make_snapshot("NVDA")})
    assert provider.get_fundamentals("NVDA").ticker == "NVDA"
    assert provider.get_fundamentals("UNKNOWN").data_status == "missing_data"


def test_report_includes_holdings_watchlist_and_deduped_fetch() -> None:
    class CountingProvider:
        def __init__(self):
            self.calls = []

        def get_fundamentals(self, ticker: str):
            self.calls.append(ticker)
            return make_snapshot(ticker)

    portfolio = Portfolio(
        name="P",
        holdings=(Holding("NVDA", Decimal("1"), Decimal("100")),),
        watchlist=(WatchlistItem("NVDA"), WatchlistItem("AAPL")),
    )
    provider = CountingProvider()
    report = build_fundamental_analysis_report(portfolio, provider)
    assert [x.ticker for x in report.holdings] == ["NVDA"]
    assert [x.ticker for x in report.watchlist] == ["NVDA", "AAPL"]
    assert provider.calls == ["NVDA", "AAPL"]


def test_missing_data_warnings_and_empty_portfolio_and_json() -> None:
    portfolio = Portfolio(name="P")
    report = build_fundamental_analysis_report(
        portfolio, StaticFundamentalDataProvider()
    )
    assert report.holdings == ()
    assert report.watchlist == ()
    assert "Fundamental snapshots" in report.summary
    assert '"holdings": []' in report.to_json()

    partial = FundamentalSnapshot(
        ticker="X",
        source="static",
        data_status="available",
        profile=CompanyProfile("X", None, None, None, None, None, "static", False),
        revenue_growth=FundamentalMetric("revenue_growth", None, False, "static"),
        earnings_growth=FundamentalMetric("earnings_growth", "5%", True, "static"),
        profitability=(),
        debt=(),
        valuation=(),
        warnings=(),
    )
    report2 = build_fundamental_analysis_report(
        Portfolio(name="P", holdings=(Holding("X", Decimal("1"), Decimal("1")),)),
        StaticFundamentalDataProvider({"X": partial}),
    )
    warnings = report2.holdings[0].warnings
    assert "company profile unavailable" in warnings
    assert "revenue growth unavailable" in warnings
    assert "profitability metrics unavailable" in warnings
    assert "debt metrics unavailable" in warnings
    assert "valuation metrics unavailable" in warnings


def test_section_availability_uses_metric_flags_not_tuple_presence() -> None:
    snapshot = FundamentalSnapshot(
        ticker="X",
        source="static",
        data_status="available",
        profile=CompanyProfile("X", "X Inc", None, None, None, None, "static", True),
        revenue_growth=FundamentalMetric("revenue_growth", "10%", True, "static"),
        earnings_growth=FundamentalMetric("earnings_growth", "8%", True, "static"),
        profitability=(FundamentalMetric("net_margin", None, False, "static"),),
        debt=(FundamentalMetric("debt_to_equity", None, False, "static"),),
        valuation=(FundamentalMetric("pe_ratio", None, False, "static"),),
        warnings=(),
    )

    report = build_fundamental_analysis_report(
        Portfolio(name="P", holdings=(Holding("X", Decimal("1"), Decimal("1")),)),
        StaticFundamentalDataProvider({"X": snapshot}),
    )

    normalized = report.holdings[0]
    assert normalized.data_status == "partial"
    assert "profitability metrics unavailable" in normalized.warnings
    assert "debt metrics unavailable" in normalized.warnings
    assert "valuation metrics unavailable" in normalized.warnings
