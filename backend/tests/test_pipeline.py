from collections.abc import Sequence
from datetime import UTC, datetime, timedelta
from typing import cast

import pytest

from app.core.supabase import SupabaseGateway
from app.models.article import ArticleInput, EmbeddedArticle
from app.models.classification import ArticleDomain, ClassificationOutput
from app.models.cluster import Cluster, ClusterResult, ExistingCluster
from app.models.pipeline_run import PipelineRunStatus, PipelineRunSummary
from app.models.synthesis import SynthesisOutput
from worker.pipeline import (
    ConnectorSpec,
    _build_synthesis_input,
    _deduplicate_fetched_articles,
    _redact_urls,
    run_pipeline,
)


def test_redact_urls_keeps_host_drops_path_and_query() -> None:
    message = "Connect error for https://newsletter.example.com/feed?token=secret123 (timeout)"

    expected = "Connect error for https://newsletter.example.com... (timeout)"
    assert _redact_urls(message) == expected
    # Credentials in the URL are the thing worth redacting; the host is not.
    assert _redact_urls("GET https://u:pw@feed.example/x?t=1 failed") == (
        "GET https://feed.example... failed"
    )


@pytest.fixture(autouse=True)
def _stub_classifier(monkeypatch: pytest.MonkeyPatch) -> None:
    """Patch classify_article, the rate-limit sleep, and embed_texts so pipeline tests stay
    hermetic and fast."""

    async def fake_classify_article(
        article: ArticleInput, *, usage: object | None = None
    ) -> ClassificationOutput:
        return ClassificationOutput(
            domains=[ArticleDomain.LLMS],
            relevance_score=0.5,
            is_noise=False,
            reason="stub",
        )

    async def fake_sleep(seconds: float) -> None:
        return None

    async def fake_embed_texts(texts: list[str]) -> list[list[float]]:
        return [[0.0] * 8 for _ in texts]

    monkeypatch.setattr("worker.pipeline.classify_article", fake_classify_article)
    monkeypatch.setattr("worker.pipeline.asyncio.sleep", fake_sleep)
    monkeypatch.setattr("worker.pipeline.embed_texts", fake_embed_texts)


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
    assert summary.articles_classified == 2
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
    hn_connector = FakeConnector([_article("HN story", source="hn", canonical_url=canonical_url)])
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


