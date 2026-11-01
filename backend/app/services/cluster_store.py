import json
from collections.abc import Sequence
from datetime import UTC, datetime
from typing import Any

from app.core.supabase import SupabaseGateway
from app.models.article import EmbeddedArticle
from app.models.cluster import ClusterResult, ExistingCluster
from app.models.synthesis import SynthesisArticle, SynthesisInput, SynthesisOutput

# postgREST sends `in.(...)` filters in the request URL; long canonical URLs overflow the
# gateway's URL-length limit, so query in batches.
_IN_FILTER_BATCH_SIZE = 20

_CLUSTER_CARD_COLUMNS = (
    "id, title, summary, so_what, momentum_score, domains, key_entities, article_count, status"
)


def _parse_vector(raw: object) -> list[float]:
    """pgvector columns come back from postgREST as a "[...]" string; normalize to floats."""
    values = json.loads(raw) if isinstance(raw, str) else raw
    if not isinstance(values, (list, tuple)):
        raise ValueError(f"Unexpected vector payload: {type(values)!r}")
    return [float(x) for x in values]


def _parse_timestamp(raw: str) -> datetime:
    """postgREST returns timestamptz as an ISO string; normalize to an aware UTC datetime."""
    parsed = datetime.fromisoformat(raw)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed


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


def _member_time(added_at: str, article: dict[str, Any] | None) -> datetime:
    """A member's effective event time: its article's ``published_at``, or ``added_at``
    when earlier or when the article has no ``published_at``. `min` guards against a feed
    with a timezone bug reporting a publish date after the pipeline actually saw it."""
    added_at_ts = _parse_timestamp(added_at)
    published_at = article.get("published_at") if article else None
    if published_at is None:
        return added_at_ts
    return min(_parse_timestamp(published_at), added_at_ts)


async def fetch_active_cluster_arrivals(
    gateway: SupabaseGateway,
) -> dict[str, list[datetime]]:
    """Per active cluster, its members' effective event times — the input momentum scores.
    Stale clusters are excluded; momentum only re-ranks the live feed."""
    active = await gateway.table("clusters").select("id").eq("status", "active").execute()
    arrivals: dict[str, list[datetime]] = {row["id"]: [] for row in active.data}
    cluster_ids = list(arrivals)
    for start in range(0, len(cluster_ids), _IN_FILTER_BATCH_SIZE):
        batch = cluster_ids[start : start + _IN_FILTER_BATCH_SIZE]
        result = await (
            gateway.table("cluster_articles")
            .select("cluster_id, added_at, articles(published_at)")
            .in_("cluster_id", batch)
            .execute()
        )
        for row in result.data:
            cluster_id = row["cluster_id"]
            added_at = row.get("added_at")
            if cluster_id not in arrivals or added_at is None:
                continue
            arrivals[cluster_id].append(_member_time(added_at, row.get("articles")))
    return arrivals


async def fetch_resynthesis_inputs(
    gateway: SupabaseGateway, cluster_ids: Sequence[str], max_articles: int
) -> dict[str, SynthesisInput]:
    """Per cluster, a SynthesisInput built from its newest ``max_articles`` members —
    newest first, because a headline rewrite has to describe what the story is now, not
    what it looked like when the oldest member joined."""
    clusters_by_id: dict[str, dict[str, Any]] = {}
    members_by_cluster: dict[str, list[tuple[datetime, dict[str, Any]]]] = {
        cluster_id: [] for cluster_id in cluster_ids
    }
    for start in range(0, len(cluster_ids), _IN_FILTER_BATCH_SIZE):
        batch = cluster_ids[start : start + _IN_FILTER_BATCH_SIZE]
        clusters_result = await (
            gateway.table("clusters").select("id, key_entities, domains").in_("id", batch).execute()
        )
        clusters_by_id.update({row["id"]: row for row in clusters_result.data})

        members_result = await (
            gateway.table("cluster_articles")
            .select("cluster_id, added_at, articles(title, content, source, published_at)")
            .in_("cluster_id", batch)
            .execute()
        )
        for row in members_result.data:
            cluster_id = row["cluster_id"]
            article = row.get("articles")
            if cluster_id not in members_by_cluster or article is None:
                continue
            member_time = _member_time(row["added_at"], article)
            members_by_cluster[cluster_id].append((member_time, article))

    inputs: dict[str, SynthesisInput] = {}
    for cluster_id, members in members_by_cluster.items():
        cluster = clusters_by_id.get(cluster_id)
        if cluster is None or not members:
            continue
        members.sort(key=lambda pair: pair[0], reverse=True)
        newest = [article for _, article in members[:max_articles]]
        inputs[cluster_id] = SynthesisInput(
            articles=[
                SynthesisArticle(
                    title=article["title"], content=article.get("content"), source=article["source"]
                )
                for article in newest
            ],
            key_entities=cluster.get("key_entities") or [],
            domains=cluster.get("domains") or [],
        )
    return inputs


