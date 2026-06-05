from enum import StrEnum

from pydantic import AnyHttpUrl, Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Environment(StrEnum):
    DEVELOPMENT = "development"
    TEST = "test"
    PRODUCTION = "production"


class LogLevel(StrEnum):
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(".env", "../.env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "Watcher API"
    app_version: str = "0.1.0"
    environment: Environment = Environment.DEVELOPMENT
    log_level: LogLevel = LogLevel.INFO
    api_host: str = "0.0.0.0"
    api_port: int = Field(default=8000, ge=1, le=65535)
    cors_origins: str = "http://localhost:3000"

    supabase_url: AnyHttpUrl | None = None
    supabase_secret_key: SecretStr | None = Field(default=None, repr=False)
    supabase_publishable_key: str | None = Field(default=None, repr=False)

    claude_api_key: SecretStr | None = Field(default=None, repr=False)
    classifier_model: str = "anthropic:claude-haiku-4-5-20251001"
    classifier_rpm: int = Field(default=15, ge=1)
    synthesis_model: str = "google-gla:gemini-2.5-flash"
    embedding_model: str = "text-embedding-005"
    encryption_key: SecretStr | None = Field(default=None, repr=False)

    pipeline_interval_minutes: int = Field(default=30, ge=1)
    hn_fetch_limit: int = Field(default=30, ge=1)
    rss_fetch_limit: int = Field(default=50, ge=1)
    rss_feed_urls: str = ""
    cluster_existing_similarity_threshold: float = Field(default=0.85, ge=0.0, le=1.0)
    cluster_new_similarity_threshold: float = Field(default=0.83, ge=0.0, le=1.0)
    momentum_stale_hours: int = Field(default=48, ge=1)
    high_signal_source_domains: str = (
        "openai.com,anthropic.com,ai.googleblog.com,huggingface.co,fastapi.tiangolo.com"
    )

    @field_validator(
        "supabase_url",
        "supabase_secret_key",
        "supabase_publishable_key",
        "claude_api_key",
        "encryption_key",
        mode="before",
    )
    @classmethod
    def empty_string_as_none(cls, value: object) -> object:
        if isinstance(value, str) and value.strip() == "":
            return None
        return value

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @property
    def high_signal_source_domain_list(self) -> list[str]:
        return [
            domain.strip()
            for domain in self.high_signal_source_domains.split(",")
            if domain.strip()
        ]

    @property
    def rss_feed_url_list(self) -> list[str]:
        return [url.strip() for url in self.rss_feed_urls.split(",") if url.strip()]

    @property
    def supabase_secret_value(self) -> str | None:
        if self.supabase_secret_key is None:
            return None
        return self.supabase_secret_key.get_secret_value()

    @property
    def claude_api_key_value(self) -> str | None:
        if self.claude_api_key is None:
            return None
        return self.claude_api_key.get_secret_value()

    @property
    def encryption_key_value(self) -> str | None:
        if self.encryption_key is None:
            return None
        return self.encryption_key.get_secret_value()


settings = Settings()
