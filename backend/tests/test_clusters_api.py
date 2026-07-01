from collections.abc import AsyncIterator
from typing import Any, cast

import httpx
import pytest
from pytest import MonkeyPatch

from app.api import clusters as clusters_api
from app.core.supabase import SupabaseGateway, get_supabase_gateway
from app.main import app
from app.models.cluster_api import ClusterCardStatus


def _card_row(cluster_id: str = "c1", momentum_score: float = 5.0) -> dict[str, Any]:
    return {
        "id": cluster_id,
        "title": "Anthropic ships a 1M-token context window",
        "summary": "Anthropic released a 1M-token Claude model.",
        "so_what": "Revisit whether your RAG layer still earns its complexity.",
        "momentum_score": momentum_score,
        "domains": ["llms"],
        "key_entities": ["anthropic"],
        "article_count": 3,
        "status": "active",
    }


@pytest.fixture
async def client() -> AsyncIterator[httpx.AsyncClient]:
    # The store is monkeypatched per test, so the gateway is never used — a dummy is fine.
    app.dependency_overrides[get_supabase_gateway] = lambda: cast(SupabaseGateway, object())
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as c:
        yield c
    app.dependency_overrides.clear()


# --- pure normalization (the core) ---


def test_normalize_momentum_maps_k_to_a_50_badge() -> None:
    assert clusters_api._normalize_momentum(5.0) == 50.0  # raw == k -> 50
    assert clusters_api._normalize_momentum(0.0) == 0.0
    assert clusters_api._normalize_momentum(15.0) == 75.0


def test_normalize_momentum_rounds_to_one_decimal() -> None:
    assert clusters_api._normalize_momentum(10.0) == 66.7  # 100*10/15 = 66.66…


def test_normalize_momentum_is_monotonic_and_bounded() -> None:
    assert clusters_api._normalize_momentum(3.0) < clusters_api._normalize_momentum(300.0) < 100


def test_row_to_card_normalizes_momentum_and_coerces_status() -> None:
    card = clusters_api._row_to_card(_card_row())

    assert card.momentum == 50.0
    assert card.status is ClusterCardStatus.ACTIVE
    assert card.key_entities == ["anthropic"]


# --- GET /clusters ---


async def test_get_clusters_returns_a_normalized_page(
    client: httpx.AsyncClient, monkeypatch: MonkeyPatch
) -> None:
    async def fake_page(
        gateway: Any, limit: int, offset: int, domain: str | None
    ) -> tuple[list[dict[str, Any]], int]:
        return [_card_row()], 1

    monkeypatch.setattr(clusters_api, "fetch_clusters_page", fake_page)

    response = await client.get("/clusters")

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    assert body["limit"] == 20 and body["offset"] == 0
    assert body["cards"][0]["momentum"] == 50.0  # normalized at the boundary
    assert "momentum_score" not in body["cards"][0]  # raw score never leaks


async def test_get_clusters_rejects_limit_over_cap(client: httpx.AsyncClient) -> None:
    response = await client.get("/clusters", params={"limit": 101})

    assert response.status_code == 422  # Query(le=100) is the in-app bound


# --- GET /clusters/{id} ---


async def test_get_cluster_detail_returns_members(
    client: httpx.AsyncClient, monkeypatch: MonkeyPatch
) -> None:
    article_row = {
        "id": "a1",
        "title": "Anthropic blog post",
        "url": "https://anthropic.com/post",
        "source": "rss",
        "published_at": "2026-06-25T10:00:00+00:00",
    }

    async def fake_detail(
        gateway: Any, cluster_id: str
    ) -> tuple[dict[str, Any], list[dict[str, Any]]] | None:
        return _card_row(cluster_id), [article_row]

    monkeypatch.setattr(clusters_api, "fetch_cluster_detail", fake_detail)

    response = await client.get("/clusters/c1")

    assert response.status_code == 200
    body = response.json()
    assert body["id"] == "c1"
    assert body["momentum"] == 50.0
    assert body["articles"][0]["id"] == "a1"
    assert body["articles"][0]["source"] == "rss"


async def test_get_cluster_detail_404_when_missing(
    client: httpx.AsyncClient, monkeypatch: MonkeyPatch
) -> None:
    async def fake_detail(
        gateway: Any, cluster_id: str
    ) -> tuple[dict[str, Any], list[dict[str, Any]]] | None:
        return None

    monkeypatch.setattr(clusters_api, "fetch_cluster_detail", fake_detail)

    response = await client.get("/clusters/does-not-exist")

    assert response.status_code == 404
    assert response.json()["detail"] == "Cluster not found"
