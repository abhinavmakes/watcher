from datetime import UTC, datetime

from app.agents.classifier import (
    CLASSIFIER_SYSTEM_PROMPT,
    format_classification_prompt,
)
from app.models.article import ArticleInput
from app.models.classification import ArticleDomain, ClassificationOutput


def _article(content: str | None = "PydanticAI added durable agent execution.") -> ArticleInput:
    return ArticleInput.model_validate(
        {
            "source": "hn",
            "title": "PydanticAI adds durable execution",
            "url": "https://example.com/pydanticai-durable-execution",
            "canonical_url": "https://example.com/pydanticai-durable-execution",
            "content": content,
            "published_at": datetime(2026, 5, 24, 9, 30, tzinfo=UTC),
            "source_metadata": {"hn_id": 123, "score": 250},
        }
    )


def test_classifier_prompt_lists_every_supported_domain() -> None:
    for domain in ArticleDomain:
        assert domain.value in CLASSIFIER_SYSTEM_PROMPT


def test_format_classification_prompt_uses_article_input_schema_fields() -> None:
    prompt = format_classification_prompt(_article())

    assert "source" in prompt
    assert "title" in prompt
    assert "url" in prompt
    assert "canonical_url" in prompt
    assert "content" in prompt
    assert "published_at" in prompt
    assert "source_metadata" in prompt
    assert "PydanticAI adds durable execution" in prompt
    assert '"score": 250' in prompt


def test_classification_output_limits_domains_to_three() -> None:
    output = ClassificationOutput.model_validate(
        {
            "domains": ["ai_agents", "python", "dev_tools"],
            "relevance_score": 0.92,
            "is_noise": False,
            "reason": "PydanticAI is an AI agent framework for Python developers.",
        }
    )

    assert output.domains == [
        ArticleDomain.AI_AGENTS,
        ArticleDomain.PYTHON,
        ArticleDomain.DEV_TOOLS,
    ]
