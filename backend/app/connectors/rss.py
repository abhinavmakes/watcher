import asyncio
from datetime import datetime
from email.utils import parsedate_to_datetime
from typing import Any

import feedparser
import httpx
from bs4 import BeautifulSoup
from pydantic import ValidationError

from app.models.article import ArticleInput
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

            articles.extend(self._feed_to_articles(feed_url, feed_bytes))
            if len(articles) >= limit:
                return articles[:limit]

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
                    "content": _clean_html(entry.get("summary")),
                    "published_at": _parse_published(entry.get("published")),
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


def _clean_html(value: object) -> str | None:
    if not isinstance(value, str):
        return None

    text = BeautifulSoup(value, "html.parser").get_text(" ", strip=True)
    return text or None


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
