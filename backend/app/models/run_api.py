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
    error_message: str | None = None


class RunPage(BaseModel):
    runs: list[RunSummaryCard]
