import pytest

from app.agents.classifier import ClassifierConfigError, _model_name_from_setting


def test_model_name_from_setting_strips_pydantic_ai_provider_prefix() -> None:
    assert (
        _model_name_from_setting("anthropic:claude-haiku-4-5-20251001")
        == "claude-haiku-4-5-20251001"
    )
    assert _model_name_from_setting("claude-haiku-4-5-20251001") == "claude-haiku-4-5-20251001"


def test_classifier_config_error_is_runtime_error() -> None:
    with pytest.raises(ClassifierConfigError):
        raise ClassifierConfigError("CLAUDE_API_KEY is required")
