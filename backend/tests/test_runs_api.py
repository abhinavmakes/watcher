from collections.abc import AsyncIterator
from typing import Any, cast

import httpx
import pytest
from pytest import MonkeyPatch

from app.api import runs as runs_api
from app.core.supabase import SupabaseGateway, get_supabase_gateway
from app.main import app


def _run_row(run_id: str = "r1") -> dict[str, Any]:
    return {
        "id": run_id,
        "started_at": "2026-09-13T08:00:00+00:00",
        "completed_at": "2026-09-13T08:25:00+00:00",
        "status": "completed",
        "articles_fetched": 263,
        "articles_classified": 185,
        "clusters_created": 16,
        "clusters_updated": 3,
        "cost_usd": 1.02,
        "tokens_in": 950_000,
        "tokens_out": 40_000,
        "stage_timings": {"fetch": 4.2, "classify": 736.0, "synthesize": 60.0},
        "error_message": None,
    }


@pytest.fixture
async def client() -> AsyncIterator[httpx.AsyncClient]:
    app.dependency_overrides[get_supabase_gateway] = lambda: cast(SupabaseGateway, object())
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as c:
        yield c
    app.dependency_overrides.clear()


async def test_get_runs_returns_typed_summaries(
    client: httpx.AsyncClient, monkeypatch: MonkeyPatch
) -> None:
    async def fake_fetch_recent_runs(gateway: Any, limit: int) -> list[dict[str, Any]]:
        assert limit == 10
        return [_run_row()]

    monkeypatch.setattr(runs_api, "fetch_recent_runs", fake_fetch_recent_runs)

    response = await client.get("/api/runs")

    assert response.status_code == 200
    body = response.json()
    assert body["runs"][0]["id"] == "r1"
    assert body["runs"][0]["cost_usd"] == 1.02
    assert body["runs"][0]["stage_timings"]["classify"] == 736.0
