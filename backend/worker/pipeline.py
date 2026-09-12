import asyncio
import logging
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime

from app.agents.classifier import classify_article
from app.agents.synthesizer import synthesize_cluster
from app.connectors.base import ArticleConnector
from app.core.config import settings
from app.core.supabase import SupabaseGateway
from app.models.article import ArticleInput, EmbeddedArticle
from app.models.classification import ClassificationOutput
from app.models.cluster import Cluster
from app.models.pipeline_run import PipelineRunStatus, PipelineRunSummary, SourceFetchStats
from app.models.synthesis import SynthesisArticle, SynthesisInput, SynthesisOutput
from app.services.article_store import fetch_existing_canonical_urls, insert_articles
from app.services.cluster_store import (
    fetch_active_cluster_arrivals,
    fetch_existing_clusters,
    persist_cluster_result,
    update_cluster_momentum,
)
from app.services.clustering import cluster_articles
from app.services.embeddings import embed_texts, format_embedding_input
from app.services.momentum import is_stale, score_momentum
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


@dataclass(frozen=True)
class MomentumStats:
    scored: int
    stale: int


@dataclass
class _RunProgress:
    """Counters accumulated as the run proceeds, so a run that dies partway still has
    something to persist. Without this the summary is only built after every stage has
    already succeeded, which means a crashed run writes no `pipeline_runs` row at all and
    the audit trail silently samples only the runs that worked."""

    articles_fetched: int = 0
    articles_classified: int = 0
    articles_skipped_known: int = 0
    clusters_created: int = 0
    clusters_updated: int = 0
    clusters_scored: int = 0
    clusters_stale: int = 0
    source_stats: dict[str, SourceFetchStats] = field(default_factory=dict)

    def to_summary(
        self,
        started_at: datetime,
        status: PipelineRunStatus,
        error_message: str | None = None,
    ) -> PipelineRunSummary:
        return PipelineRunSummary(
            started_at=started_at,
            completed_at=datetime.now(UTC),
            status=status,
            articles_fetched=self.articles_fetched,
            articles_classified=self.articles_classified,
            articles_skipped_known=self.articles_skipped_known,
            clusters_created=self.clusters_created,
            clusters_updated=self.clusters_updated,
            clusters_scored=self.clusters_scored,
            clusters_stale=self.clusters_stale,
            source_stats=self.source_stats,
            error_message=error_message,
        )


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
            key_entities=classification.key_entities,
            relevance=classification.relevance_score,
            published_at=article.published_at,
            vector=vector,
        )
        for (article, classification), vector in zip(selected, vectors, strict=True)
    ]


def _build_synthesis_input(cluster: Cluster, by_url: dict[str, ArticleInput]) -> SynthesisInput:
    articles = [
        SynthesisArticle(
            title=by_url[url].title,
            content=by_url[url].content,
            source=by_url[url].source,
        )
        for url in cluster.member_urls
        if url in by_url
    ]
    return SynthesisInput(
        articles=articles,
        key_entities=cluster.key_entities,
        domains=cluster.domains,
    )


async def _synthesize_new_clusters(
    new_clusters: Sequence[Cluster],
    classified: Sequence[tuple[ArticleInput, ClassificationOutput | None]],
) -> list[SynthesisOutput | None]:
    by_url = {article.canonical_url: article for article, _ in classified}
    interval = 60 / settings.synthesis_rpm
    syntheses: list[SynthesisOutput | None] = []
    for i, cluster in enumerate(new_clusters):
        if i > 0:
            await asyncio.sleep(interval)
        try:
            output: SynthesisOutput | None = await synthesize_cluster(
                _build_synthesis_input(cluster, by_url)
            )
        except Exception as e:
            logger.warning(
                "synthesis_failed",
                extra={"member_urls": cluster.member_urls, "error": str(e)},
            )
            output = None
        syntheses.append(output)
    return syntheses


