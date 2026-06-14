import asyncio
import logging
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime

from app.agents.classifier import classify_article
from app.connectors.base import ArticleConnector
from app.core.config import settings
from app.core.supabase import SupabaseGateway
from app.models.article import ArticleInput, EmbeddedArticle
from app.models.classification import ClassificationOutput
from app.models.pipeline_run import PipelineRunStatus, PipelineRunSummary, SourceFetchStats
from app.services.article_store import fetch_existing_canonical_urls, insert_articles
from app.services.cluster_store import fetch_existing_clusters, persist_cluster_result
from app.services.clustering import cluster_articles
from app.services.embeddings import embed_texts, format_embedding_input
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


async def _embed_articles(
    classified: Sequence[tuple[ArticleInput, ClassificationOutput | None]],
) -> list[EmbeddedArticle]:
    selected = [
        (article, classification)
        for article, classification in classified
        if classification is not None and not classification.is_noise
    ]
    texts = [format_embedding_input(article) for article, _ in selected]
    vectors = await embed_texts(texts)
    return [
        EmbeddedArticle(
            canonical_url=article.canonical_url,
            title=article.title,
            domains=classification.domains,
            relevance=classification.relevance_score,
            published_at=article.published_at,
            vector=vector,
        )
        for (article, classification), vector in zip(selected, vectors, strict=True)
    ]


async def run_pipeline(
    connector_specs: Sequence[ConnectorSpec],
    gateway: SupabaseGateway | None = None,
) -> PipelineRunSummary:
    started_at = datetime.now(UTC)

    results = await asyncio.gather(*(_fetch_from_connector(spec) for spec in connector_specs))
    all_articles = [article for result in results for article in result.articles]
    dedup_result = _deduplicate_fetched_articles(all_articles)

    # Classify only articles we have not seen before. Re-classifying already-persisted
    # articles is the dominant recurring LLM cost, so filter against the DB first.
    to_classify = dedup_result.articles
    articles_skipped_known = 0
    if gateway is not None:
        existing = await fetch_existing_canonical_urls(
            gateway, [article.canonical_url for article in to_classify]
        )
        if existing:
            to_classify = [a for a in to_classify if a.canonical_url not in existing]
            articles_skipped_known = len(dedup_result.articles) - len(to_classify)
            logger.info(
                "pipeline_skipped_known_articles",
                extra={"known": articles_skipped_known, "to_classify": len(to_classify)},
            )

    classified_articles = await _classify_articles(to_classify)
    source_stats = {
        result.source: SourceFetchStats(
            returned=len(result.articles),
            duplicates=dedup_result.duplicates_by_source.get(result.source, 0),
            error=result.error,
        )
        for result in results
    }
    clusters_created = 0
    clusters_updated = 0
    if gateway is not None:
        embedded = await _embed_articles(classified_articles)
        await insert_articles(
            gateway=gateway,
            articles=classified_articles,
            embeddings={item.canonical_url: item.vector for item in embedded},
        )
        existing_clusters = await fetch_existing_clusters(gateway)
        cluster_result = cluster_articles(embedded, existing_clusters)
        await persist_cluster_result(gateway, cluster_result, existing_clusters, embedded)
        clusters_created = len(cluster_result.new_clusters)
        clusters_updated = len(cluster_result.updated)

    summary = PipelineRunSummary(
        started_at=started_at,
        completed_at=datetime.now(UTC),
        status=PipelineRunStatus.COMPLETED,
        articles_fetched=len(all_articles),
        articles_classified=sum(1 for _, c in classified_articles if c is not None),
        articles_skipped_known=articles_skipped_known,
        clusters_created=clusters_created,
        clusters_updated=clusters_updated,
        source_stats=source_stats,
    )

    if gateway is not None:
        await insert_pipeline_run(gateway=gateway, summary=summary)

    return summary
