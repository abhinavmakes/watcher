from datetime import datetime

from pydantic import BaseModel

from app.models.pipeline_run import PipelineRunStatus


class RunSummaryCard(BaseModel):
    id: str
    started_at: datetime
    completed_at: datetime | None
    status: PipelineRunStatus
    articles_fetched: int
    articles_classified: int
    clusters_created: int
    clusters_updated: int
    cost_usd: float
    tokens_in: int
    tokens_out: int
    stage_timings: dict[str, float]
    # No error_message: raw exceptions can carry request or org ids, so they stay in the DB.


class RunPage(BaseModel):
    runs: list[RunSummaryCard]