async def _score_momentum(gateway: SupabaseGateway, now: datetime) -> MomentumStats:
    """Recompute momentum + staleness for every active cluster, not just those touched this
    run: a cluster with no new members still decays and can cross the stale line by elapsed
    time alone, so the sweep has to visit all of them. Returns scored + stale counts."""
    arrivals_by_cluster = await fetch_active_cluster_arrivals(gateway)
    stale_count = 0
    for cluster_id, arrivals in arrivals_by_cluster.items():
        score = score_momentum(arrivals, now, settings.momentum_half_life_hours)
        stale = is_stale(arrivals, now, settings.momentum_stale_hours)
        if stale:
            stale_count += 1
        await update_cluster_momentum(
            gateway,
            cluster_id,
            momentum_score=score,
            status="stale" if stale else "active",
        )
    return MomentumStats(scored=len(arrivals_by_cluster), stale=stale_count)


async def _record_run(gateway: SupabaseGateway | None, summary: PipelineRunSummary) -> None:
    """Persist the run row, swallowing its own errors. On the failure path the original
    exception is the one worth propagating; a lost audit row must not mask it."""
    if gateway is None:
        return
    try:
        await insert_pipeline_run(gateway=gateway, summary=summary)
    except Exception as exc:
        logger.warning("pipeline_run_not_recorded", extra={"error": str(exc)})


async def run_pipeline(
    connector_specs: Sequence[ConnectorSpec],
    gateway: SupabaseGateway | None = None,
) -> PipelineRunSummary:
    started_at = datetime.now(UTC)
    progress = _RunProgress()

    try:
        results = await asyncio.gather(*(_fetch_from_connector(spec) for spec in connector_specs))
        all_articles = [article for result in results for article in result.articles]
        dedup_result = _deduplicate_fetched_articles(all_articles)
        progress.articles_fetched = len(all_articles)
        progress.source_stats = {
            result.source: SourceFetchStats(
                returned=len(result.articles),
                duplicates=dedup_result.duplicates_by_source.get(result.source, 0),
                error=result.error,
            )
            for result in results
        }

        # Classify only articles we have not seen before. Re-classifying already-persisted
        # articles is the dominant recurring LLM cost, so filter against the DB first.
        to_classify = dedup_result.articles
        if gateway is not None:
            existing = await fetch_existing_canonical_urls(
                gateway, [article.canonical_url for article in to_classify]
            )
            if existing:
                to_classify = [a for a in to_classify if a.canonical_url not in existing]
                progress.articles_skipped_known = len(dedup_result.articles) - len(to_classify)
                logger.info(
                    "pipeline_skipped_known_articles",
                    extra={
                        "known": progress.articles_skipped_known,
                        "to_classify": len(to_classify),
                    },
                )

        classified_articles = await _classify_articles(to_classify)
        progress.articles_classified = sum(1 for _, c in classified_articles if c is not None)

        if gateway is not None:
            embedded = await _embed_articles(classified_articles)
            await insert_articles(
                gateway=gateway,
                articles=classified_articles,
                embeddings={item.canonical_url: item.vector for item in embedded},
            )
            existing_clusters = await fetch_existing_clusters(gateway)
            cluster_result = cluster_articles(embedded, existing_clusters)
            new_cluster_syntheses = await _synthesize_new_clusters(
                cluster_result.new_clusters, classified_articles
            )
            await persist_cluster_result(
                gateway, cluster_result, existing_clusters, embedded, new_cluster_syntheses
            )
            progress.clusters_created = len(cluster_result.new_clusters)
            progress.clusters_updated = len(cluster_result.updated)
            logger.info(
                "pipeline_synthesized_clusters",
                extra={"synthesized": sum(1 for s in new_cluster_syntheses if s is not None)},
            )
            momentum = await _score_momentum(gateway, datetime.now(UTC))
            progress.clusters_scored = momentum.scored
            progress.clusters_stale = momentum.stale
            logger.info(
                "pipeline_scored_momentum",
                extra={
                    "clusters_scored": progress.clusters_scored,
                    "clusters_stale": progress.clusters_stale,
                },
            )
    except Exception as exc:
        failed = progress.to_summary(started_at, PipelineRunStatus.FAILED, str(exc))
        logger.error(
            "pipeline_failed",
            extra={
                "error": str(exc),
                "articles_fetched": failed.articles_fetched,
                "articles_classified": failed.articles_classified,
                "clusters_created": failed.clusters_created,
            },
        )
        await _record_run(gateway, failed)
        raise

    summary = progress.to_summary(started_at, PipelineRunStatus.COMPLETED)
    await _record_run(gateway, summary)
    return summary
