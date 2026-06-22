import math
from decimal import Decimal

from finwall.fundamentals import (
    CompanyProfile,
    FundamentalMetric,
    FundamentalSnapshot,
    StaticFundamentalDataProvider,
    build_fundamental_analysis_report,
    build_fundamental_data_provider,
)
from finwall.fundamentals_yfinance import YFinanceFundamentalDataProvider
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


class FakeYFinanceProvider(YFinanceFundamentalDataProvider):
    def __init__(self, info):
        super().__init__()
        self.info = info

    def _load_info(self, ticker: str):
        if isinstance(self.info, Exception):
            raise self.info
        return self.info


def test_yfinance_provider_extracts_profile_and_metrics() -> None:
    provider = FakeYFinanceProvider(
        {
            "longName": "NVIDIA Corporation",
            "sector": "Technology",
            "industry": "Semiconductors",
            "country": "United States",
            "website": "https://www.nvidia.com",
            "revenueGrowth": 0.12,
            "earningsGrowth": 0.20,
            "grossMargins": 0.75,
            "operatingMargins": 0.55,
            "profitMargins": 0.48,
            "returnOnEquity": 1.1,
            "returnOnAssets": 0.45,
            "debtToEquity": 22.4,
            "currentRatio": 4.1,
            "trailingPE": 50.2,
            "forwardPE": 31.5,
            "priceToSalesTrailing12Months": 28.7,
            "priceToBook": 45.9,
        }
    )

    snapshot = provider.get_fundamentals("nvda")

    assert snapshot.ticker == "NVDA"
    assert snapshot.source == "yfinance"
    assert snapshot.data_status == "available"
    assert snapshot.profile.company_name == "NVIDIA Corporation"
    assert snapshot.profile.sector == "Technology"
    assert snapshot.revenue_growth.value == "12%"
    assert snapshot.earnings_growth.value == "20%"
    assert snapshot.profitability[0].value == "75%"
    assert snapshot.debt[0].value == "0.22"
    assert snapshot.valuation[0].name == "pe_ratio"
    assert snapshot.valuation[0].value == "50.2"


def test_yfinance_provider_rejects_non_finite_metric_values() -> None:
    provider = FakeYFinanceProvider(
        {
            "longName": "Non Finite Corp",
            "revenueGrowth": math.nan,
            "earningsGrowth": math.inf,
            "trailingPE": "-inf",
        }
    )

    snapshot = provider.get_fundamentals("NAN")

    assert snapshot.data_status == "partial"
    assert snapshot.revenue_growth.available is False
    assert snapshot.earnings_growth.available is False
    assert snapshot.valuation[0].name == "pe_ratio"
    assert snapshot.valuation[0].available is False
    assert "revenue growth unavailable" in snapshot.warnings
    assert "valuation metrics unavailable" in snapshot.warnings


def test_yfinance_provider_handles_partial_missing_profile_and_metrics() -> None:
    provider = FakeYFinanceProvider({"shortName": "Partial Co", "trailingPE": 10})

    snapshot = provider.get_fundamentals("PART")

    assert snapshot.data_status == "partial"
    assert snapshot.profile.company_name == "Partial Co"
    assert snapshot.revenue_growth.available is False
    assert snapshot.valuation[0].available is True
    assert "revenue growth unavailable" in snapshot.warnings
    assert "debt metrics unavailable" in snapshot.warnings


def test_yfinance_provider_unparseable_metric_is_unavailable() -> None:
    provider = FakeYFinanceProvider(
        {"longName": "Bad Metric", "revenueGrowth": "not-a-number"}
    )

    snapshot = provider.get_fundamentals("BAD")

    assert snapshot.revenue_growth.available is False
    assert snapshot.revenue_growth.value is None
    assert "revenue growth unavailable" in snapshot.warnings


def test_yfinance_provider_exception_returns_safe_missing_snapshot() -> None:
    provider = FakeYFinanceProvider(RuntimeError("secret provider payload"))

    snapshot = provider.get_fundamentals("ERR")
    payload = snapshot.profile.error + " " + " ".join(snapshot.warnings)

    assert snapshot.data_status == "missing_data"
    assert "provider request failed" in payload
    assert "secret provider payload" not in payload


def test_yfinance_provider_unknown_ticker_returns_missing_data() -> None:
    snapshot = FakeYFinanceProvider({}).get_fundamentals("UNKNOWN")

    assert snapshot.data_status == "missing_data"
    assert snapshot.source == "yfinance"
    assert "ticker fundamentals unavailable" in snapshot.warnings


def test_provider_selection_supports_yfinance() -> None:
    provider = build_fundamental_data_provider("yfinance", 3.0)

    assert isinstance(provider, YFinanceFundamentalDataProvider)
