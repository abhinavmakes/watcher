from typing import Protocol

from app.models.article import ArticleInput


class ArticleConnector(Protocol):
    async def fetch_articles(self, limit: int) -> list[ArticleInput]:
        """Fetch a list of articles from the connector."""
        ...
