import pytest
from pydantic import SecretStr
from pydantic_ai.models.anthropic import AnthropicModel
from pydantic_ai.models.openai import OpenAIResponsesModel

from app.agents import llm
from app.agents.llm import LLMConfigError, build_model


def test_build_model_routes_on_provider_prefix(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(llm.settings, "openai_api_key", SecretStr("sk-test"))
    monkeypatch.setattr(llm.settings, "claude_api_key", SecretStr("claude-test"))

    openai_model = build_model("openai:gpt-6-luna")
    anthropic_model = build_model("anthropic:claude-haiku-4-5-20251001")

    assert isinstance(openai_model, OpenAIResponsesModel)
    assert openai_model.model_name == "gpt-6-luna"
    assert isinstance(anthropic_model, AnthropicModel)
    assert anthropic_model.model_name == "claude-haiku-4-5-20251001"


def test_build_model_requires_the_matching_provider_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(llm.settings, "openai_api_key", None)

    with pytest.raises(LLMConfigError, match="OPENAI_API_KEY"):
        build_model("openai:gpt-6-luna")
