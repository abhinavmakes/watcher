from datetime import UTC, datetime

import pytest

from app.models.article import ArticleInput
from worker.pipeline import ConnectorSpec, run_pipeline


class FakeConnector:
    def __init__(self, articles: list[ArticleInput]) -> None:
        self._articles = articles
        self.seen_limit: int | None = None

    async def fetch_articles(self, limit: int) -> list[ArticleInput]:
        self.seen_limit = limit
        return self._articles[:limit]


class FailingConnector:
    async def fetch_articles(self, limit: int) -> list[ArticleInput]:
        raise RuntimeError("source unavailable")


def _article(title: str, source: str = "hn") -> ArticleInput:
    return ArticleInput.model_validate(
        {
            "source": source,
            "title": title,
            "url": f"https://example.com/{title.lower().replace(' ', '-')}",
            "canonical_url": f"https://example.com/{title.lower().replace(' ', '-')}",
            "content": "Article body",
            "published_at": datetime(2026, 5, 21, tzinfo=UTC),
            "source_metadata": {},
        }
    )


@pytest.mark.asyncio
async def test_run_pipeline_fetches_from_all_connectors() -> None:
    hn_connector = FakeConnector([_article("HN story")])
    rss_connector = FakeConnector([_article("RSS story", source="rss")])

    summary = await run_pipeline(
        [
            ConnectorSpec(name="hn", connector=hn_connector, limit=10),
            ConnectorSpec(name="rss", connector=rss_connector, limit=5),
        ]
    )

    assert summary.status == "completed"
    assert summary.articles_fetched == 2
    assert summary.articles_classified == 0
    assert summary.clusters_updated == 0
    assert summary.clusters_created == 0
    assert summary.source_stats["hn"].returned == 1
    assert summary.source_stats["hn"].error is None
    assert summary.source_stats["rss"].returned == 1
    assert summary.source_stats["rss"].error is None
    assert hn_connector.seen_limit == 10
    assert rss_connector.seen_limit == 5


@pytest.mark.asyncio
async def test_run_pipeline_continues_when_one_connector_fails() -> None:
    summary = await run_pipeline(
        [
            ConnectorSpec(
                name="hn",
                connector=FakeConnector([_article("Working story")]),
                limit=10,
            ),
            ConnectorSpec(name="rss", connector=FailingConnector(), limit=5),
        ]
    )

    assert summary.status == "completed"
    assert summary.articles_fetched == 1
    assert summary.source_stats["hn"].returned == 1
    assert summary.source_stats["hn"].error is None
    assert summary.source_stats["rss"].returned == 0
    assert summary.source_stats["rss"].error == "source unavailable"


@pytest.mark.asyncio
async def test_run_pipeline_returns_empty_summary_when_no_connectors_are_registered() -> None:
    summary = await run_pipeline([])

    assert summary.status == "completed"
    assert summary.articles_fetched == 0
    assert summary.source_stats == {}
