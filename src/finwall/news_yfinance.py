from __future__ import annotations

import importlib
import queue
import threading
from collections.abc import Callable
from datetime import datetime, timezone
from numbers import Number
from typing import Any

from finwall.news import NewsArticle, NewsProviderResult, NewsTopicType

SOURCE = "yfinance"


class YFinanceNewsDataProvider:
    """Defensive news provider backed by yfinance ticker news."""

    def __init__(self, timeout_seconds: float = 5.0) -> None:
        self.timeout_seconds = timeout_seconds
        self.source = SOURCE

    def get_company_news(self, ticker: str, limit: int) -> NewsProviderResult:
        normalized = ticker.upper().strip()
        if not normalized:
            return _result(
                NewsTopicType.TICKER, ticker, (), False, "ticker is required"
            )

        yfinance, import_error = _load_yfinance()
        if yfinance is None:
            return _result(NewsTopicType.TICKER, normalized, (), False, import_error)

        try:
            ticker_data = yfinance.Ticker(normalized)
            raw_news = _get_ticker_news(ticker_data, self.timeout_seconds)
        except TimeoutError:
            return _result(
                NewsTopicType.TICKER,
                normalized,
                (),
                False,
                "yfinance news request timed out",
            )
        except Exception:
            return _result(
                NewsTopicType.TICKER,
                normalized,
                (),
                False,
                "yfinance news request failed",
            )

        articles = _normalize_articles(raw_news, normalized, limit)
        if not articles:
            return _result(
                NewsTopicType.TICKER,
                normalized,
                (),
                False,
                "no company news available from yfinance",
            )
        return _result(NewsTopicType.TICKER, normalized, articles, True, None)

    def get_market_news(self, topic: str, limit: int) -> NewsProviderResult:
        del limit
        return _result(
            NewsTopicType.MARKET,
            topic,
            (),
            False,
            "yfinance news provider does not support market topic news",
        )

    def get_sector_news(self, sector: str, limit: int) -> NewsProviderResult:
        del limit
        return _result(
            NewsTopicType.SECTOR,
            sector,
            (),
            False,
            "yfinance news provider does not support sector news",
        )


def _load_yfinance() -> tuple[object | None, str | None]:
    try:
        return importlib.import_module("yfinance"), None
    except ImportError:
        return None, "yfinance is not installed; install project dependencies"


def _get_ticker_news(ticker_data: object, timeout_seconds: float) -> object:
    def fetch() -> object:
        get_news = getattr(ticker_data, "get_news", None)
        if callable(get_news):
            try:
                return get_news(count=100)
            except TypeError:
                return get_news()
        return getattr(ticker_data, "news", ())

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
        raise TimeoutError("yfinance news request timed out") from exc
    if success:
        return value
    if isinstance(value, Exception):
        raise value
    raise RuntimeError("yfinance news request failed")


def _normalize_articles(
    raw_news: object, ticker: str, limit: int
) -> tuple[NewsArticle, ...]:
    if limit <= 0 or not isinstance(raw_news, (list, tuple)):
        return ()

    articles: list[NewsArticle] = []
    for item in raw_news:
        article = _normalize_article(item, ticker)
        if article is None:
            continue
        articles.append(article)
        if len(articles) >= limit:
            break
    return tuple(articles)


def _normalize_article(item: object, ticker: str) -> NewsArticle | None:
    if not isinstance(item, dict):
        return None
    content = item.get("content") if isinstance(item.get("content"), dict) else {}

    title = _first_string(item, content, keys=("title", "headline"))
    if title is None:
        return None

    source_name = _source_name(item, content) or "Unknown"
    url = _url(item, content)
    published_at = _published_at(item, content)

    return NewsArticle(
        title=title,
        source_name=source_name,
        url=url,
        published_at=published_at,
        topic_type=NewsTopicType.TICKER,
        topic=ticker,
        ticker=ticker,
        sector=None,
    )


def _first_string(*containers: dict[str, Any], keys: tuple[str, ...]) -> str | None:
    for container in containers:
        for key in keys:
            value = container.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
    return None


def _source_name(item: dict[str, Any], content: dict[str, Any]) -> str | None:
    direct = _first_string(item, content, keys=("publisher", "source", "provider"))
    if direct:
        return direct
    provider = content.get("provider")
    if isinstance(provider, dict):
        return _first_string(provider, keys=("displayName", "name"))
    return None


def _url(item: dict[str, Any], content: dict[str, Any]) -> str | None:
    direct = _first_string(item, content, keys=("link", "url", "canonicalUrl"))
    if direct:
        return direct
    canonical = content.get("canonicalUrl")
    if isinstance(canonical, dict):
        return _first_string(canonical, keys=("url",))
    click = content.get("clickThroughUrl")
    if isinstance(click, dict):
        return _first_string(click, keys=("url",))
    return None


def _published_at(item: dict[str, Any], content: dict[str, Any]) -> str | None:
    value = None
    for container in (item, content):
        for key in ("providerPublishTime", "pubDate", "displayTime", "published_at"):
            candidate = container.get(key)
            if candidate is not None:
                value = candidate
                break
        if value is not None:
            break
    if isinstance(value, str) and value.strip():
        return value.strip().replace("Z", "+00:00")
    if isinstance(value, Number):
        try:
            return datetime.fromtimestamp(float(value), timezone.utc).isoformat()
        except (OverflowError, OSError, ValueError):
            return None
    return None


def _result(
    topic_type: NewsTopicType,
    topic: str,
    articles: tuple[NewsArticle, ...],
    available: bool,
    error: str | None,
) -> NewsProviderResult:
    return NewsProviderResult(topic_type, topic, articles, SOURCE, available, error)
