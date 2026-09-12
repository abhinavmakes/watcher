from datetime import UTC, datetime
from typing import Any, cast

import pytest

from app.core.supabase import SupabaseGateway
from app.models.pipeline_run import PipelineRunStatus, PipelineRunSummary, SourceFetchStats
from app.services.pipeline_run_store import insert_pipeline_run


class FakeInsertQuery:
    def __init__(self) -> None:
        self.execute_called = False

    async def execute(self) -> None:
        self.execute_called = True


class FakeTable:
    def __init__(self) -> None:
        self.inserted_row: dict[str, Any] | None = None
        self.query = FakeInsertQuery()

    def insert(self, row: dict[str, Any]) -> FakeInsertQuery:
        self.inserted_row = row
        return self.query


class FakeGateway:
    def __init__(self) -> None:
        self.table_calls: list[str] = []
        self.table_instance = FakeTable()

    def table(self, table_name: str) -> FakeTable:
        self.table_calls.append(table_name)
        return self.table_instance


@pytest.mark.asyncio
async def test_insert_pipeline_run_maps_summary_to_pipeline_runs_table_row() -> None:
    fake_gateway = FakeGateway()
    summary = PipelineRunSummary(
        started_at=datetime(2026, 5, 24, 8, 0, tzinfo=UTC),
        completed_at=datetime(2026, 5, 24, 8, 1, tzinfo=UTC),
        status=PipelineRunStatus.COMPLETED,
        articles_fetched=12,
        articles_classified=0,
        articles_skipped_known=5,
        clusters_updated=0,
        clusters_created=0,
        clusters_scored=6,
        clusters_stale=2,
        source_stats={
            "hn": SourceFetchStats(returned=10, duplicates=0),
            "rss": SourceFetchStats(returned=2, duplicates=1, error="feed unavailable"),
        },
        error_message=None,
    )

    await insert_pipeline_run(cast(SupabaseGateway, fake_gateway), summary)

    assert fake_gateway.table_calls == ["pipeline_runs"]
    assert fake_gateway.table_instance.query.execute_called is True
    assert fake_gateway.table_instance.inserted_row == {
        "started_at": "2026-05-24T08:00:00Z",
        "completed_at": "2026-05-24T08:01:00Z",
        "status": "completed",
        "articles_fetched": 12,
        "articles_classified": 0,
        "articles_skipped_known": 5,
        "clusters_updated": 0,
        "clusters_created": 0,
        "clusters_scored": 6,
        "clusters_stale": 2,
        "source_stats": {
            "hn": {"returned": 10, "duplicates": 0, "error": None},
            "rss": {
                "returned": 2,
                "duplicates": 1,
                "error": "feed unavailable",
            },
        },
        "error_message": None,
        "cost_usd": 0.0,
        "tokens_in": 0,
        "tokens_out": 0,
        "stage_timings": {},
    }
