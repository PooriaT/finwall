from finwall.news import (
    NewsArticle,
    NewsProviderResult,
    NewsReport,
    NewsTopicType,
    RecencyStatus,
    SourceQuality,
)
from finwall.news_summary import build_news_summary_report


def a(
    title: str,
    source_quality: SourceQuality,
    recency: RecencyStatus,
    source: str = "Reuters",
    url: str | None = "u",
):
    return NewsArticle(
        title,
        source,
        url,
        "2026-01-01T00:00:00+00:00",
        NewsTopicType.TICKER,
        "NVDA",
        "NVDA",
        None,
        source_quality,
        recency,
    )


def test_classification_and_conflict_and_references() -> None:
    result = NewsProviderResult(
        NewsTopicType.TICKER,
        "NVDA",
        (
            a("NVDA reports earnings", SourceQuality.TRUSTED, RecencyStatus.RECENT),
            a(
                "NVDA shares rise after earnings",
                SourceQuality.STANDARD,
                RecencyStatus.RECENT,
                source="CNBC",
            ),
            a(
                "NVDA may soar next big multibagger",
                SourceQuality.UNSUPPORTED,
                RecencyStatus.UNKNOWN,
                source="Reddit",
            ),
            a("NVDA raises guidance", SourceQuality.TRUSTED, RecencyStatus.RECENT),
            a("NVDA cuts guidance", SourceQuality.TRUSTED, RecencyStatus.RECENT),
            a("NVDA beats estimates", SourceQuality.STANDARD, RecencyStatus.STALE),
            a("NVDA misses estimates", SourceQuality.STANDARD, RecencyStatus.RECENT),
        ),
        "static",
        True,
    )
    raw = NewsReport((result,), (), (), (), "s", (), ("l1",))
    summary = build_news_summary_report(raw)
    topic = summary.holdings[0]

    assert topic.confirmed_facts
    assert topic.market_interpretations
    assert topic.speculative_claims
    assert topic.uncertainties
    assert any("Conflicting headlines" in w for w in topic.warnings)
    assert all(
        claim.source_references
        for claim in topic.confirmed_facts
        + topic.market_interpretations
        + topic.speculative_claims
    )
    assert topic.source_references[0].url == "u"


def test_missing_and_unavailable_become_uncertainty() -> None:
    result = NewsProviderResult(
        NewsTopicType.TICKER, "AAPL", (), "static", False, "down"
    )
    raw = NewsReport((result,), (), (), (), "s", (), ())
    summary = build_news_summary_report(raw)
    assert summary.holdings[0].uncertainties
    assert summary.holdings[0].confidence in {"low", "medium"}


def test_to_json_sections() -> None:
    raw = NewsReport((), (), (), (), "s", (), ())
    payload = build_news_summary_report(raw).to_json()
    assert '"holdings"' in payload
    assert '"watchlist"' in payload
    assert '"market"' in payload
    assert '"sectors"' in payload
