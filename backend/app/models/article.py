from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field, HttpUrl

from app.models.classification import ArticleDomain

ArticleSource = Literal["hn", "rss", "github", "producthunt"]


class ArticleInput(BaseModel):
    source: ArticleSource
    title: str = Field(min_length=1)
    url: HttpUrl
    canonical_url: str = Field(min_length=1)
    content: str | None = None
    published_at: datetime | None = None
    source_metadata: dict[str, Any] = Field(default_factory=dict)


class EmbeddedArticle(BaseModel):
    canonical_url: str = Field(min_length=1)
    title: str = Field(min_length=1)
    domains: list[ArticleDomain]
    key_entities: list[str] = Field(default_factory=list)
    relevance: float = Field(ge=0.0, le=1.0)
    published_at: datetime | None = None
    vector: list[float]
