from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, Field


class PipelineRunStatus(StrEnum):
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class SourceFetchStats(BaseModel):
    returned: int
    duplicates: int = 0
    error: str | None = None


class PipelineRunSummary(BaseModel):
    started_at: datetime
    completed_at: datetime | None
    status: PipelineRunStatus
    articles_fetched: int = 0
    articles_classified: int = 0
    articles_skipped_known: int = 0
    clusters_updated: int = 0
    clusters_created: int = 0
    source_stats: dict[str, SourceFetchStats] = Field(default_factory=dict)
    error_message: str | None = None
