import asyncio
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime

from app.connectors.base import ArticleConnector
from app.core.supabase import SupabaseGateway
from app.models.article import ArticleInput
from app.models.pipeline_run import PipelineRunStatus, PipelineRunSummary, SourceFetchStats
from app.services.article_store import insert_articles
from app.services.pipeline_run_store import insert_pipeline_run


class PipelineError(Exception):
    """Base for all pipeline failures."""


class IngestionError(PipelineError):
    """Raised when an error occurs during article ingestion."""

    def __init__(self, message: str):
        self.message = message
        super().__init__(f"Failed to ingest articles: {message}")


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
            duplicates_by_source[article.source] = duplicates_by_source.get(article.source, 0) + 1
            continue
        seen_canonical_urls.add(article.canonical_url)
        unique_articles.append(article)
    return DedupResult(
        articles=unique_articles,
        duplicates_by_source=duplicates_by_source,
    )


async def run_pipeline(
    connector_specs: Sequence[ConnectorSpec],
    gateway: SupabaseGateway | None = None,
) -> PipelineRunSummary:
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
    if gateway is not None:
        await insert_articles(
            gateway=gateway,
            articles=dedup_result.articles,
        )

    summary = PipelineRunSummary(
        started_at=started_at,
        completed_at=datetime.now(UTC),
        status=PipelineRunStatus.COMPLETED,
        articles_fetched=len(all_articles),
        source_stats=source_stats,
    )

    if gateway is not None:
        await insert_pipeline_run(gateway=gateway, summary=summary)

    return summary
