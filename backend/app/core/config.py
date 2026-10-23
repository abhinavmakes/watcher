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
    rate_limit: str = "60/minute"
    rate_limit_enabled: bool = True
    # Number of proxies between the client and this app. 0 = nothing in front, so
    # X-Forwarded-For is attacker-supplied and must be ignored. Set to 1 behind a single
    # ALB/CDN. Secure by default: an unset value cannot be spoofed.
    trusted_proxy_hops: int = Field(default=0, ge=0)

    supabase_url: AnyHttpUrl | None = None
    supabase_secret_key: SecretStr | None = Field(default=None, repr=False)
    supabase_publishable_key: str | None = Field(default=None, repr=False)

    claude_api_key: SecretStr | None = Field(default=None, repr=False)
    classifier_model: str = "openai:gpt-6-luna"
    classifier_rpm: int = Field(default=15, ge=1)
    synthesis_model: str = "openai:gpt-6-luna"
    synthesis_rpm: int = Field(default=15, ge=1)
    openai_api_key: SecretStr | None = Field(default=None, repr=False)
    embedding_model: str = "text-embedding-3-small"
    embedding_dimensions: int = Field(default=768, ge=1)
    # 4x the original 2000: the first 2000 chars of a long-form engineering post are largely
    # boilerplate intro, which made vectors similar within a publisher rather than within a
    # subject. Stops well short of the model's ~30k-char limit because one vector over a 21k-char
    # document averages toward mush — that is the problem chunking solves, not a wider window.
    embedding_max_content_chars: int = Field(default=8000, ge=1)
    embedding_batch_size: int = Field(default=128, ge=1)

    pipeline_interval_minutes: int = Field(default=30, ge=1)
    # Feeds return their last N entries regardless of date, so a newly added blog
    # backfills years of archive on its first fetch. Momentum scores arrival time, not
    # publication time, so those archives rank as breaking news. 14 days suits a weekly
    # briefing; articles with no date at all are kept, because dropping on unknown is
    # the more destructive guess.
    max_article_age_days: int = Field(default=14, ge=1)
    hn_fetch_limit: int = Field(default=30, ge=1)
    rss_fetch_limit: int = Field(default=50, ge=1)
    rss_feed_urls: str = ""
    cluster_existing_similarity_threshold: float = Field(default=0.78, ge=0.0, le=1.0)
    cluster_new_similarity_threshold: float = Field(default=0.75, ge=0.0, le=1.0)
    # Lower tier used only when the article and cluster share a key entity (entity-anchored
    # merge): catches same-story coverage that sits below the cosine-only thresholds.
    cluster_entity_similarity_threshold: float = Field(default=0.65, ge=0.0, le=1.0)
    # A news event has a lifetime. Once a story's first article was published this long ago it
    # stops accepting new ones, so an old cluster cannot keep absorbing unrelated coverage.
    cluster_window_hours: int = Field(default=168, ge=1)
    momentum_stale_hours: int = Field(default=168, ge=1)
    momentum_half_life_hours: float = Field(default=72.0, gt=0)
    high_signal_source_domains: str = (
        "openai.com,anthropic.com,ai.googleblog.com,huggingface.co,fastapi.tiangolo.com"
    )

    @field_validator(
        "supabase_url",
        "supabase_secret_key",
        "supabase_publishable_key",
        "claude_api_key",
        "openai_api_key",
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
    def openai_api_key_value(self) -> str | None:
        if self.openai_api_key is None:
            return None
        return self.openai_api_key.get_secret_value()


settings = Settings()
