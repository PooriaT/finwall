from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from enum import StrEnum
from typing import Protocol

from finwall.models import Portfolio


class NewsTopicType(StrEnum):
    TICKER = "ticker"
    MARKET = "market"
    SECTOR = "sector"


class SourceQuality(StrEnum):
    TRUSTED = "trusted"
    STANDARD = "standard"
    LOW_QUALITY = "low_quality"
    UNSUPPORTED = "unsupported"
    UNKNOWN = "unknown"


class RecencyStatus(StrEnum):
    RECENT = "recent"
    STALE = "stale"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class NewsArticle:
    title: str
    source_name: str
    url: str | None
    published_at: str | None
    topic_type: NewsTopicType
    topic: str
    ticker: str | None
    sector: str | None
    source_quality: SourceQuality = SourceQuality.UNKNOWN
    recency_status: RecencyStatus = RecencyStatus.UNKNOWN
    available: bool = True
    error: str | None = None


@dataclass(frozen=True)
class NewsProviderResult:
    topic_type: NewsTopicType
    topic: str
    articles: tuple[NewsArticle, ...]
    source: str
    available: bool
    error: str | None = None


@dataclass(frozen=True)
class NewsReport:
    holdings: tuple[NewsProviderResult, ...]
    watchlist: tuple[NewsProviderResult, ...]
    market: tuple[NewsProviderResult, ...]
    sectors: tuple[NewsProviderResult, ...]
    summary: str
    warnings: tuple[str, ...]
    limitations: tuple[str, ...]

    def as_dict(self) -> dict[str, object]:
        return asdict(self)

    def to_json(self) -> str:
        return json.dumps(self.as_dict(), indent=2)


class NewsDataProvider(Protocol):
    def get_company_news(self, ticker: str, limit: int) -> NewsProviderResult: ...

    def get_market_news(self, topic: str, limit: int) -> NewsProviderResult: ...

    def get_sector_news(self, sector: str, limit: int) -> NewsProviderResult: ...


TRUSTED_SOURCES = {"reuters", "bloomberg", "associated press", "wsj"}
STANDARD_SOURCES = {"cnbc", "marketwatch", "financial times", "yahoo finance"}
LOW_QUALITY_SOURCES = {"benzinga", "investorplace"}
UNSUPPORTED_SOURCES = {"reddit", "stocktwits", "x"}


def _normalize_source_name(source_name: str) -> str:
    return " ".join(source_name.strip().lower().split())


def classify_source_quality(source_name: str | None) -> SourceQuality:
    if not source_name:
        return SourceQuality.UNKNOWN
    normalized = _normalize_source_name(source_name)
    if normalized in TRUSTED_SOURCES:
        return SourceQuality.TRUSTED
    if normalized in STANDARD_SOURCES:
        return SourceQuality.STANDARD
    if normalized in LOW_QUALITY_SOURCES:
        return SourceQuality.LOW_QUALITY
    if normalized in UNSUPPORTED_SOURCES:
        return SourceQuality.UNSUPPORTED
    return SourceQuality.UNKNOWN


def classify_recency(
    published_at: str | None,
    *,
    max_age_hours: int,
    now: datetime | None = None,
) -> RecencyStatus:
    if not published_at:
        return RecencyStatus.UNKNOWN
    try:
        cleaned = published_at.strip().replace("Z", "+00:00")
        parsed = datetime.fromisoformat(cleaned)
    except ValueError:
        return RecencyStatus.UNKNOWN

    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)

    current = now or datetime.now(timezone.utc)
    if parsed < current - timedelta(hours=max_age_hours):
        return RecencyStatus.STALE
    return RecencyStatus.RECENT


def _normalize_title(title: str) -> str:
    return re.sub(r"\s+", " ", title.strip().lower())


def deduplicate_articles(
    articles: tuple[NewsArticle, ...],
) -> tuple[tuple[NewsArticle, ...], int]:
    seen_urls: set[str] = set()
    seen_titles: set[tuple[str, str]] = set()
    unique: list[NewsArticle] = []
    duplicates = 0

    for article in articles:
        normalized_url = (article.url or "").strip().lower()
        if normalized_url:
            if normalized_url in seen_urls:
                duplicates += 1
                continue
            seen_urls.add(normalized_url)
            unique.append(article)
            continue

        key = (
            _normalize_title(article.title),
            _normalize_source_name(article.source_name),
        )
        if key in seen_titles:
            duplicates += 1
            continue
        seen_titles.add(key)
        unique.append(article)

    return tuple(unique), duplicates


class StaticNewsDataProvider:
    def __init__(
        self,
        company_news: dict[str, NewsProviderResult] | None = None,
        market_news: dict[str, NewsProviderResult] | None = None,
        sector_news: dict[str, NewsProviderResult] | None = None,
        *,
        source: str = "static",
    ) -> None:
        self.source = source
        self._company_news = {k.upper(): v for k, v in (company_news or {}).items()}
        self._market_news = {k.lower(): v for k, v in (market_news or {}).items()}
        self._sector_news = {k.lower(): v for k, v in (sector_news or {}).items()}

    def get_company_news(self, ticker: str, limit: int) -> NewsProviderResult:
        normalized = ticker.upper()
        configured = self._company_news.get(normalized)
        if configured is None:
            return self._unavailable_result(
                NewsTopicType.TICKER, normalized, "company news not configured"
            )
        return _trim_result(configured, limit)

    def get_market_news(self, topic: str, limit: int) -> NewsProviderResult:
        normalized = topic.lower()
        configured = self._market_news.get(normalized)
        if configured is None:
            return self._unavailable_result(
                NewsTopicType.MARKET, topic, "market news not configured"
            )
        return _trim_result(configured, limit)

    def get_sector_news(self, sector: str, limit: int) -> NewsProviderResult:
        normalized = sector.lower()
        configured = self._sector_news.get(normalized)
        if configured is None:
            return self._unavailable_result(
                NewsTopicType.SECTOR, sector, "sector news not configured"
            )
        return _trim_result(configured, limit)

    def _unavailable_result(
        self, topic_type: NewsTopicType, topic: str, error: str
    ) -> NewsProviderResult:
        return NewsProviderResult(topic_type, topic, (), self.source, False, error)


