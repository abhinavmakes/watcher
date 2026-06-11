from datetime import UTC, datetime
from types import SimpleNamespace
from typing import Any, cast

import pytest

from app.core.supabase import SupabaseGateway
from app.models.article import ArticleInput
from app.models.classification import ArticleDomain, ClassificationOutput
from app.services.article_store import fetch_existing_canonical_urls, insert_articles


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


def _classification() -> ClassificationOutput:
    return ClassificationOutput(
        domains=[ArticleDomain.LLMS, ArticleDomain.AI_AGENTS],
        relevance_score=0.82,
        is_noise=False,
        reason="LLM agent framework release with concrete impact.",
    )


@pytest.mark.asyncio
async def test_insert_articles_writes_article_fields_without_classification() -> None:
    fake_gateway = FakeGateway()

    inserted_count = await insert_articles(
        cast(SupabaseGateway, fake_gateway),
        [(_article(), None)],
    )

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
async def test_insert_articles_writes_classification_fields_when_present() -> None:
    fake_gateway = FakeGateway()

    inserted_count = await insert_articles(
        cast(SupabaseGateway, fake_gateway),
        [(_article(), _classification())],
    )

    assert inserted_count == 1
    assert fake_gateway.table_instance.upserted_rows is not None
    row = fake_gateway.table_instance.upserted_rows[0]
    assert row["domains"] == ["llms", "ai_agents"]
    assert row["relevance"] == 0.82
    assert row["is_noise"] is False
    assert "relevance_score" not in row


@pytest.mark.asyncio
async def test_insert_articles_omits_classification_keys_when_classification_is_none() -> None:
    fake_gateway = FakeGateway()

    await insert_articles(
        cast(SupabaseGateway, fake_gateway),
        [(_article(), None)],
    )

    assert fake_gateway.table_instance.upserted_rows is not None
    row = fake_gateway.table_instance.upserted_rows[0]
    assert "domains" not in row
    assert "relevance" not in row
    assert "is_noise" not in row


class FakeSelectQuery:
    def __init__(self, rows: list[dict[str, Any]]) -> None:
        self._rows = rows
        self.selected: str | None = None
        self.in_column: str | None = None
        self.in_values: list[str] | None = None

    def select(self, columns: str) -> "FakeSelectQuery":
        self.selected = columns
        return self

    def in_(self, column: str, values: list[str]) -> "FakeSelectQuery":
        self.in_column = column
        self.in_values = values
        return self

    async def execute(self) -> SimpleNamespace:
        return SimpleNamespace(data=self._rows)


class FakeSelectGateway:
    def __init__(self, rows: list[dict[str, Any]]) -> None:
        self.query = FakeSelectQuery(rows)
        self.table_calls: list[str] = []

    def table(self, table_name: str) -> FakeSelectQuery:
        self.table_calls.append(table_name)
        return self.query


@pytest.mark.asyncio
async def test_fetch_existing_canonical_urls_returns_persisted_subset() -> None:
    gateway = FakeSelectGateway([{"canonical_url": "https://example.com/known"}])

    existing = await fetch_existing_canonical_urls(
        cast(SupabaseGateway, gateway),
        ["https://example.com/known", "https://example.com/fresh"],
    )

    assert existing == {"https://example.com/known"}
    assert gateway.table_calls == ["articles"]
    assert gateway.query.in_column == "canonical_url"
    assert gateway.query.in_values == [
        "https://example.com/known",
        "https://example.com/fresh",
    ]


@pytest.mark.asyncio
async def test_fetch_existing_canonical_urls_skips_db_for_empty_input() -> None:
    gateway = FakeSelectGateway([])

    existing = await fetch_existing_canonical_urls(cast(SupabaseGateway, gateway), [])

    assert existing == set()
    assert gateway.table_calls == []


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
