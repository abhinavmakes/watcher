from functools import cache

from pydantic_ai.models import Model
from pydantic_ai.models.anthropic import AnthropicModel
from pydantic_ai.models.openai import OpenAIResponsesModel
from pydantic_ai.providers.anthropic import AnthropicProvider
from pydantic_ai.providers.openai import OpenAIProvider

from app.core.config import settings


class LLMConfigError(RuntimeError):
    pass


# One provider (and so one HTTP connection pool) per key, shared by every agent on it.
@cache
def _openai_provider(api_key: str) -> OpenAIProvider:
    return OpenAIProvider(api_key=api_key)


@cache
def _anthropic_provider(api_key: str) -> AnthropicProvider:
    return AnthropicProvider(api_key=api_key)


def build_model(model_setting: str) -> Model:
    """Build a PydanticAI model from a ``provider:model`` setting, e.g. ``openai:gpt-6-luna``."""
    provider, sep, model_name = model_setting.partition(":")
    if not sep:
        raise LLMConfigError(f"Model setting {model_setting!r} needs a provider prefix")

    if provider == "openai":
        api_key = settings.openai_api_key_value
        if api_key is None:
            raise LLMConfigError(f"OPENAI_API_KEY is required for {model_setting}")
        return OpenAIResponsesModel(model_name, provider=_openai_provider(api_key))

    if provider == "anthropic":
        api_key = settings.claude_api_key_value
        if api_key is None:
            raise LLMConfigError(f"CLAUDE_API_KEY is required for {model_setting}")
        return AnthropicModel(model_name, provider=_anthropic_provider(api_key))

    raise LLMConfigError(f"Unsupported model provider {provider!r} in {model_setting!r}")
