from finwall.fundamental_summary import (
    FundamentalRiskLevel,
    build_fundamental_summary_report,
    summarize_fundamental_snapshot,
)
from finwall.fundamentals import (
    CompanyProfile,
    FundamentalAnalysisReport,
    FundamentalMetric,
    FundamentalSnapshot,
)


def mk_snapshot(ticker: str, **kwargs) -> FundamentalSnapshot:
    base = FundamentalSnapshot(
        ticker=ticker,
        source="static",
        data_status="available",
        profile=CompanyProfile(
            ticker, f"{ticker} Inc", "Tech", "Software", "US", None, "static", True
        ),
        revenue_growth=FundamentalMetric("revenue_growth", "10%", True, "static"),
        earnings_growth=FundamentalMetric("earnings_growth", "8%", True, "static"),
        profitability=(FundamentalMetric("net_margin", "20%", True, "static"),),
        debt=(
            FundamentalMetric("debt_to_equity", "0.2", True, "static"),
            FundamentalMetric("current_ratio", "2", True, "static"),
        ),
        valuation=(FundamentalMetric("pe_ratio", "20", True, "static"),),
        warnings=(),
    )
    return FundamentalSnapshot(**(base.__dict__ | kwargs))


def test_strong_fundamentals_example() -> None:
    summary = summarize_fundamental_snapshot(mk_snapshot("NVDA"))
    assert summary.risk_level == FundamentalRiskLevel.LOW
    assert summary.strengths


def test_weak_revenue_profitability_valuation_debt_and_speculative_flags() -> None:
    summary = summarize_fundamental_snapshot(
        mk_snapshot(
            "X",
            revenue_growth=FundamentalMetric("revenue_growth", "-5%", True, "static"),
            profitability=(FundamentalMetric("net_margin", "-3%", True, "static"),),
            valuation=(FundamentalMetric("pe_ratio", "80", True, "static"),),
            debt=(FundamentalMetric("debt_to_equity", "3", True, "static"),),
        )
    )
    assert "weak_revenue_trend" in summary.flags
    assert "weak_profitability" in summary.flags
    assert "high_valuation_risk" in summary.flags
    assert "high_debt_risk" in summary.flags
    assert "speculative_profile" in summary.flags
    assert summary.risk_level == FundamentalRiskLevel.HIGH


def test_missing_and_partial_data_and_unparseable_inputs() -> None:
    summary = summarize_fundamental_snapshot(
        mk_snapshot(
            "Y",
            profile=CompanyProfile("Y", None, None, None, None, None, "static", False),
            revenue_growth=FundamentalMetric(
                "revenue_growth", "unknown", True, "static"
            ),
            profitability=(FundamentalMetric("net_margin", None, False, "static"),),
            valuation=(FundamentalMetric("pe_ratio", "n/a", True, "static"),),
            debt=(),
        )
    )
    assert "company_profile" in summary.missing_information
    assert "debt_metrics" in summary.missing_information
    assert any("raw" in i for i in summary.reasoning_inputs)
    assert "profitability:net_margin" in summary.missing_information
    assert summary.profitability == "missing"
    assert summary.valuation_risk == "missing"
    assert summary.debt_risk == "missing"


def test_valuation_not_reasonable_without_usable_metrics() -> None:
    summary = summarize_fundamental_snapshot(
        mk_snapshot(
            "Z",
            valuation=(FundamentalMetric("pe_ratio", "n/a", True, "static"),),
        )
    )
    assert summary.valuation_risk == "missing"
    assert "valuation_metrics" in summary.missing_information


def test_debt_not_moderate_without_usable_metrics() -> None:
    summary = summarize_fundamental_snapshot(
        mk_snapshot(
            "Q",
            debt=(FundamentalMetric("debt_to_equity", "n/a", True, "static"),),
        )
    )
    assert summary.debt_risk == "missing"
    assert "debt_metrics" in summary.missing_information


def test_build_report_preserves_holdings_and_watchlist_and_json() -> None:
    raw = FundamentalAnalysisReport(
        holdings=(mk_snapshot("AAA"),),
        watchlist=(mk_snapshot("BBB"),),
        summary="raw",
        limitations=("raw limit",),
    )
    report = build_fundamental_summary_report(raw)
    assert [x.ticker for x in report.holdings] == ["AAA"]
    assert [x.ticker for x in report.watchlist] == ["BBB"]
    assert '"holdings": [' in report.to_json()
