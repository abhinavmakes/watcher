from enum import StrEnum

from pydantic import BaseModel

from app.models.article import ArticleInput
from app.models.classification import ArticleDomain


class RelevanceBand(StrEnum):
    LOW = "low"  # 0.00-0.34
    MID = "mid"  # 0.35-0.69
    HIGH = "high"  # 0.70-1.00


class LabeledArticle(BaseModel):
    """One eval example: a raw article + the human ground-truth labels.

    The classifier's own output is never stored here — labeling is blind."""

    article: ArticleInput
    expected_is_noise: bool | None = None
    expected_domains: list[ArticleDomain] = []
    relevance_band: RelevanceBand | None = None
    note: str = ""

    @property
    def is_labeled(self) -> bool:
        return self.expected_is_noise is not None
