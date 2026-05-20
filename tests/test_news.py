from datetime import datetime, timedelta, timezone

from finwall.models import Holding, Portfolio, WatchlistItem
from finwall.news import (
    NewsArticle,
    NewsProviderResult,
    NewsTopicType,
    RecencyStatus,
    SourceQuality,
    StaticNewsDataProvider,
    build_news_report,
    classify_recency,
    classify_source_quality,
)


def _article(
    title: str, source: str, url: str | None = None, published_at: str | None = None
):
    return NewsArticle(
        title, source, url, published_at, NewsTopicType.TICKER, "NVDA", "NVDA", None
    )


def test_static_provider_configured_and_unavailable() -> None:
    result = NewsProviderResult(
        NewsTopicType.TICKER, "NVDA", (_article("A", "Reuters"),), "static", True
    )
    provider = StaticNewsDataProvider(company_news={"NVDA": result})
    assert provider.get_company_news("NVDA", 5).available is True
    assert provider.get_company_news("AAPL", 5).available is False


def test_report_includes_sections_and_filters() -> None:
    portfolio = Portfolio(
        name="P",
        holdings=(Holding("NVDA", 1, 10, "Technology"),),
        watchlist=(WatchlistItem("AAPL"),),
    )
    provider = StaticNewsDataProvider(
        company_news={
            "NVDA": NewsProviderResult(
                NewsTopicType.TICKER,
                "NVDA",
                (_article("N", "Reuters", "u1"),),
                "static",
                True,
            ),
            "AAPL": NewsProviderResult(
                NewsTopicType.TICKER,
                "AAPL",
                (_article("A", "CNBC", "u2"),),
                "static",
                True,
            ),
        },
        market_news={
            "market": NewsProviderResult(
                NewsTopicType.MARKET, "market", (), "static", True
            )
        },
        sector_news={
            "technology": NewsProviderResult(
                NewsTopicType.SECTOR, "Technology", (), "static", True
            )
        },
    )
    report = build_news_report(
        portfolio, provider, include_market=True, include_sectors=True
    )
    assert report.holdings[0].topic == "NVDA"
    assert report.watchlist[0].topic == "AAPL"
    assert len(report.market) == 1
    assert len(report.sectors) == 1


def test_market_and_sector_optional() -> None:
    portfolio = Portfolio(name="P", holdings=(Holding("NVDA", 1, 1),))
    provider = StaticNewsDataProvider()
    report = build_news_report(
        portfolio, provider, include_market=False, include_sectors=False
    )
    assert report.market == ()
    assert report.sectors == ()


def test_deduplicate_url_and_title() -> None:
    portfolio = Portfolio(name="P", holdings=(Holding("NVDA", 1, 1),))
    dup_url = _article("T1", "Reuters", "http://x")
    dup_title1 = _article("  SAME   title ", "CNBC", None)
    dup_title2 = _article("same title", "CNBC", None)
    provider = StaticNewsDataProvider(
        company_news={
            "NVDA": NewsProviderResult(
                NewsTopicType.TICKER,
                "NVDA",
                (dup_url, dup_url, dup_title1, dup_title2),
                "static",
                True,
            )
        }
    )
    report = build_news_report(portfolio, provider)
    assert len(report.holdings[0].articles) == 2
    assert any("duplicate" in w for w in report.warnings)


def test_source_quality_and_recency() -> None:
    assert classify_source_quality("Reuters") == SourceQuality.TRUSTED
    assert classify_source_quality("CNBC") == SourceQuality.STANDARD
    assert classify_source_quality("Benzinga") == SourceQuality.LOW_QUALITY
    assert classify_source_quality("Reddit") == SourceQuality.UNSUPPORTED
    assert classify_source_quality("New Source") == SourceQuality.UNKNOWN

    now = datetime.now(timezone.utc)
    assert (
        classify_recency(
            (now - timedelta(hours=1)).isoformat(), max_age_hours=72, now=now
        )
        == RecencyStatus.RECENT
    )
    assert (
        classify_recency(
            (now - timedelta(hours=100)).isoformat(), max_age_hours=72, now=now
        )
        == RecencyStatus.STALE
    )
    assert (
        classify_recency("not-a-date", max_age_hours=72, now=now)
        == RecencyStatus.UNKNOWN
    )


def test_provider_errors_become_warnings_and_json() -> None:
    class BadProvider:
        def get_company_news(self, ticker: str, limit: int):
            raise RuntimeError("boom")

        def get_market_news(self, topic: str, limit: int):
            return NewsProviderResult(
                NewsTopicType.MARKET, topic, (), "bad", False, "x"
            )

        def get_sector_news(self, sector: str, limit: int):
            return NewsProviderResult(
                NewsTopicType.SECTOR, sector, (), "bad", False, "x"
            )

    report = build_news_report(
        Portfolio(name="P", holdings=(Holding("NVDA", 1, 1),)), BadProvider()
    )
    assert report.warnings
    payload = report.to_json()
    assert '"warnings"' in payload
    assert '"limitations"' in payload
    assert '"source_quality"' in payload or '"articles"' in payload
