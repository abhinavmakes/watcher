from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query

from app.core.supabase import SupabaseGateway, get_supabase_gateway
from app.models.cluster_api import ClusterArticleRef, ClusterCard, ClusterDetail, ClusterPage
from app.services.cluster_store import fetch_cluster_detail, fetch_clusters_page

router = APIRouter()

# k = raw momentum that maps to a 50 badge; raw ≈ fresh-article count, so 5 reads as a "mid" story.
_MOMENTUM_K = 5.0


def _normalize_momentum(raw: float, k: float = _MOMENTUM_K) -> float:
    return round(100 * raw / (raw + k), 1)


def _row_to_card(row: dict[str, Any]) -> ClusterCard:
    return ClusterCard(
        id=row["id"],
        title=row["title"],
        summary=row["summary"],
        so_what=row["so_what"],
        momentum=_normalize_momentum(row["momentum_score"]),
        domains=row["domains"],
        key_entities=row["key_entities"],
        article_count=row["article_count"],
        status=row["status"],
    )


def _row_to_detail(row: dict[str, Any], articles: list[dict[str, Any]]) -> ClusterDetail:
    return ClusterDetail(
        **_row_to_card(row).model_dump(),
        articles=[ClusterArticleRef(**article) for article in articles],
    )


@router.get("/clusters")
async def get_clusters(
    gateway: Annotated[SupabaseGateway, Depends(get_supabase_gateway)],
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
    domain: Annotated[str | None, Query()] = None,
) -> ClusterPage:
    rows, total = await fetch_clusters_page(gateway, limit, offset, domain)
    return ClusterPage(
        cards=[_row_to_card(row) for row in rows],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/clusters/{cluster_id}")
async def get_cluster(
    cluster_id: UUID,
    gateway: Annotated[SupabaseGateway, Depends(get_supabase_gateway)],
) -> ClusterDetail:
    detail = await fetch_cluster_detail(gateway, str(cluster_id))
    if detail is None:
        raise HTTPException(status_code=404, detail="Cluster not found")
    cluster_row, article_rows = detail
    return _row_to_detail(cluster_row, article_rows)
