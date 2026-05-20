from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from enum import StrEnum

from finwall.news import (
    NewsArticle,
    NewsProviderResult,
    NewsReport,
    RecencyStatus,
    SourceQuality,
)


class NewsClaimConfidence(StrEnum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class NewsClaimType(StrEnum):
    CONFIRMED_FACT = "confirmed_fact"
    MARKET_INTERPRETATION = "market_interpretation"
    UNCERTAINTY = "uncertainty"
    SPECULATIVE = "speculative"


FACT_PATTERNS = (
    "reports earnings",
    "announces",
    "files",
    "raises guidance",
    "cuts guidance",
    "launches",
    "acquires",
    "beats estimates",
    "misses estimates",
    "appoints",
    "approves",
    "receives approval",
)
INTERPRETATION_PATTERNS = (
    "shares rise",
    "shares fall",
    "stock jumps",
    "stock drops",
    "analysts say",
    "why investors",
    "market reacts",
    "could benefit",
    "pressure on shares",
)
SPECULATIVE_PATTERNS = (
    "rumor",
    "may",
    "might",
    "could",
    "prediction",
    "target",
    "will soar",
    "will crash",
    "next big",
    "multibagger",
    "guaranteed",
    "hot stock",
    "buy now",
)
CONFLICT_GROUPS = (
    ("raises guidance", "cuts guidance"),
    ("beats estimates", "misses estimates"),
    ("shares rise", "shares fall"),
    ("upgrade", "downgrade"),
)


@dataclass(frozen=True)
class NewsSourceReference:
    title: str
    source_name: str
    url: str | None
    published_at: str | None
    source_quality: str
    recency_status: str


@dataclass(frozen=True)
class NewsClaim:
    claim_type: str
    text: str
    confidence: str
    source_references: tuple[NewsSourceReference, ...]
    warning: str | None = None


@dataclass(frozen=True)
class TopicNewsSummary:
    topic_type: str
    topic: str
    ticker: str | None
    confirmed_facts: tuple[NewsClaim, ...]
    market_interpretations: tuple[NewsClaim, ...]
    uncertainties: tuple[NewsClaim, ...]
    speculative_claims: tuple[NewsClaim, ...]
    source_references: tuple[NewsSourceReference, ...]
    warnings: tuple[str, ...]
    confidence: str


@dataclass(frozen=True)
class NewsSummaryReport:
    holdings: tuple[TopicNewsSummary, ...]
    watchlist: tuple[TopicNewsSummary, ...]
    market: tuple[TopicNewsSummary, ...]
    sectors: tuple[TopicNewsSummary, ...]
    summary: str
    warnings: tuple[str, ...]
    limitations: tuple[str, ...]

    def as_dict(self) -> dict[str, object]:
        return asdict(self)

    def to_json(self) -> str:
        return json.dumps(self.as_dict(), indent=2)


def _reference(article: NewsArticle) -> NewsSourceReference:
    return NewsSourceReference(
        title=article.title,
        source_name=article.source_name,
        url=article.url,
        published_at=article.published_at,
        source_quality=article.source_quality.value,
        recency_status=article.recency_status.value,
    )


def _contains_any(text: str, patterns: tuple[str, ...]) -> bool:
    return any(pattern in text for pattern in patterns)


def _detect_conflicts(articles: tuple[NewsArticle, ...]) -> tuple[str, ...]:
    text = " || ".join(article.title.lower() for article in articles)
    warnings: list[str] = []
    for left, right in CONFLICT_GROUPS:
        if left in text and right in text:
            warnings.append(
                "Conflicting headlines include "
                f"'{left}' and '{right}'; "
                "Finwall does not resolve the conflict."
            )
    return tuple(warnings)


def _build_topic_summary(result: NewsProviderResult) -> TopicNewsSummary:
    refs = tuple(_reference(article) for article in result.articles)
    confirmed_facts: list[NewsClaim] = []
    interpretations: list[NewsClaim] = []
    uncertainties: list[NewsClaim] = []
    speculative: list[NewsClaim] = []
    warnings: list[str] = []

    if not result.available:
        warning = (
            f"Provider unavailable for topic '{result.topic}': "
            f"{result.error or 'unknown error'}."
        )
        warnings.append(warning)
        uncertainties.append(
            NewsClaim(
                claim_type=NewsClaimType.UNCERTAINTY.value,
                text=(
                    "Unclear from available headlines because provider data is "
                    f"unavailable for {result.topic}."
                ),
                confidence=NewsClaimConfidence.LOW.value,
                source_references=(),
                warning=warning,
            )
        )

    if not result.articles:
        uncertainties.append(
            NewsClaim(
                claim_type=NewsClaimType.UNCERTAINTY.value,
                text=(
                    "Unclear from available headlines because no articles were "
                    f"returned for {result.topic}."
                ),
                confidence=NewsClaimConfidence.LOW.value,
                source_references=(),
            )
        )

    for article in result.articles:
        title = article.title.strip()
        lowered = title.lower()
        claim_ref = (_reference(article),)

        is_speculative_text = _contains_any(lowered, SPECULATIVE_PATTERNS)
        is_market_interpretation = _contains_any(lowered, INTERPRETATION_PATTERNS)
        is_fact_like = _contains_any(lowered, FACT_PATTERNS)
        strong_source = article.source_quality in {
            SourceQuality.TRUSTED,
            SourceQuality.STANDARD,
        }
        high_quality_source = article.source_quality in {SourceQuality.TRUSTED}
        recency_ok = article.recency_status in {
            RecencyStatus.RECENT,
            RecencyStatus.UNKNOWN,
        }

        if (
            article.source_quality
            in {SourceQuality.LOW_QUALITY, SourceQuality.UNSUPPORTED}
            or is_speculative_text
        ):
            warning = None
            if article.source_quality == SourceQuality.UNSUPPORTED:
                warning = "Low-confidence claim from unsupported source."
            speculative.append(
                NewsClaim(
                    claim_type=NewsClaimType.SPECULATIVE.value,
                    text=f"Low-confidence claim from headline: {title}",
                    confidence=NewsClaimConfidence.LOW.value,
                    source_references=claim_ref,
                    warning=warning,
                )
            )
            continue

        if is_market_interpretation:
            interpretations.append(
                NewsClaim(
                    claim_type=NewsClaimType.MARKET_INTERPRETATION.value,
                    text=f"Possible interpretation from headline: {title}",
                    confidence=NewsClaimConfidence.MEDIUM.value,
                    source_references=claim_ref,
                )
            )
            continue

        if is_fact_like and strong_source and recency_ok and not is_speculative_text:
            confidence = (
                NewsClaimConfidence.HIGH.value
                if high_quality_source
                else NewsClaimConfidence.MEDIUM.value
            )
            confirmed_facts.append(
                NewsClaim(
                    claim_type=NewsClaimType.CONFIRMED_FACT.value,
                    text=f"Headline indicates: {title}",
                    confidence=confidence,
                    source_references=claim_ref,
                )
            )
            continue

        uncertainties.append(
            NewsClaim(
                claim_type=NewsClaimType.UNCERTAINTY.value,
                text=f"Unclear from available headlines: {title}",
                confidence=NewsClaimConfidence.LOW.value,
                source_references=claim_ref,
            )
        )

    if any(
        article.recency_status == RecencyStatus.STALE for article in result.articles
    ):
        warnings.append(
            "Some headlines are stale and may not reflect current conditions."
        )
    if any(
        article.source_quality == SourceQuality.UNKNOWN for article in result.articles
    ):
        warnings.append("Some headlines come from unknown source quality.")

    for conflict_warning in _detect_conflicts(result.articles):
        warnings.append(conflict_warning)
        uncertainties.append(
            NewsClaim(
                claim_type=NewsClaimType.UNCERTAINTY.value,
                text="Conflicting headlines were detected; Finwall does not resolve the conflict.",
                confidence=NewsClaimConfidence.LOW.value,
                source_references=refs,
                warning=conflict_warning,
            )
        )

    topic_confidence = NewsClaimConfidence.HIGH.value
    if warnings or uncertainties or speculative:
        topic_confidence = NewsClaimConfidence.MEDIUM.value
    if len(warnings) > 1 or (speculative and uncertainties):
        topic_confidence = NewsClaimConfidence.LOW.value

    return TopicNewsSummary(
        topic_type=result.topic_type.value,
        topic=result.topic,
        ticker=result.topic if result.topic_type.value == "ticker" else None,
        confirmed_facts=tuple(confirmed_facts),
        market_interpretations=tuple(interpretations),
        uncertainties=tuple(uncertainties),
        speculative_claims=tuple(speculative),
        source_references=refs,
        warnings=tuple(warnings),
        confidence=topic_confidence,
    )


def build_news_summary_report(news_report: NewsReport) -> NewsSummaryReport:
    holdings = tuple(_build_topic_summary(item) for item in news_report.holdings)
    watchlist = tuple(_build_topic_summary(item) for item in news_report.watchlist)
    market = tuple(_build_topic_summary(item) for item in news_report.market)
    sectors = tuple(_build_topic_summary(item) for item in news_report.sectors)

    warnings = list(news_report.warnings)
    for section in (holdings, watchlist, market, sectors):
        for topic in section:
            warnings.extend(topic.warnings)

    limitations = list(news_report.limitations) + [
        "News summaries are deterministic headline classifications and do not use LLMs.",
        "News summaries are decision-support input only and do not provide trade recommendations.",
    ]

    summary = (
        "News summaries separate confirmed facts, possible market interpretations, "
        "uncertainties, and speculative/low-confidence claims using deterministic headline rules."
    )

    return NewsSummaryReport(
        holdings=holdings,
        watchlist=watchlist,
        market=market,
        sectors=sectors,
        summary=summary,
        warnings=tuple(warnings),
        limitations=tuple(limitations),
    )