@pytest.mark.asyncio
async def test_run_pipeline_inserts_deduplicated_articles_when_gateway_is_provided(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    canonical_url = "https://example.com/shared-story"
    first_article = _article("HN story", source="hn", canonical_url=canonical_url)
    duplicate_article = _article("RSS story", source="rss", canonical_url=canonical_url)
    inserted_pairs: list[tuple[ArticleInput, ClassificationOutput | None]] = []
    persisted_summaries: list[PipelineRunSummary] = []
    captured_embeddings: dict[str, list[float]] = {}

    async def fake_insert_articles(
        gateway: SupabaseGateway,
        articles: Sequence[tuple[ArticleInput, ClassificationOutput | None]],
        embeddings: dict[str, list[float]] | None = None,
    ) -> int:
        inserted_pairs.extend(articles)
        if embeddings:
            captured_embeddings.update(embeddings)
        return len(articles)

    monkeypatch.setattr("worker.pipeline.insert_articles", fake_insert_articles)

    async def fake_insert_pipeline_run(
        gateway: SupabaseGateway,
        summary: PipelineRunSummary,
    ) -> None:
        persisted_summaries.append(summary)

    async def fake_fetch_existing(
        gateway: SupabaseGateway, canonical_urls: Sequence[str]
    ) -> set[str]:
        return set()

    monkeypatch.setattr("worker.pipeline.insert_pipeline_run", fake_insert_pipeline_run)
    monkeypatch.setattr("worker.pipeline.fetch_existing_canonical_urls", fake_fetch_existing)

    cluster_results: list[ClusterResult] = []

    async def fake_fetch_existing_clusters(gateway: SupabaseGateway) -> list[ExistingCluster]:
        return []

    async def fake_persist_cluster_result(
        gateway: SupabaseGateway,
        result: ClusterResult,
        existing_clusters: Sequence[ExistingCluster],
        embedded: Sequence[EmbeddedArticle],
        new_cluster_syntheses: Sequence[SynthesisOutput | None] | None = None,
    ) -> None:
        cluster_results.append(result)

    monkeypatch.setattr("worker.pipeline.fetch_existing_clusters", fake_fetch_existing_clusters)
    monkeypatch.setattr("worker.pipeline.persist_cluster_result", fake_persist_cluster_result)

    async def fake_fetch_arrivals(gateway: SupabaseGateway) -> dict[str, list[datetime]]:
        return {}

    monkeypatch.setattr("worker.pipeline.fetch_active_cluster_arrivals", fake_fetch_arrivals)

    summary = await run_pipeline(
        [
            ConnectorSpec(name="hn", connector=FakeConnector([first_article]), limit=10),
            ConnectorSpec(name="rss", connector=FakeConnector([duplicate_article]), limit=10),
        ],
        gateway=cast(SupabaseGateway, object()),
    )

    assert summary.articles_fetched == 2
    assert summary.articles_classified == 1
    assert [article for article, _ in inserted_pairs] == [first_article]
    assert all(classification is not None for _, classification in inserted_pairs)
    assert captured_embeddings == {canonical_url: [0.0] * 8}
    assert len(cluster_results) == 1
    assert persisted_summaries == [summary]
    assert summary.source_stats["hn"].duplicates == 0
    assert summary.source_stats["rss"].duplicates == 1


@pytest.mark.asyncio
async def test_run_pipeline_skips_articles_already_in_db(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    known = _article("Known story", source="hn", canonical_url="https://example.com/known")
    fresh = _article("Fresh story", source="hn", canonical_url="https://example.com/fresh")
    inserted_pairs: list[tuple[ArticleInput, ClassificationOutput | None]] = []

    async def fake_fetch_existing(
        gateway: SupabaseGateway, canonical_urls: Sequence[str]
    ) -> set[str]:
        return {"https://example.com/known"}

    async def fake_insert_articles(
        gateway: SupabaseGateway,
        articles: Sequence[tuple[ArticleInput, ClassificationOutput | None]],
        embeddings: dict[str, list[float]] | None = None,
    ) -> int:
        inserted_pairs.extend(articles)
        return len(articles)

    async def fake_insert_pipeline_run(
        gateway: SupabaseGateway,
        summary: PipelineRunSummary,
    ) -> None:
        return None

    monkeypatch.setattr("worker.pipeline.fetch_existing_canonical_urls", fake_fetch_existing)
    monkeypatch.setattr("worker.pipeline.insert_articles", fake_insert_articles)
    monkeypatch.setattr("worker.pipeline.insert_pipeline_run", fake_insert_pipeline_run)

    async def fake_fetch_existing_clusters(gateway: SupabaseGateway) -> list[ExistingCluster]:
        return []

    async def fake_persist_cluster_result(
        gateway: SupabaseGateway,
        result: ClusterResult,
        existing_clusters: Sequence[ExistingCluster],
        embedded: Sequence[EmbeddedArticle],
        new_cluster_syntheses: Sequence[SynthesisOutput | None] | None = None,
    ) -> None:
        return None

    monkeypatch.setattr("worker.pipeline.fetch_existing_clusters", fake_fetch_existing_clusters)
    monkeypatch.setattr("worker.pipeline.persist_cluster_result", fake_persist_cluster_result)

    async def fake_fetch_arrivals(gateway: SupabaseGateway) -> dict[str, list[datetime]]:
        return {}

    monkeypatch.setattr("worker.pipeline.fetch_active_cluster_arrivals", fake_fetch_arrivals)

    summary = await run_pipeline(
        [ConnectorSpec(name="hn", connector=FakeConnector([known, fresh]), limit=10)],
        gateway=cast(SupabaseGateway, object()),
    )

    assert summary.articles_fetched == 2
    assert summary.articles_classified == 1
    assert summary.articles_skipped_known == 1
    assert [article for article, _ in inserted_pairs] == [fresh]


@pytest.mark.asyncio
async def test_run_pipeline_skips_insert_when_gateway_is_not_provided(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    insert_called = False

    async def fake_insert_articles(
        gateway: SupabaseGateway,
        articles: Sequence[ArticleInput],
    ) -> int:
        nonlocal insert_called
        insert_called = True
        return len(articles)

    monkeypatch.setattr("worker.pipeline.insert_articles", fake_insert_articles)

    summary = await run_pipeline(
        [ConnectorSpec(name="hn", connector=FakeConnector([_article("HN story")]), limit=10)]
    )

    assert summary.articles_fetched == 1
    assert insert_called is False


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


def test_build_synthesis_input_maps_members_and_drops_unresolved_urls() -> None:
    first = _article("First", source="rss", canonical_url="u-a")
    second = _article("Second", source="hn", canonical_url="u-b")
    by_url = {first.canonical_url: first, second.canonical_url: second}
    cluster = Cluster(
        centroid=[0.0],
        member_urls=["u-a", "u-b", "u-missing"],
        domains=[ArticleDomain.LLMS],
        key_entities=["anthropic"],
    )

    result = _build_synthesis_input(cluster, by_url)

    # One SynthesisArticle per resolvable member; the unknown url is dropped, not an error.
    assert [article.title for article in result.articles] == ["First", "Second"]
    assert [article.source for article in result.articles] == ["rss", "hn"]
    assert result.articles[0].content == "Article body"
    # Cluster carries the unioned domains/entities; synthesis input reuses them as-is.
    assert result.domains == [ArticleDomain.LLMS]
    assert result.key_entities == ["anthropic"]


@pytest.mark.asyncio
async def test_run_pipeline_scores_momentum_and_marks_stale(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def fake_insert_articles(
        gateway: SupabaseGateway,
        articles: Sequence[tuple[ArticleInput, ClassificationOutput | None]],
        embeddings: dict[str, list[float]] | None = None,
    ) -> int:
        return len(articles)

    async def fake_fetch_existing(
        gateway: SupabaseGateway, canonical_urls: Sequence[str]
    ) -> set[str]:
        return set()

    async def fake_insert_pipeline_run(
        gateway: SupabaseGateway, summary: PipelineRunSummary
    ) -> None:
        return None

    async def fake_fetch_existing_clusters(gateway: SupabaseGateway) -> list[ExistingCluster]:
        return []

    async def fake_persist_cluster_result(
        gateway: SupabaseGateway,
        result: ClusterResult,
        existing_clusters: Sequence[ExistingCluster],
        embedded: Sequence[EmbeddedArticle],
        new_cluster_syntheses: Sequence[SynthesisOutput | None] | None = None,
    ) -> None:
        return None

    async def fake_fetch_arrivals(gateway: SupabaseGateway) -> dict[str, list[datetime]]:
        now = datetime.now(UTC)
        return {"fresh": [now], "stale-one": [now - timedelta(hours=72)]}

    captured: list[tuple[str, float, str]] = []

    async def fake_update(
        gateway: SupabaseGateway, cluster_id: str, momentum_score: float, status: str
    ) -> None:
        captured.append((cluster_id, momentum_score, status))

    monkeypatch.setattr("worker.pipeline.insert_articles", fake_insert_articles)
    monkeypatch.setattr("worker.pipeline.fetch_existing_canonical_urls", fake_fetch_existing)
    monkeypatch.setattr("worker.pipeline.insert_pipeline_run", fake_insert_pipeline_run)
    monkeypatch.setattr("worker.pipeline.fetch_existing_clusters", fake_fetch_existing_clusters)
    monkeypatch.setattr("worker.pipeline.persist_cluster_result", fake_persist_cluster_result)
    monkeypatch.setattr("worker.pipeline.fetch_active_cluster_arrivals", fake_fetch_arrivals)
    monkeypatch.setattr("worker.pipeline.update_cluster_momentum", fake_update)

    summary = await run_pipeline(
        [ConnectorSpec(name="hn", connector=FakeConnector([_article("HN story")]), limit=10)],
        gateway=cast(SupabaseGateway, object()),
    )

    by_id = {cid: (score, status) for cid, score, status in captured}
    assert by_id["stale-one"][1] == "stale"
    assert by_id["fresh"][1] == "active"
    # Sum-of-decay: a fresh member outscores one that is 72h old.
    assert by_id["fresh"][0] > by_id["stale-one"][0]
    # Both counts land in the run summary for the pipeline_runs audit row.
    assert summary.clusters_scored == 2
    assert summary.clusters_stale == 1


def _failure_gateway_patches(
    monkeypatch: pytest.MonkeyPatch, persisted: list[PipelineRunSummary]
) -> None:
    async def fake_fetch_existing(
        gateway: SupabaseGateway, canonical_urls: Sequence[str]
    ) -> set[str]:
        return set()

    async def exploding_insert_articles(
        gateway: SupabaseGateway,
        articles: Sequence[tuple[ArticleInput, ClassificationOutput | None]],
        embeddings: dict[str, list[float]] | None = None,
    ) -> int:
        raise RuntimeError("supabase unreachable")

    async def fake_insert_pipeline_run(
        gateway: SupabaseGateway, summary: PipelineRunSummary
    ) -> None:
        persisted.append(summary)

    monkeypatch.setattr("worker.pipeline.fetch_existing_canonical_urls", fake_fetch_existing)
    monkeypatch.setattr("worker.pipeline.insert_articles", exploding_insert_articles)
    monkeypatch.setattr("worker.pipeline.insert_pipeline_run", fake_insert_pipeline_run)


@pytest.mark.asyncio
async def test_run_pipeline_records_a_failed_run_with_the_counts_it_reached(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # A crash used to leave no pipeline_runs row at all, because the summary was only built
    # after every stage had already succeeded — so the audit trail only sampled runs that worked.
    persisted: list[PipelineRunSummary] = []
    _failure_gateway_patches(monkeypatch, persisted)

    with pytest.raises(RuntimeError, match="supabase unreachable"):
        await run_pipeline(
            [ConnectorSpec(name="hn", connector=FakeConnector([_article("Story")]), limit=10)],
            gateway=cast(SupabaseGateway, object()),
        )

    assert len(persisted) == 1
    failed = persisted[0]
    assert failed.status is PipelineRunStatus.FAILED
    assert failed.error_message == "supabase unreachable"
    # The work done before the crash survives rather than being lost with the run.
    assert failed.articles_fetched == 1
    assert failed.articles_classified == 1
    assert failed.clusters_created == 0
    assert failed.source_stats["hn"].returned == 1
    assert failed.completed_at is not None


@pytest.mark.asyncio
async def test_run_pipeline_does_not_let_a_failed_audit_write_mask_the_real_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    persisted: list[PipelineRunSummary] = []
    _failure_gateway_patches(monkeypatch, persisted)

    async def exploding_insert_pipeline_run(
        gateway: SupabaseGateway, summary: PipelineRunSummary
    ) -> None:
        raise RuntimeError("audit table is also down")

    monkeypatch.setattr("worker.pipeline.insert_pipeline_run", exploding_insert_pipeline_run)

    # The pipeline's own failure is the diagnostic worth propagating, not the bookkeeping one.
    with pytest.raises(RuntimeError, match="supabase unreachable"):
        await run_pipeline(
            [ConnectorSpec(name="hn", connector=FakeConnector([_article("Story")]), limit=10)],
            gateway=cast(SupabaseGateway, object()),
        )


@pytest.mark.asyncio
async def test_run_pipeline_marks_a_successful_run_completed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    summary = await run_pipeline(
        [ConnectorSpec(name="hn", connector=FakeConnector([_article("Story")]), limit=10)]
    )

    assert summary.status is PipelineRunStatus.COMPLETED
    assert summary.error_message is None
