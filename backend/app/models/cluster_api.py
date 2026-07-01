from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, Field


class ClusterCardStatus(StrEnum):
    ACTIVE = "active"
    STALE = "stale"


class ClusterCard(BaseModel):
    id: str
    title: str
    summary: str | None = None
    so_what: str | None = None
    momentum: float = Field(ge=0, le=100)
    domains: list[str]
    key_entities: list[str]
    article_count: int
    status: ClusterCardStatus


class ClusterPage(BaseModel):
    cards: list[ClusterCard]
    total: int
    limit: int
    offset: int


class ClusterArticleRef(BaseModel):
    id: str
    title: str
    url: str
    source: str
    published_at: datetime | None = None


class ClusterDetail(ClusterCard):
    articles: list[ClusterArticleRef]
