import asyncio
import logging
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime

from app.agents.classifier import classify_article
from app.connectors.base import ArticleConnector
from app.core.config import settings
from app.core.supabase import SupabaseGateway
from app.models.article import ArticleInput
from app.models.classification import ClassificationOutput
from app.models.pipeline_run import PipelineRunStatus, PipelineRunSummary, SourceFetchStats
from app.services.article_store import insert_articles
from app.services.pipeline_run_store import insert_pipeline_run

logger = logging.getLogger(__name__)


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


async def _classify_articles(
    articles: Sequence[ArticleInput],
) -> list[tuple[ArticleInput, ClassificationOutput | None]]:
    results: list[tuple[ArticleInput, ClassificationOutput | None]] = []
    interval = 60 / settings.classifier_rpm
    for i, article in enumerate(articles):
        if i > 0:
            await asyncio.sleep(interval)
        try:
            result: ClassificationOutput | None = await classify_article(article)
        except Exception as e:
            logger.warning(
                "classification_failed",
                extra={"canonical_url": article.canonical_url, "error": str(e)},
            )
            result = None
        results.append((article, result))
    return results


async def run_pipeline(
    connector_specs: Sequence[ConnectorSpec],
    gateway: SupabaseGateway | None = None,
) -> PipelineRunSummary:
    started_at = datetime.now(UTC)

    results = await asyncio.gather(*(_fetch_from_connector(spec) for spec in connector_specs))
    all_articles = [article for result in results for article in result.articles]
    dedup_result = _deduplicate_fetched_articles(all_articles)
    classified_articles = await _classify_articles(dedup_result.articles)
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
            articles=classified_articles,
        )

    summary = PipelineRunSummary(
        started_at=started_at,
        completed_at=datetime.now(UTC),
        status=PipelineRunStatus.COMPLETED,
        articles_fetched=len(all_articles),
        articles_classified=sum(1 for _, c in classified_articles if c is not None),
        source_stats=source_stats,
    )

    if gateway is not None:
        await insert_pipeline_run(gateway=gateway, summary=summary)

    return summary
