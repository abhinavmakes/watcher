from datetime import UTC, datetime

import pytest

from app.models.article import ArticleInput
from worker.pipeline import ConnectorSpec, _deduplicate_fetched_articles, run_pipeline


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


def _article(
    title: str,
    source: str = "hn",
    canonical_url: str | None = None,
) -> ArticleInput:
    url = f"https://example.com/{title.lower().replace(' ', '-')}"
    return ArticleInput.model_validate(
        {
            "source": source,
            "title": title,
            "url": url,
            "canonical_url": canonical_url or url,
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
    assert summary.source_stats["hn"].duplicates == 0
    assert summary.source_stats["hn"].error is None
    assert summary.source_stats["rss"].returned == 1
    assert summary.source_stats["rss"].duplicates == 0
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
    assert summary.source_stats["hn"].duplicates == 0
    assert summary.source_stats["hn"].error is None
    assert summary.source_stats["rss"].returned == 0
    assert summary.source_stats["rss"].duplicates == 0
    assert summary.source_stats["rss"].error == "source unavailable"


@pytest.mark.asyncio
async def test_run_pipeline_returns_empty_summary_when_no_connectors_are_registered() -> None:
    summary = await run_pipeline([])

    assert summary.status == "completed"
    assert summary.articles_fetched == 0
    assert summary.source_stats == {}


@pytest.mark.asyncio
async def test_run_pipeline_records_cross_source_duplicates() -> None:
    canonical_url = "https://example.com/shared-story"
    hn_connector = FakeConnector(
        [_article("HN story", source="hn", canonical_url=canonical_url)]
    )
    rss_connector = FakeConnector(
        [_article("RSS story", source="rss", canonical_url=canonical_url)]
    )

    summary = await run_pipeline(
        [
            ConnectorSpec(name="hn", connector=hn_connector, limit=10),
            ConnectorSpec(name="rss", connector=rss_connector, limit=10),
        ]
    )

    assert summary.articles_fetched == 2
    assert summary.source_stats["hn"].returned == 1
    assert summary.source_stats["hn"].duplicates == 0
    assert summary.source_stats["rss"].returned == 1
    assert summary.source_stats["rss"].duplicates == 1


def test_deduplicate_fetched_articles_keeps_unique_canonical_urls() -> None:
    articles = [
        _article("First story"),
        _article("Second story", source="rss"),
    ]

    result = _deduplicate_fetched_articles(articles)

    assert result.articles == articles
    assert result.duplicates_by_source == {}


def test_deduplicate_fetched_articles_keeps_first_duplicate() -> None:
    canonical_url = "https://example.com/shared-story"
    first = _article("HN story", source="hn", canonical_url=canonical_url)
    duplicate = _article("RSS story", source="rss", canonical_url=canonical_url)

    result = _deduplicate_fetched_articles([first, duplicate])

    assert result.articles == [first]
    assert result.duplicates_by_source == {"rss": 1}


def test_deduplicate_fetched_articles_counts_duplicates_by_source() -> None:
    canonical_url = "https://example.com/shared-story"
    first = _article("Original story", source="hn", canonical_url=canonical_url)
    rss_duplicate = _article("RSS duplicate", source="rss", canonical_url=canonical_url)
    github_duplicate = _article(
        "GitHub duplicate",
        source="github",
        canonical_url=canonical_url,
    )

    result = _deduplicate_fetched_articles([first, rss_duplicate, github_duplicate])

    assert result.articles == [first]
    assert result.duplicates_by_source == {"rss": 1, "github": 1}


def test_deduplicate_fetched_articles_preserves_first_seen_order() -> None:
    first = _article("First story")
    second = _article("Second story")
    duplicate_first = _article(
        "First story duplicate",
        source="rss",
        canonical_url=first.canonical_url,
    )
    third = _article("Third story")

    result = _deduplicate_fetched_articles([first, second, duplicate_first, third])

    assert result.articles == [first, second, third]


def test_deduplicate_fetched_articles_handles_empty_input() -> None:
    result = _deduplicate_fetched_articles([])

    assert result.articles == []
    assert result.duplicates_by_source == {}
