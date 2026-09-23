"""
Central configuration for the application.
"""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # --- Application ---
    app_name: str = "AI Memory Vault"
    environment: str = "development"
    debug: bool = True

    # --- Security ---
    secret_key: str
    access_token_expire_minutes: int = 30
    jwt_algorithm: str = "HS256"

    # --- Database ---
    database_url: str = "sqlite:///./memory_vault.db"

    # --- Redis / background jobs (not used yet — ingestion runs synchronously) ---
    redis_url: str = "redis://localhost:6379/0"

    # --- AI providers ---
    groq_api_key: str | None = None
    gemini_api_key: str | None = None
    openai_api_key: str | None = None
    llm_model: str = "openai/gpt-oss-120b"

    # --- Ingestion / chunking ---
    chunk_size_chars: int = 1200
    chunk_overlap_chars: int = 150
    max_upload_size_mb: int = 20

    # --- Search ---
    max_search_results: int = 8

    # --- Email (password reset, email verification) ---
    brevo_api_key: str | None = None
    brevo_sender_email: str | None = None
    brevo_sender_name: str = "AI Memory Vault"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()