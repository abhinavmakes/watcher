from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from typing import Any

import pytest
from pydantic_settings import SettingsConfigDict
from pytest import MonkeyPatch

from app.core import supabase as supabase_module
from app.core.config import Settings


class EnvOnlySettings(Settings):
    model_config = SettingsConfigDict(env_file=None, env_file_encoding="utf-8", extra="ignore")


WATCHER_ENV_KEYS = (
    "ENVIRONMENT",
    "LOG_LEVEL",
    "API_HOST",
    "API_PORT",
    "CORS_ORIGINS",
    "RATE_LIMIT",
    "RATE_LIMIT_ENABLED",
    "SUPABASE_URL",
    "SUPABASE_SECRET_KEY",
    "SUPABASE_PUBLISHABLE_KEY",
    "CLAUDE_API_KEY",
    "OPENAI_API_KEY",
    "CLASSIFIER_MODEL",
    "CLASSIFIER_RPM",
    "SYNTHESIS_MODEL",
    "SYNTHESIS_RPM",
    "EMBEDDING_MODEL",
    "EMBEDDING_DIMENSIONS",
    "EMBEDDING_MAX_CONTENT_CHARS",
    "EMBEDDING_BATCH_SIZE",
    "PIPELINE_INTERVAL_MINUTES",
    "HN_FETCH_LIMIT",
    "RSS_FETCH_LIMIT",
    "RSS_FEED_URLS",
    "CLUSTER_EXISTING_SIMILARITY_THRESHOLD",
    "CLUSTER_NEW_SIMILARITY_THRESHOLD",
    "CLUSTER_ENTITY_SIMILARITY_THRESHOLD",
    "MOMENTUM_STALE_HOURS",
    "MOMENTUM_HALF_LIFE_HOURS",
    "HIGH_SIGNAL_SOURCE_DOMAINS",
    "TRUSTED_PROXY_HOPS",
)


@pytest.fixture
def build_env_settings(
    monkeypatch: MonkeyPatch,
) -> Callable[[Mapping[str, str | None]], Settings]:
    def build(values: Mapping[str, str | None]) -> Settings:
        for key in WATCHER_ENV_KEYS:
            monkeypatch.delenv(key, raising=False)

        for key, value in values.items():
            if value is None:
                monkeypatch.delenv(key, raising=False)
            else:
                monkeypatch.setenv(key, value)

        return EnvOnlySettings()

    return build


class FakeAsyncSupabaseClient:
    def table(self, table_name: str) -> str:
        return f"table:{table_name}"

    def rpc(self, function_name: str, params: dict[str, object] | None = None) -> tuple[str, Any]:
        return function_name, params


@dataclass
class FakeSupabaseFactory:
    calls: dict[str, str] = field(default_factory=dict)
    client: FakeAsyncSupabaseClient = field(default_factory=FakeAsyncSupabaseClient)

    async def create_async_client(self, url: str, key: str) -> FakeAsyncSupabaseClient:
        self.calls["url"] = url
        self.calls["key"] = key
        return self.client


@pytest.fixture
def fake_supabase_factory(monkeypatch: MonkeyPatch) -> FakeSupabaseFactory:
    factory = FakeSupabaseFactory()
    monkeypatch.setattr(supabase_module, "create_async_client", factory.create_async_client)
    return factory
