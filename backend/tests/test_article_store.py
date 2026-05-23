from datetime import UTC, datetime
from typing import Any, cast

import pytest

from app.core.supabase import SupabaseGateway
from app.models.article import ArticleInput
from app.services.article_store import insert_articles


class FakeInsertQuery:
    def __init__(self) -> None:
        self.execute_called = False

    async def execute(self) -> None:
        self.execute_called = True


class FakeTable:
    def __init__(self) -> None:
        self.upserted_rows: list[dict[str, Any]] | None = None
        self.on_conflict: str | None = None
        self.ignore_duplicates: bool | None = None
        self.query = FakeInsertQuery()

    def upsert(
        self,
        rows: list[dict[str, Any]],
        *,
        on_conflict: str,
        ignore_duplicates: bool,
    ) -> FakeInsertQuery:
        self.upserted_rows = rows
        self.on_conflict = on_conflict
        self.ignore_duplicates = ignore_duplicates
        return self.query


class FakeGateway:
    def __init__(self) -> None:
        self.table_calls: list[str] = []
        self.table_instance = FakeTable()

    def table(self, table_name: str) -> FakeTable:
        self.table_calls.append(table_name)
        return self.table_instance


def _article() -> ArticleInput:
    return ArticleInput.model_validate(
        {
            "source": "hn",
            "title": "Article store story",
            "url": "https://example.com/articles/store-story",
            "canonical_url": "https://example.com/articles/store-story",
            "content": "Article body",
            "published_at": datetime(2026, 5, 23, 8, 30, tzinfo=UTC),
            "source_metadata": {
                "hn_id": 123,
                "score": 42,
            },
        }
    )


@pytest.mark.asyncio
async def test_insert_articles_maps_article_input_to_articles_table_row() -> None:
    fake_gateway = FakeGateway()

    inserted_count = await insert_articles(cast(SupabaseGateway, fake_gateway), [_article()])

    assert inserted_count == 1
    assert fake_gateway.table_calls == ["articles"]
    assert fake_gateway.table_instance.query.execute_called is True
    assert fake_gateway.table_instance.on_conflict == "canonical_url"
    assert fake_gateway.table_instance.ignore_duplicates is True
    assert fake_gateway.table_instance.upserted_rows == [
        {
            "source": "hn",
            "title": "Article store story",
            "url": "https://example.com/articles/store-story",
            "canonical_url": "https://example.com/articles/store-story",
            "content": "Article body",
            "published_at": "2026-05-23T08:30:00Z",
            "source_meta": {
                "hn_id": 123,
                "score": 42,
            },
        }
    ]


@pytest.mark.asyncio
async def test_insert_articles_returns_zero_for_empty_input_without_db_call() -> None:
    fake_gateway = FakeGateway()

    inserted_count = await insert_articles(cast(SupabaseGateway, fake_gateway), [])

    assert inserted_count == 0
    assert fake_gateway.table_calls == []
    assert fake_gateway.table_instance.upserted_rows is None
    assert fake_gateway.table_instance.on_conflict is None
    assert fake_gateway.table_instance.ignore_duplicates is None
    assert fake_gateway.table_instance.query.execute_called is False
