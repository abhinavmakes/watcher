from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field, HttpUrl

ArticleSource = Literal["hn", "rss", "github", "producthunt", "devto"]


class ArticleInput(BaseModel):
    source: ArticleSource
    title: str = Field(min_length=1)
    url: HttpUrl
    canonical_url: str = Field(min_length=1)
    content: str | None = None
    published_at: datetime | None = None
    source_metadata: dict[str, Any] = Field(default_factory=dict)
