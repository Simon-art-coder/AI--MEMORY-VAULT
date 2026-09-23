"""
Central configuration for the application.

We use pydantic-settings instead of raw os.environ calls so that every
config value is typed, validated, and documented in one place. If a
required value is missing or malformed, the app fails immediately on
startup rather than failing halfway through a request three days from now.
"""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # --- Application ---
    app_name: str = "AI Memory Vault"
    environment: str = "development"  # development | staging | production
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
    # Chat/extraction run on Groq (see app/ai/llm_client.py for why).
    # Embeddings run on Gemini, with an OpenAI fallback, then a local
    # lexical fallback if neither key is set.
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

    # --- Email (password reset) ---
    smtp_host: str = "smtp.gmail.com"
    smtp_port: int = 587
    smtp_username: str | None = None
    smtp_password: str | None = None
    smtp_from_email: str | None = None

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )


@lru_cache
def get_settings() -> Settings:
    """
    Returns a cached Settings instance.

    lru_cache means the .env file is only read and validated once per
    process, not on every request that needs a config value.
    """
    return Settings()