def _trim_result(result: NewsProviderResult, limit: int) -> NewsProviderResult:
    if limit <= 0:
        return NewsProviderResult(
            result.topic_type,
            result.topic,
            (),
            result.source,
            result.available,
            result.error,
        )
    return NewsProviderResult(
        topic_type=result.topic_type,
        topic=result.topic,
        articles=result.articles[:limit],
        source=result.source,
        available=result.available,
        error=result.error,
    )


def build_news_data_provider(
    provider_name: str, timeout_seconds: float
) -> NewsDataProvider:
    del timeout_seconds
    if provider_name.strip().lower() != "static":
        return StaticNewsDataProvider(source=f"static-fallback:{provider_name}")
    return StaticNewsDataProvider()


def _enrich_articles(
    result: NewsProviderResult,
    *,
    max_age_hours: int,
) -> tuple[tuple[NewsArticle, ...], int]:
    enriched = tuple(
        NewsArticle(
            title=item.title,
            source_name=item.source_name,
            url=item.url,
            published_at=item.published_at,
            topic_type=item.topic_type,
            topic=item.topic,
            ticker=item.ticker,
            sector=item.sector,
            source_quality=classify_source_quality(item.source_name),
            recency_status=classify_recency(
                item.published_at, max_age_hours=max_age_hours
            ),
            available=item.available,
            error=item.error,
        )
        for item in result.articles
    )
    return deduplicate_articles(enriched)


def build_news_report(
    portfolio: Portfolio,
    provider: NewsDataProvider,
    *,
    include_market: bool = True,
    include_sectors: bool = True,
    limit_per_topic: int = 5,
    max_age_hours: int = 72,
) -> NewsReport:
    warnings: list[str] = []
    limitations = [
        "News output is raw decision-support input only and not financial advice.",
        "News is not integrated into recommendations, sentiment, or automated actions.",
    ]

    holdings: list[NewsProviderResult] = []
    for holding in portfolio.holdings:
        try:
            raw = provider.get_company_news(holding.ticker, limit_per_topic)
        except Exception as exc:
            warnings.append(f"holding {holding.ticker}: {exc}")
            raw = NewsProviderResult(
                NewsTopicType.TICKER, holding.ticker, (), "provider", False, str(exc)
            )
        deduped, removed = _enrich_articles(raw, max_age_hours=max_age_hours)
        if removed:
            warnings.append(
                f"holding {holding.ticker}: removed {removed} duplicate article(s)"
            )
        holdings.append(
            NewsProviderResult(
                raw.topic_type, raw.topic, deduped, raw.source, raw.available, raw.error
            )
        )

    watchlist: list[NewsProviderResult] = []
    for item in portfolio.watchlist:
        try:
            raw = provider.get_company_news(item.ticker, limit_per_topic)
        except Exception as exc:
            warnings.append(f"watchlist {item.ticker}: {exc}")
            raw = NewsProviderResult(
                NewsTopicType.TICKER, item.ticker, (), "provider", False, str(exc)
            )
        deduped, removed = _enrich_articles(raw, max_age_hours=max_age_hours)
        if removed:
            warnings.append(
                f"watchlist {item.ticker}: removed {removed} duplicate article(s)"
            )
        watchlist.append(
            NewsProviderResult(
                raw.topic_type, raw.topic, deduped, raw.source, raw.available, raw.error
            )
        )

    market: list[NewsProviderResult] = []
    if include_market:
        try:
            raw = provider.get_market_news("market", limit_per_topic)
        except Exception as exc:
            warnings.append(f"market: {exc}")
            raw = NewsProviderResult(
                NewsTopicType.MARKET, "market", (), "provider", False, str(exc)
            )
        deduped, removed = _enrich_articles(raw, max_age_hours=max_age_hours)
        if removed:
            warnings.append(f"market: removed {removed} duplicate article(s)")
        market.append(
            NewsProviderResult(
                raw.topic_type, raw.topic, deduped, raw.source, raw.available, raw.error
            )
        )

    sectors: list[NewsProviderResult] = []
    if include_sectors:
        unique_sectors = sorted(
            {holding.sector for holding in portfolio.holdings if holding.sector}
        )
        for sector in unique_sectors:
            try:
                raw = provider.get_sector_news(sector, limit_per_topic)
            except Exception as exc:
                warnings.append(f"sector {sector}: {exc}")
                raw = NewsProviderResult(
                    NewsTopicType.SECTOR, sector, (), "provider", False, str(exc)
                )
            deduped, removed = _enrich_articles(raw, max_age_hours=max_age_hours)
            if removed:
                warnings.append(
                    f"sector {sector}: removed {removed} duplicate article(s)"
                )
            sectors.append(
                NewsProviderResult(
                    raw.topic_type,
                    raw.topic,
                    deduped,
                    raw.source,
                    raw.available,
                    raw.error,
                )
            )

    summary = (
        f"News topics: holdings={len(holdings)}, watchlist={len(watchlist)}, "
        f"market={len(market)}, sectors={len(sectors)}."
    )

    return NewsReport(
        tuple(holdings),
        tuple(watchlist),
        tuple(market),
        tuple(sectors),
        summary,
        tuple(warnings),
        tuple(limitations),
    )