async def update_cluster_synthesis(
    gateway: SupabaseGateway, cluster_id: str, synthesis: SynthesisOutput
) -> None:
    await (
        gateway.table("clusters")
        .update(
            {"title": synthesis.title, "summary": synthesis.summary, "so_what": synthesis.so_what}
        )
        .eq("id", cluster_id)
        .execute()
    )


async def update_cluster_momentum(
    gateway: SupabaseGateway,
    cluster_id: str,
    momentum_score: float,
    status: str,
) -> None:
    await (
        gateway.table("clusters")
        .update({"momentum_score": momentum_score, "status": status})
        .eq("id", cluster_id)
        .execute()
    )


async def _fetch_article_ids(gateway: SupabaseGateway, canonical_urls: list[str]) -> dict[str, str]:
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
    new_cluster_syntheses: Sequence[SynthesisOutput | None] | None = None,
) -> None:
    by_url = {item.canonical_url: item for item in embedded}
    existing_by_id = {cluster.id: cluster for cluster in existing_clusters}

    member_urls = [url for cluster in result.new_clusters for url in cluster.member_urls]
    member_urls += [url for urls in result.updated.values() for url in urls]
    if not member_urls:
        return

    article_ids = await _fetch_article_ids(gateway, member_urls)

    for index, cluster in enumerate(result.new_clusters):
        synthesis = new_cluster_syntheses[index] if new_cluster_syntheses is not None else None
        # Synthesis title names the actual event; fall back to the highest-relevance
        # member headline when synthesis is unavailable (failed or skipped).
        title_url = max(cluster.member_urls, key=lambda url: by_url[url].relevance)
        row: dict[str, object] = {
            "title": synthesis.title if synthesis is not None else by_url[title_url].title,
            "centroid": cluster.centroid,
            "domains": [str(domain) for domain in cluster.domains],
            "key_entities": cluster.key_entities,
            "article_count": len(cluster.member_urls),
            "signal_type": "cluster",
        }
        if synthesis is not None:
            row["summary"] = synthesis.summary
            row["so_what"] = synthesis.so_what
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


async def fetch_clusters_page(
    gateway: SupabaseGateway, limit: int, offset: int, domain: str | None
) -> tuple[list[dict[str, Any]], int]:
    query = (
        gateway.table("clusters")
        .select(_CLUSTER_CARD_COLUMNS, count="exact")
        .eq("status", "active")
    )
    if domain is not None:
        query = query.contains("domains", [domain])
    query = query.order("momentum_score", desc=True).range(offset, offset + limit - 1)
    result = await query.execute()
    return result.data, result.count


async def fetch_cluster_detail(
    gateway: SupabaseGateway, cluster_id: str
) -> tuple[dict[str, Any], list[dict[str, Any]]] | None:
    """A cluster by id plus its member articles. No status filter — a permalink to a
    cluster that later went stale still resolves; hide-stale governs the feed, not
    direct lookups. Returns None when the id is unknown (the API translates that to 404)."""
    cluster = await (
        gateway.table("clusters").select(_CLUSTER_CARD_COLUMNS).eq("id", cluster_id).execute()
    )
    if not cluster.data:
        return None
    links = await (
        gateway.table("cluster_articles")
        .select("article_id")
        .eq("cluster_id", cluster_id)
        .execute()
    )
    article_ids = [row["article_id"] for row in links.data]
    if not article_ids:
        return cluster.data[0], []
    articles = await (
        gateway.table("articles")
        .select("id, title, url, source, published_at")
        .in_("id", article_ids)
        .order("published_at", desc=True)
        .execute()
    )
    return cluster.data[0], articles.data
