import asyncio
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Literal

from pydantic import BaseModel, Field

from app.connectors.base import ArticleConnector
from app.models.article import ArticleInput


@dataclass(frozen=True)
class ConnectorSpec:
    name: str
    connector: ArticleConnector
    limit: int


@dataclass(frozen=True)
class FetchResult:
    source: str
    articles: list[ArticleInput]
    error: str | None = None


@dataclass(frozen=True)
class SourceFetchStats(BaseModel):
    returned: int
    error: str | None = None


class PipelineRunSummary(BaseModel):
    started_at: datetime
    completed_at: datetime
    status: Literal["completed"]
    articles_fetched: int = 0
    articles_classified: int = 0
    clusters_updated: int = 0
    clusters_created: int = 0
    source_stats: dict[str, SourceFetchStats] = Field(default_factory=dict)


async def _fetch_from_connector(spec: ConnectorSpec) -> FetchResult:
    try:
        articles = await spec.connector.fetch_articles(spec.limit)
    except Exception as exc:
        return FetchResult(source=spec.name, articles=[], error=str(exc))

    return FetchResult(source=spec.name, articles=articles)


async def run_pipeline(connector_specs: Sequence[ConnectorSpec]) -> PipelineRunSummary:
    started_at = datetime.now(UTC)

    results = await asyncio.gather(*(_fetch_from_connector(spec) for spec in connector_specs))
    articles_fetched = sum(len(result.articles) for result in results)
    source_stats = {
        result.source: SourceFetchStats(returned=len(result.articles), error=result.error)
        for result in results
    }

    return PipelineRunSummary(
        started_at=started_at,
        completed_at=datetime.now(UTC),
        articles_fetched=articles_fetched,
        source_stats=source_stats,
        status="completed",
    )
