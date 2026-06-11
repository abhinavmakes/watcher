from dataclasses import dataclass

import pytest

from app.core.config import settings
from app.models import ArticleInput
from app.services import embeddings
from app.services.embeddings import (
    EmbeddingConfigError,
    build_embedding_client,
    embed_texts,
    format_embedding_input,
)


@dataclass
class _FakeItem:
    index: int
    embedding: list[float]


@dataclass
class _FakeResponse:
    data: list[_FakeItem]


class _FakeEmbeddings:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    async def create(self, *, model: str, input: list[str], dimensions: int) -> _FakeResponse:
        self.calls.append({"model": model, "input": list(input), "dimensions": dimensions})
        # Return reversed to prove embed_texts restores input order via the index.
        items = [_FakeItem(index=i, embedding=[float(i)] * dimensions) for i in range(len(input))]
        return _FakeResponse(data=list(reversed(items)))


class _FakeClient:
    def __init__(self) -> None:
        self.embeddings = _FakeEmbeddings()


@pytest.fixture
def fake_client(monkeypatch: pytest.MonkeyPatch) -> _FakeClient:
    client = _FakeClient()
    monkeypatch.setattr(embeddings, "get_embedding_client", lambda: client)
    monkeypatch.setattr(settings, "embedding_dimensions", 4)
    monkeypatch.setattr(settings, "embedding_model", "text-embedding-3-small")
    return client


@pytest.mark.asyncio
async def test_embed_texts_returns_vectors_in_input_order(fake_client: _FakeClient) -> None:
    vectors = await embed_texts(["a", "b", "c"])

    assert [v[0] for v in vectors] == [0.0, 1.0, 2.0]
    assert all(len(v) == 4 for v in vectors)
    assert fake_client.embeddings.calls[0]["dimensions"] == 4


@pytest.mark.asyncio
async def test_embed_texts_batches_large_inputs(
    fake_client: _FakeClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "embedding_batch_size", 2)

    vectors = await embed_texts(["a", "b", "c", "d", "e"])

    assert len(vectors) == 5
    assert [len(call["input"]) for call in fake_client.embeddings.calls] == [2, 2, 1]  # type: ignore[arg-type]


@pytest.mark.asyncio
async def test_embed_texts_returns_empty_without_calling_api(fake_client: _FakeClient) -> None:
    vectors = await embed_texts([])

    assert vectors == []
    assert fake_client.embeddings.calls == []


def test_build_embedding_client_requires_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "openai_api_key", None)

    with pytest.raises(EmbeddingConfigError):
        build_embedding_client()


def _article(
    *,
    title: str = "Example Title",
    content: str | None = None,
    source_metadata: dict[str, object] | None = None,
) -> ArticleInput:
    return ArticleInput(
        source="hn",
        title=title,
        url="https://example.com/a",  # type: ignore[arg-type]
        canonical_url="https://example.com/a",
        content=content,
        source_metadata=source_metadata or {},
    )


def test_format_uses_title_only_when_no_content_or_tags() -> None:
    result = format_embedding_input(_article())

    assert result.strip() == "Example Title"


def test_format_collapses_content_whitespace() -> None:
    result = format_embedding_input(_article(content="hello   \n\n  world"))

    assert "hello world" in result
    assert "\n\n" not in result.strip()


def test_format_truncates_content_to_cap(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "embedding_max_content_chars", 5)

    result = format_embedding_input(_article(content="abcdefghijklmnop"))

    assert "abcde" in result
    assert "abcdef" not in result


def test_format_includes_tags_when_present() -> None:
    result = format_embedding_input(_article(source_metadata={"tags": ["ai", "ml"]}))

    assert "ai, ml" in result


def test_format_omits_tags_when_absent() -> None:
    result = format_embedding_input(_article(content="body text"))

    assert result.strip() == "Example Title\nbody text"
