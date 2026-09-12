import asyncio
from datetime import datetime
from email.utils import parsedate_to_datetime
from typing import Any

import feedparser
import httpx
from pydantic import ValidationError

from app.models.article import ArticleInput
from app.services.html_text import clean_html
from app.services.url_normalizer import normalize_url


class RssConnector:
    def __init__(self, client: httpx.AsyncClient, feed_urls: list[str]) -> None:
        self._client = client
        self._feed_urls = feed_urls

    async def _fetch_feed(self, feed_url: str) -> bytes | None:
        try:
            resp = await self._client.get(feed_url)
            resp.raise_for_status()
        except httpx.HTTPError:
            return None
        return resp.content

    async def fetch_articles(self, limit: int) -> list[ArticleInput]:
        if limit < 1:
            return []

        feed_results = await asyncio.gather(
            *(self._fetch_feed(feed_url) for feed_url in self._feed_urls)
        )

        articles: list[ArticleInput] = []
        for feed_url, feed_bytes in zip(self._feed_urls, feed_results, strict=True):
            if feed_bytes is None:
                continue
            # Per-feed cap: each feed contributes at most `limit`, so one dense feed
            # (e.g. a Google News query returning ~100 items) can't starve the others.
            # Total is bounded by limit * len(feed_urls).
            articles.extend(self._feed_to_articles(feed_url, feed_bytes)[:limit])

        return articles

    def _feed_to_articles(self, feed_url: str, feed_bytes: bytes) -> list[ArticleInput]:
        parsed_feed: Any = feedparser.parse(feed_bytes)
        feed_title = parsed_feed.feed.get("title")
        if not isinstance(feed_title, str):
            feed_title = None

        articles: list[ArticleInput] = []
        for entry in parsed_feed.entries:
            article = self._entry_to_article(feed_url, feed_title, entry)
            if article is not None:
                articles.append(article)

        return articles

    def _entry_to_article(
        self,
        feed_url: str,
        feed_title: str | None,
        entry: dict[str, Any],
    ) -> ArticleInput | None:
        title = entry.get("title")
        link = entry.get("link")

        if (
            not isinstance(title, str)
            or not title.strip()
            or not isinstance(link, str)
            or not link.strip()
        ):
            return None

        link = link.strip()
        try:
            article = ArticleInput.model_validate(
                {
                    "source": "rss",
                    "title": title.strip(),
                    "url": link,
                    "canonical_url": normalize_url(link),
                    "content": _extract_body(entry),
                    "published_at": _parse_published(_published_value(entry)),
                    "source_metadata": {
                        "feed_url": feed_url,
                        "feed_title": feed_title,
                        "entry_id": entry.get("id"),
                        "tags": _extract_tags(entry.get("tags")),
                    },
                }
            )
        except ValidationError:
            return None

        return article


def _extract_body(entry: dict[str, Any]) -> str | None:
    """Prefer the full post body over the teaser.

    Feeds carry the body in `<content:encoded>` (RSS) or `<content>` (Atom), which feedparser
    surfaces as `entry.content`; `<description>`/`summary` is usually a truncated teaser. Reading
    only `summary` cost 30-67x the text on every feed that ships both — measured 2026-08-02:
    Ahead of AI 74 -> 33,325 chars, Pragmatic Engineer 170 -> 12,066, AWS ML blog 314 -> 21,115.
    """
    content = entry.get("content")
    if isinstance(content, list) and content:
        first = content[0]
        if isinstance(first, dict):
            body = clean_html(first.get("value"))
            if body:
                return body

    return clean_html(entry.get("summary"))


def _published_value(entry: dict[str, Any]) -> object:
    """Atom entries may carry only `<updated>`; feedparser aliases `updated` to `published`
    but not the reverse, so reading `published` alone silently drops the date on those feeds.
    """
    return entry.get("published") or entry.get("updated")


def _parse_published(value: object) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None

    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        pass

    try:
        return parsedate_to_datetime(value)
    except (TypeError, ValueError):
        return None


def _extract_tags(value: object) -> list[str]:
    if not isinstance(value, list):
        return []

    tags: list[str] = []
    for tag in value:
        if isinstance(tag, dict) and isinstance(tag.get("term"), str):
            tags.append(tag["term"])

    return tags
