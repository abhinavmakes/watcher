import pytest

from app.agents.classifier import ClassifierConfigError, _google_model_name_from_setting


def test_google_model_name_from_setting_strips_pydantic_ai_provider_prefixes() -> None:
    assert (
        _google_model_name_from_setting("google-gla:gemini-2.5-flash-lite")
        == "gemini-2.5-flash-lite"
    )
    assert (
        _google_model_name_from_setting("google:gemini-2.5-flash-lite") == "gemini-2.5-flash-lite"
    )
    assert _google_model_name_from_setting("gemini-2.5-flash-lite") == "gemini-2.5-flash-lite"


def test_classifier_config_error_is_runtime_error() -> None:
    with pytest.raises(ClassifierConfigError):
        raise ClassifierConfigError("GOOGLE_API_KEY is required")
