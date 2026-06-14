import math
from dataclasses import dataclass

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


def _mean_centroid(vectors: list[list[float]]) -> list[float]:
    return [sum(axis) / len(vectors) for axis in zip(*vectors, strict=True)]


def cosine_similarity(vec1: list[float], vec2: list[float]) -> float:
    dot_product = sum(a * b for a, b in zip(vec1, vec2, strict=True))
    norm1 = math.sqrt(sum(a * a for a in vec1))
    norm2 = math.sqrt(sum(b * b for b in vec2))
    return dot_product / (norm1 * norm2)


def cluster_articles(
    embedded_articles: list[EmbeddedArticle], existing_clusters: list[ExistingCluster]
) -> ClusterResult:

    updated: dict[str, list[str]] = {}
    orphan_pool: list[EmbeddedArticle] = []
    forming: list[_FormingCluster] = []
    for article in embedded_articles:
        best_score = 0.0
        best_id: str | None = None
        for cluster in existing_clusters:
            score = cosine_similarity(article.vector, cluster.centroid)
            if score > best_score:
                best_score = score
                best_id = cluster.id

        if best_id is not None and best_score >= settings.cluster_existing_similarity_threshold:
            updated.setdefault(best_id, []).append(article.canonical_url)
        else:
            orphan_pool.append(article)

    for article in orphan_pool:
        best_score = 0.0
        best: _FormingCluster | None = None
        for forming_cluster in forming:
            score = cosine_similarity(article.vector, forming_cluster.centroid)
            if score > best_score:
                best_score = score
                best = forming_cluster

        if best is not None and best_score >= settings.cluster_new_similarity_threshold:
            best.member_urls.append(article.canonical_url)
            best.member_vectors.append(article.vector)
            best.centroid = _mean_centroid(best.member_vectors)
            best.domains.update(article.domains)
        else:
            forming.append(
                _FormingCluster(
                    centroid=article.vector,
                    member_urls=[article.canonical_url],
                    member_vectors=[article.vector],
                    domains=set(article.domains),
                )
            )

    # A forming cluster that never gained a second member is a singleton -> a true orphan.
    new_clusters = [
        Cluster(centroid=fc.centroid, member_urls=fc.member_urls, domains=sorted(fc.domains))
        for fc in forming
        if len(fc.member_urls) >= 2
    ]
    orphans = [fc.member_urls[0] for fc in forming if len(fc.member_urls) == 1]

    return ClusterResult(new_clusters=new_clusters, updated=updated, orphans=orphans)
