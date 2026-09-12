import pytest

from app.models.article import EmbeddedArticle
from app.models.classification import ArticleDomain
from app.models.cluster import ExistingCluster
from app.services.clustering import _mean_centroid, cluster_articles, cosine_similarity


def _embedded(
    url: str,
    vector: list[float],
    domains: list[ArticleDomain],
    relevance: float = 0.5,
    key_entities: list[str] | None = None,
) -> EmbeddedArticle:
    return EmbeddedArticle(
        canonical_url=url,
        title=url,
        domains=domains,
        key_entities=key_entities or [],
        relevance=relevance,
        vector=vector,
    )


def test_cosine_similarity_identical_and_orthogonal() -> None:
    assert cosine_similarity([1.0, 0.0], [1.0, 0.0]) == pytest.approx(1.0)
    assert cosine_similarity([1.0, 0.0], [0.0, 1.0]) == pytest.approx(0.0)


def test_mean_centroid_averages_per_axis() -> None:
    assert _mean_centroid([[1.0, 0.0, 0.0], [1.0, 0.5, 0.0]]) == pytest.approx([1.0, 0.25, 0.0])


def test_empty_input_returns_empty_result() -> None:
    result = cluster_articles([], [])

    assert result.new_clusters == []
    assert result.updated == {}
    assert result.orphans == []


def test_phase_b_groups_similar_orphans_and_isolates_far_ones() -> None:
    # a, b point in nearly the same direction (cosine ~0.89 >= 0.83) -> one cluster.
    # c is orthogonal to both -> stays a singleton -> orphan.
    a = _embedded("https://a", [1.0, 0.0, 0.0], [ArticleDomain.LLMS])
    b = _embedded("https://b", [1.0, 0.5, 0.0], [ArticleDomain.AI_AGENTS])
    c = _embedded("https://c", [0.0, 1.0, 0.0], [ArticleDomain.RESEARCH])

    result = cluster_articles([a, b, c], [])

    assert result.updated == {}
    assert len(result.new_clusters) == 1
    cluster = result.new_clusters[0]
    assert cluster.member_urls == ["https://a", "https://b"]
    assert cluster.centroid == pytest.approx([1.0, 0.25, 0.0])
    assert cluster.domains == [ArticleDomain.AI_AGENTS, ArticleDomain.LLMS]
    assert result.orphans == ["https://c"]


def test_phase_a_joins_existing_cluster() -> None:
    # d is close to the existing centroid (cosine ~0.89 >= 0.85) -> joins it, no new cluster.
    d = _embedded("https://d", [0.0, 0.5, 1.0], [ArticleDomain.INFRA])
    existing = ExistingCluster(id="cluster-existing", centroid=[0.0, 0.0, 1.0], article_count=1)

    result = cluster_articles([d], [existing])

    assert result.updated == {"cluster-existing": ["https://d"]}
    assert result.new_clusters == []
    assert result.orphans == []


def test_full_run_splits_across_both_phases() -> None:
    a = _embedded("https://a", [1.0, 0.0, 0.0], [ArticleDomain.LLMS])
    b = _embedded("https://b", [1.0, 0.5, 0.0], [ArticleDomain.AI_AGENTS])
    c = _embedded("https://c", [0.0, 1.0, 0.0], [ArticleDomain.RESEARCH])
    d = _embedded("https://d", [0.0, 0.5, 1.0], [ArticleDomain.INFRA])
    existing = ExistingCluster(id="cluster-existing", centroid=[0.0, 0.0, 1.0], article_count=1)

    result = cluster_articles([a, b, c, d], [existing])

    assert result.updated == {"cluster-existing": ["https://d"]}
    assert [cl.member_urls for cl in result.new_clusters] == [["https://a", "https://b"]]
    assert result.orphans == ["https://c"]


def test_entity_anchored_merge_below_cosine_threshold() -> None:
    # cosine ~0.74 sits below CLUSTER_NEW (0.75), but a shared entity merges them.
    a = _embedded("https://a", [1.0, 0.0, 0.0], [ArticleDomain.LLMS], key_entities=["anthropic"])
    b = _embedded("https://b", [1.0, 0.9, 0.0], [ArticleDomain.LLMS], key_entities=["anthropic"])

    result = cluster_articles([a, b], [])

    assert len(result.new_clusters) == 1
    assert result.new_clusters[0].member_urls == ["https://a", "https://b"]
    assert result.new_clusters[0].key_entities == ["anthropic"]
    assert result.orphans == []


def test_no_merge_below_cosine_without_shared_entity() -> None:
    # Same ~0.74 cosine, but no shared entity -> they stay apart (precision preserved).
    a = _embedded("https://a", [1.0, 0.0, 0.0], [ArticleDomain.LLMS], key_entities=["openai"])
    b = _embedded("https://b", [1.0, 0.9, 0.0], [ArticleDomain.LLMS], key_entities=["mistral"])

    result = cluster_articles([a, b], [])

    assert result.new_clusters == []
    assert sorted(result.orphans) == ["https://a", "https://b"]


def test_phase_a_entity_anchored_join_below_cosine_threshold() -> None:
    article = _embedded(
        "https://d", [1.0, 0.9, 0.0], [ArticleDomain.LLMS], key_entities=["anthropic"]
    )
    existing = ExistingCluster(
        id="c1", centroid=[1.0, 0.0, 0.0], article_count=2, key_entities=["anthropic"]
    )

    result = cluster_articles([article], [existing])

    assert result.updated == {"c1": ["https://d"]}
    assert result.new_clusters == []


def test_cosine_similarity_returns_zero_for_a_zero_vector() -> None:
    # An all-zero embedding used to raise ZeroDivisionError mid-run, which killed the
    # pipeline before it could write a pipeline_runs row.
    assert cosine_similarity([0.0, 0.0], [1.0, 0.0]) == 0.0
    assert cosine_similarity([0.0, 0.0], [0.0, 0.0]) == 0.0


def test_cluster_articles_survives_a_zero_vector() -> None:
    zero = _embedded("https://example.com/zero", [0.0, 0.0], [ArticleDomain.LLMS])
    normal = _embedded("https://example.com/normal", [1.0, 0.0], [ArticleDomain.LLMS])

    result = cluster_articles([zero, normal], [])

    # Similar to nothing, so it stays a singleton rather than crashing the run.
    assert result.new_clusters == []
    assert sorted(result.orphans) == [
        "https://example.com/normal",
        "https://example.com/zero",
    ]
