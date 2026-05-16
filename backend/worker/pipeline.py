from datetime import UTC, datetime
from typing import Literal

from pydantic import BaseModel, Field


class PipelineRunSummary(BaseModel):
    started_at: datetime
    completed_at: datetime
    status: Literal["completed"]
    articles_fetched: int = 0
    articles_classified: int = 0
    clusters_updated: int = 0
    clusters_created: int = 0
    source_stats: dict[str, object] = Field(default_factory=dict)


async def run_pipeline() -> PipelineRunSummary:
    started_at = datetime.now(UTC)
    return PipelineRunSummary(
        started_at=started_at,
        completed_at=datetime.now(UTC),
        status="completed",
    )
