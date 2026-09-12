from datetime import UTC, datetime

import pytest

from app.models.article import ArticleInput
from app.models.classification import ArticleDomain, ClassificationOutput
from worker.pipeline import _classify_articles


def _article(title: str, source: str = "hn") -> ArticleInput:
    url = f"https://example.com/{title.lower().replace(' ', '-')}"
    return ArticleInput.model_validate(
        {
            "source": source,
            "title": title,
            "url": url,
            "canonical_url": url,
            "content": "Article body",
            "published_at": datetime(2026, 5, 21, tzinfo=UTC),
            "source_metadata": {},
        }
    )


def _classification(domain: ArticleDomain = ArticleDomain.LLMS) -> ClassificationOutput:
    return ClassificationOutput(
        domains=[domain],
        relevance_score=0.8,
        is_noise=False,
        reason="test classification",
    )


@pytest.fixture
def recorded_sleeps(monkeypatch: pytest.MonkeyPatch) -> list[float]:
    """Stub asyncio.sleep so tests don't actually wait. Returns recorded durations."""
    sleeps: list[float] = []

    async def _record_sleep(seconds: float) -> None:
        sleeps.append(seconds)

    monkeypatch.setattr("worker.pipeline.asyncio.sleep", _record_sleep)
    return sleeps


@pytest.mark.asyncio
async def test_classify_articles_returns_empty_list_for_empty_input(
    recorded_sleeps: list[float],
) -> None:
    result = await _classify_articles([])

    assert result == []
    assert recorded_sleeps == []


@pytest.mark.asyncio
async def test_classify_articles_pairs_articles_with_classifications_preserving_order(
    monkeypatch: pytest.MonkeyPatch,
    recorded_sleeps: list[float],
) -> None:
    a1 = _article("First")
    a2 = _article("Second")
    a3 = _article("Third")
    expected = {
        a1.canonical_url: _classification(ArticleDomain.LLMS),
        a2.canonical_url: _classification(ArticleDomain.AI_AGENTS),
        a3.canonical_url: _classification(ArticleDomain.PYTHON),
    }

    async def fake_classify_article(
        article: ArticleInput, *, usage: object | None = None
    ) -> ClassificationOutput:
        return expected[article.canonical_url]

    monkeypatch.setattr("worker.pipeline.classify_article", fake_classify_article)

    result = await _classify_articles([a1, a2, a3])

    assert [article for article, _ in result] == [a1, a2, a3]
    assert [classification for _, classification in result] == [
        expected[a1.canonical_url],
        expected[a2.canonical_url],
        expected[a3.canonical_url],
    ]


@pytest.mark.asyncio
async def test_classify_articles_records_none_for_failed_articles_without_raising(
    monkeypatch: pytest.MonkeyPatch,
    recorded_sleeps: list[float],
) -> None:
    a1 = _article("First")
    a2 = _article("Second")
    a3 = _article("Third")
    good_output = _classification()

    async def fake_classify_article(
        article: ArticleInput, *, usage: object | None = None
    ) -> ClassificationOutput:
        if article is a2:
            raise RuntimeError("agent boom")
        return good_output

    monkeypatch.setattr("worker.pipeline.classify_article", fake_classify_article)

    result = await _classify_articles([a1, a2, a3])

    assert result == [(a1, good_output), (a2, None), (a3, good_output)]


@pytest.mark.parametrize(
    ("article_count", "expected_sleep_count"),
    [(0, 0), (1, 0), (3, 2), (5, 4)],
)
@pytest.mark.asyncio
async def test_classify_articles_sleeps_n_minus_one_times_between_calls(
    monkeypatch: pytest.MonkeyPatch,
    recorded_sleeps: list[float],
    article_count: int,
    expected_sleep_count: int,
) -> None:
    articles = [_article(f"Article {i}") for i in range(article_count)]

    async def fake_classify_article(
        article: ArticleInput, *, usage: object | None = None
    ) -> ClassificationOutput:
        return _classification()

    monkeypatch.setattr("worker.pipeline.classify_article", fake_classify_article)

    await _classify_articles(articles)

    assert len(recorded_sleeps) == expected_sleep_count


@pytest.mark.asyncio
async def test_classify_articles_sleep_interval_is_60_over_classifier_rpm(
    monkeypatch: pytest.MonkeyPatch,
    recorded_sleeps: list[float],
) -> None:
    monkeypatch.setattr("worker.pipeline.settings.classifier_rpm", 30)
    articles = [_article(f"Article {i}") for i in range(3)]

    async def fake_classify_article(
        article: ArticleInput, *, usage: object | None = None
    ) -> ClassificationOutput:
        return _classification()

    monkeypatch.setattr("worker.pipeline.classify_article", fake_classify_article)

    await _classify_articles(articles)

    assert recorded_sleeps == [2.0, 2.0]
