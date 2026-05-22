import asyncio
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Literal

from pydantic import BaseModel, Field

from app.connectors.base import ArticleConnector
from app.models.article import ArticleInput


@dataclass(frozen=True)
class ConnectorSpec:
    name: str
    connector: ArticleConnector
    limit: int


@dataclass(frozen=True)
class FetchResult:
    source: str
    articles: list[ArticleInput]
    error: str | None = None


@dataclass(frozen=True)
class DedupResult:
    articles: list[ArticleInput]
    duplicates_by_source: dict[str, int]


class SourceFetchStats(BaseModel):
    returned: int
    duplicates: int = 0
    error: str | None = None


class PipelineRunSummary(BaseModel):
    started_at: datetime
    completed_at: datetime
    status: Literal["completed"]
    articles_fetched: int = 0
    articles_classified: int = 0
    clusters_updated: int = 0
    clusters_created: int = 0
    source_stats: dict[str, SourceFetchStats] = Field(default_factory=dict)


async def _fetch_from_connector(spec: ConnectorSpec) -> FetchResult:
    try:
        articles = await spec.connector.fetch_articles(spec.limit)
    except Exception as exc:
        return FetchResult(source=spec.name, articles=[], error=str(exc))

    return FetchResult(source=spec.name, articles=articles)


def _deduplicate_fetched_articles(articles: Sequence[ArticleInput]) -> DedupResult:
    seen_canonical_urls: set[str] = set()
    unique_articles: list[ArticleInput] = []
    duplicates_by_source: dict[str, int] = {}
    for article in articles:
        if article.canonical_url in seen_canonical_urls:
            duplicates_by_source[article.source] = (
                duplicates_by_source.get(article.source, 0) + 1
            )
            continue
        seen_canonical_urls.add(article.canonical_url)
        unique_articles.append(article)
    return DedupResult(
        articles=unique_articles,
        duplicates_by_source=duplicates_by_source,
    )


async def run_pipeline(connector_specs: Sequence[ConnectorSpec]) -> PipelineRunSummary:
    started_at = datetime.now(UTC)

    results = await asyncio.gather(*(_fetch_from_connector(spec) for spec in connector_specs))
    all_articles = [article for result in results for article in result.articles]
    dedup_result = _deduplicate_fetched_articles(all_articles)

    source_stats = {
        result.source: SourceFetchStats(
            returned=len(result.articles),
            duplicates=dedup_result.duplicates_by_source.get(result.source, 0),
            error=result.error,
        )
        for result in results
    }

    return PipelineRunSummary(
        started_at=started_at,
        completed_at=datetime.now(UTC),
        articles_fetched=len(all_articles),
        source_stats=source_stats,
        status="completed",
    )
