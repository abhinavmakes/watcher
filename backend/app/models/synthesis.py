from pydantic import BaseModel, Field

from app.models.article import ArticleSource
from app.models.classification import ArticleDomain


class SynthesisOutput(BaseModel):
    summary: str = Field(
        ..., min_length=1, description="What happened, 1-3 sentences, grounded only in the articles"
    )
    so_what: str = Field(
        ..., min_length=1, description="Why the reader should care, what changes for them"
    )
    title: str = Field(
        ...,
        min_length=1,
        description="A concrete headline naming the actual event, not a topic label.",
    )


class SynthesisArticle(BaseModel):
    title: str
    content: str | None = None
    source: ArticleSource
   

class SynthesisInput(BaseModel):
    articles: list[SynthesisArticle]
    key_entities: list[str] = Field(default_factory=list)
    domains: list[ArticleDomain] = Field(default_factory=list)
