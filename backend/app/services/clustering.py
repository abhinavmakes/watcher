import math
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime, timedelta

from app.core.config import settings
from app.models.article import EmbeddedArticle
from app.models.classification import ArticleDomain
from app.models.cluster import Cluster, ClusterResult, ExistingCluster


@dataclass
class _FormingCluster:
    centroid: list[float]
    member_urls: list[str]
    member_vectors: list[list[float]]
    domains: set[ArticleDomain]
    entities: set[str]


def _mean_centroid(vectors: list[list[float]]) -> list[float]:
    return [sum(axis) / len(vectors) for axis in zip(*vectors, strict=True)]


def cosine_similarity(vec1: list[float], vec2: list[float]) -> float:
    dot_product = sum(a * b for a, b in zip(vec1, vec2, strict=True))
    norm1 = math.sqrt(sum(a * a for a in vec1))
    norm2 = math.sqrt(sum(b * b for b in vec2))
    denominator = norm1 * norm2
    if denominator == 0.0:
        # A zero vector has no direction, so it is similar to nothing. Returning 0.0 keeps
        # the article out of every merge instead of raising ZeroDivisionError mid-run — and
        # a crash here writes no pipeline_runs row at all.
        return 0.0
    return dot_product / denominator


def open_clusters(
    clusters: list[ExistingCluster],
    member_times: dict[str, list[datetime]],
    now: datetime,
    window_hours: float,
) -> list[ExistingCluster]:
    """Clusters still eligible to receive new members: the window is measured from the
    earliest member, not the newest, because measuring from the newest would let a magnet
    cluster refresh its own window on every join and never close."""
    window = timedelta(hours=window_hours)
    open_ids: list[ExistingCluster] = []
    for cluster in clusters:
        times = member_times.get(cluster.id)
        if not times:
            continue
        if now - min(times) <= window:
            open_ids.append(cluster)
    return open_ids


def _shares_entity(left: list[str], right: Iterable[str]) -> bool:
    return bool(set(left) & set(right))


def _joins(score: float, shares_entity: bool, *, high: float) -> bool:
    """Two-tier merge rule: auto-merge near-duplicates at/above ``high``, or merge a
    looser pair (down to the entity threshold) only when they share a key entity.
    Entities give recall on same-story coverage without lowering the cosine floor for
    unrelated articles, which a single threshold cannot do."""
    return score >= high or (
        score >= settings.cluster_entity_similarity_threshold and shares_entity
    )


def cluster_articles(
    embedded_articles: list[EmbeddedArticle], existing_clusters: list[ExistingCluster]
) -> ClusterResult:
    updated: dict[str, list[str]] = {}
    orphan_pool: list[EmbeddedArticle] = []

    for article in embedded_articles:
        best_score = 0.0
        best: ExistingCluster | None = None
        for cluster in existing_clusters:
            score = cosine_similarity(article.vector, cluster.centroid)
            if score > best_score:
                best_score = score
                best = cluster

        if best is not None and _joins(
            best_score,
            _shares_entity(article.key_entities, best.key_entities),
            high=settings.cluster_existing_similarity_threshold,
        ):
            updated.setdefault(best.id, []).append(article.canonical_url)
        else:
            orphan_pool.append(article)

    forming: list[_FormingCluster] = []
    for article in orphan_pool:
        best_score = 0.0
        best_forming: _FormingCluster | None = None
        for forming_cluster in forming:
            score = cosine_similarity(article.vector, forming_cluster.centroid)
            if score > best_score:
                best_score = score
                best_forming = forming_cluster

        if best_forming is not None and _joins(
            best_score,
            _shares_entity(article.key_entities, best_forming.entities),
            high=settings.cluster_new_similarity_threshold,
        ):
            best_forming.member_urls.append(article.canonical_url)
            best_forming.member_vectors.append(article.vector)
            best_forming.centroid = _mean_centroid(best_forming.member_vectors)
            best_forming.domains.update(article.domains)
            best_forming.entities.update(article.key_entities)
        else:
            forming.append(
                _FormingCluster(
                    centroid=article.vector,
                    member_urls=[article.canonical_url],
                    member_vectors=[article.vector],
                    domains=set(article.domains),
                    entities=set(article.key_entities),
                )
            )

    # A forming cluster that never gained a second member is a singleton -> a true orphan.
    new_clusters = [
        Cluster(
            centroid=fc.centroid,
            member_urls=fc.member_urls,
            domains=sorted(fc.domains),
            key_entities=sorted(fc.entities),
        )
        for fc in forming
        if len(fc.member_urls) >= 2
    ]
    orphans = [fc.member_urls[0] for fc in forming if len(fc.member_urls) == 1]

    return ClusterResult(new_clusters=new_clusters, updated=updated, orphans=orphans)
