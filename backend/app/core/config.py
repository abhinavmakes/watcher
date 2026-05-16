from pydantic import AnyHttpUrl, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(".env", "../.env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "Watcher API"
    app_version: str = "0.1.0"
    environment: str = "development"
    log_level: str = "INFO"
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    cors_origins: str = "http://localhost:3000"

    supabase_url: AnyHttpUrl | None = None
    supabase_service_key: str | None = Field(default=None, repr=False)
    supabase_anon_key: str | None = Field(default=None, repr=False)

    google_api_key: str | None = Field(default=None, repr=False)
    classifier_model: str = "google-gla:gemini-2.5-flash-lite"
    synthesis_model: str = "google-gla:gemini-2.5-flash"
    embedding_model: str = "text-embedding-005"

    encryption_key: str | None = Field(default=None, repr=False)

    pipeline_interval_minutes: int = 30
    cluster_existing_similarity_threshold: float = 0.85
    cluster_new_similarity_threshold: float = 0.83
    momentum_stale_hours: int = 48
    high_signal_source_domains: str = (
        "openai.com,anthropic.com,ai.googleblog.com,huggingface.co,fastapi.tiangolo.com"
    )

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


settings = Settings()
