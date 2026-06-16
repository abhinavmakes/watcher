import json
from collections.abc import Sequence

from app.core.supabase import SupabaseGateway
from app.models.article import EmbeddedArticle
from app.models.cluster import ClusterResult, ExistingCluster

# postgREST sends `in.(...)` filters in the request URL; long canonical URLs overflow the
# gateway's URL-length limit, so query in batches.
_IN_FILTER_BATCH_SIZE = 20


def _parse_vector(raw: object) -> list[float]:
    """pgvector columns come back from postgREST as a "[...]" string; normalize to floats."""
    values = json.loads(raw) if isinstance(raw, str) else raw
    if not isinstance(values, (list, tuple)):
        raise ValueError(f"Unexpected vector payload: {type(values)!r}")
    return [float(x) for x in values]


def _update_centroid(
    old_centroid: list[float], old_count: int, new_vectors: list[list[float]]
) -> tuple[list[float], int]:
    """Running-mean update: equivalent to re-averaging all members, but only needs the
    stored centroid + count, not a re-fetch of every existing member vector."""
    total = old_count + len(new_vectors)
    new_centroid = [
        (old_centroid[i] * old_count + sum(v[i] for v in new_vectors)) / total
        for i in range(len(old_centroid))
    ]
    return new_centroid, total


async def fetch_existing_clusters(gateway: SupabaseGateway) -> list[ExistingCluster]:
    result = await (
        gateway.table("clusters")
        .select("id, centroid, article_count, key_entities")
        .eq("status", "active")
        .execute()
    )
    clusters: list[ExistingCluster] = []
    for row in result.data:
        if row.get("centroid") is None:
            continue
        clusters.append(
            ExistingCluster(
                id=row["id"],
                centroid=_parse_vector(row["centroid"]),
                article_count=row["article_count"],
                key_entities=row.get("key_entities") or [],
            )
        )
    return clusters


async def _fetch_article_ids(
    gateway: SupabaseGateway, canonical_urls: list[str]
) -> dict[str, str]:
    # Batch the `in.(...)` filter — long Google News URLs overflow the request URL limit.
    ids: dict[str, str] = {}
    for start in range(0, len(canonical_urls), _IN_FILTER_BATCH_SIZE):
        batch = canonical_urls[start : start + _IN_FILTER_BATCH_SIZE]
        result = await (
            gateway.table("articles")
            .select("id, canonical_url")
            .in_("canonical_url", batch)
            .execute()
        )
        ids.update({row["canonical_url"]: row["id"] for row in result.data})
    return ids


async def _link_members(
    gateway: SupabaseGateway,
    cluster_id: str,
    member_urls: Sequence[str],
    article_ids: dict[str, str],
) -> None:
    rows = [
        {"cluster_id": cluster_id, "article_id": article_ids[url]}
        for url in member_urls
        if url in article_ids
    ]
    if not rows:
        return
    await (
        gateway.table("cluster_articles")
        .upsert(rows, on_conflict="cluster_id,article_id", ignore_duplicates=True)
        .execute()
    )


async def persist_cluster_result(
    gateway: SupabaseGateway,
    result: ClusterResult,
    existing_clusters: Sequence[ExistingCluster],
    embedded: Sequence[EmbeddedArticle],
) -> None:
    by_url = {item.canonical_url: item for item in embedded}
    existing_by_id = {cluster.id: cluster for cluster in existing_clusters}

    member_urls = [url for cluster in result.new_clusters for url in cluster.member_urls]
    member_urls += [url for urls in result.updated.values() for url in urls]
    if not member_urls:
        return

    article_ids = await _fetch_article_ids(gateway, member_urls)

    for cluster in result.new_clusters:
        title_url = max(cluster.member_urls, key=lambda url: by_url[url].relevance)
        row = {
            "title": by_url[title_url].title,
            "centroid": cluster.centroid,
            "domains": [str(domain) for domain in cluster.domains],
            "key_entities": cluster.key_entities,
            "article_count": len(cluster.member_urls),
            "signal_type": "cluster",
        }
        insert_result = await gateway.table("clusters").insert(row).execute()
        new_id = insert_result.data[0]["id"]
        await _link_members(gateway, new_id, cluster.member_urls, article_ids)

    for cluster_id, urls in result.updated.items():
        existing = existing_by_id[cluster_id]
        new_vectors = [by_url[url].vector for url in urls]
        new_centroid, new_count = _update_centroid(
            existing.centroid, existing.article_count, new_vectors
        )
        merged_entities = set(existing.key_entities)
        for url in urls:
            merged_entities.update(by_url[url].key_entities)
        await (
            gateway.table("clusters")
            .update(
                {
                    "centroid": new_centroid,
                    "article_count": new_count,
                    "key_entities": sorted(merged_entities),
                }
            )
            .eq("id", cluster_id)
            .execute()
        )
        await _link_members(gateway, cluster_id, urls, article_ids)
