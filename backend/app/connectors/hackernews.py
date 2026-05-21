import asyncio
from datetime import UTC, datetime
from typing import Any

import httpx
from pydantic import ValidationError

from app.models.article import ArticleInput
from app.services.url_normalizer import normalize_url

HN_BASE_URL = "https://hacker-news.firebaseio.com/v0"
HN_DISCUSSION_BASE_URL = "https://news.ycombinator.com/item"


class HackerNewsConnector:
    def __init__(self, client: httpx.AsyncClient) -> None:
        self._client = client

    async def fetch_item(self, sid: int) -> dict[str, Any] | None:
        try:
            resp = await self._client.get(f"{HN_BASE_URL}/item/{sid}.json")
            resp.raise_for_status()
        except httpx.HTTPError:
            return None

        payload = resp.json()
        if not isinstance(payload, dict):
            return None

        return payload

    async def fetch_articles(self, limit: int) -> list[ArticleInput]:
        """Fetch a list of articles from the Hacker News API."""
        resp = await self._client.get(f"{HN_BASE_URL}/topstories.json")  # returns upto 500 item ids
        resp.raise_for_status()

        payload = resp.json()
        if not isinstance(payload, list):
            return []

        item_ids = [item_id for item_id in payload if isinstance(item_id, int)][:limit]
        hn_items = await asyncio.gather(*[self.fetch_item(sid) for sid in item_ids])

        articles: list[ArticleInput] = []
        for item in hn_items:
            if not item or item.get("type") != "story" or item.get("deleted") or item.get("dead"):
                continue

            hn_id = item.get("id")
            title = item.get("title")
            if not isinstance(hn_id, int) or not isinstance(title, str) or not title.strip():
                continue

            discussion_url = f"{HN_DISCUSSION_BASE_URL}?id={hn_id}"
            raw_url = item.get("url")
            article_url = (
                raw_url.strip() if isinstance(raw_url, str) and raw_url.strip() else discussion_url
            )

            try:
                article = ArticleInput.model_validate(
                    {
                        "source": "hn",
                        "title": title,
                        "url": article_url,
                        "canonical_url": normalize_url(article_url),
                        "content": item.get("text"),
                        "published_at": _published_at(item.get("time")),
                        "source_metadata": {
                            "hn_id": hn_id,
                            "author": item.get("by"),
                            "score": item.get("score"),
                            "comment_count": item.get("descendants"),
                            "discussion_url": discussion_url,
                        },
                    }
                )
            except ValidationError:
                # If one HN item has bad data, skip that item, ingest the rest.
                continue

            articles.append(article)

        return articles


def _published_at(value: object) -> datetime | None:
    if not isinstance(value, int | float):
        return None
    return datetime.fromtimestamp(value, UTC)
