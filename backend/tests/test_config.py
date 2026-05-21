from collections.abc import Mapping
from typing import Protocol

import pytest
from pydantic import ValidationError

from app.core.config import Environment, LogLevel, Settings


class BuildEnvSettings(Protocol):
    def __call__(self, values: Mapping[str, str | None]) -> Settings: ...


def test_settings_loads_typed_values_from_environment(
    build_env_settings: BuildEnvSettings,
) -> None:
    settings = build_env_settings(
        {
            "ENVIRONMENT": "test",
            "LOG_LEVEL": "DEBUG",
            "API_PORT": "9000",
            "CORS_ORIGINS": "http://localhost:3000, https://watcher.example",
            "SUPABASE_URL": "https://watcher.supabase.co",
            "SUPABASE_SECRET_KEY": "sb_secret_test",
            "SUPABASE_PUBLISHABLE_KEY": "sb_publishable_test",
            "GOOGLE_API_KEY": "google-test-key",
            "ENCRYPTION_KEY": "encryption-test-key",
            "HIGH_SIGNAL_SOURCE_DOMAINS": "openai.com, anthropic.com",
        }
    )

    assert settings.environment is Environment.TEST
    assert settings.log_level is LogLevel.DEBUG
    assert settings.api_port == 9000
    assert settings.cors_origin_list == ["http://localhost:3000", "https://watcher.example"]
    assert str(settings.supabase_url) == "https://watcher.supabase.co/"
    assert settings.supabase_secret_value == "sb_secret_test"
    assert settings.supabase_publishable_key == "sb_publishable_test"
    assert settings.google_api_key_value == "google-test-key"
    assert settings.encryption_key_value == "encryption-test-key"
    assert settings.high_signal_source_domain_list == ["openai.com", "anthropic.com"]


def test_settings_treats_blank_optional_secrets_as_missing(
    build_env_settings: BuildEnvSettings,
) -> None:
    settings = build_env_settings(
        {
            "SUPABASE_URL": "",
            "SUPABASE_SECRET_KEY": "",
            "SUPABASE_PUBLISHABLE_KEY": "",
            "GOOGLE_API_KEY": "",
            "ENCRYPTION_KEY": "",
        }
    )

    assert settings.supabase_url is None
    assert settings.supabase_secret_value is None
    assert settings.supabase_publishable_key is None
    assert settings.google_api_key_value is None
    assert settings.encryption_key_value is None


def test_settings_redacts_secret_values() -> None:
    settings = Settings.model_validate(
        {
            "supabase_secret_key": "sb_secret_test",
            "google_api_key": "google-test-key",
            "encryption_key": "encryption-test-key",
        }
    )

    settings_repr = repr(settings)

    assert "sb_secret_test" not in settings_repr
    assert "google-test-key" not in settings_repr
    assert "encryption-test-key" not in settings_repr


def test_settings_validates_bounds() -> None:
    with pytest.raises(ValidationError):
        Settings(api_port=70_000)

    with pytest.raises(ValidationError):
        Settings(cluster_existing_similarity_threshold=1.1)

    with pytest.raises(ValidationError):
        Settings(pipeline_interval_minutes=0)
