from datetime import UTC, datetime
from pathlib import Path

from app.models.article import ArticleInput
from scripts.generate_seed_articles import serialize_articles, write_seed_articles


def _article() -> ArticleInput:
    return ArticleInput.model_validate(
        {
            "source": "hn",
            "title": "Seed story",
            "url": "https://example.com/seed-story",
            "canonical_url": "https://example.com/seed-story",
            "content": "Seed body",
            "published_at": datetime(2026, 5, 22, tzinfo=UTC),
            "source_metadata": {"score": 10},
        }
    )


def test_serialize_articles_uses_json_safe_values() -> None:
    payload = serialize_articles([_article()])

    assert payload == [
        {
            "source": "hn",
            "title": "Seed story",
            "url": "https://example.com/seed-story",
            "canonical_url": "https://example.com/seed-story",
            "content": "Seed body",
            "published_at": "2026-05-22T00:00:00Z",
            "source_metadata": {"score": 10},
        }
    ]


def test_write_seed_articles_writes_json_array(tmp_path: Path) -> None:
    output_path = tmp_path / "seed_articles.json"

    write_seed_articles([_article()], output_path)

    text = output_path.read_text(encoding="utf-8")
    assert text.startswith("[\n")
    assert "Seed story" in text
