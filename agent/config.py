"""
Pydantic settings for the JobUndo agent service.

All configuration comes from environment variables.
Pydantic validates types at startup — if a required env var is missing
or has the wrong type, the service fails fast with a clear error.
"""
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # ── Database ──────────────────────────────────────────────────────────
    # asyncpg requires the postgresql+asyncpg:// scheme (health checks)
    async_database_url: str = (
        "postgresql+asyncpg://jobundo:changeme@localhost:5432/jobundo"
    )
    # psycopg2 sync URL — used by langchain-postgres PGVector (Phase 5)
    # Maps DATABASE_URL env var (postgres://... → postgresql+psycopg2://...)
    sync_database_url: str = (
        "postgresql+psycopg2://jobundo:changeme@localhost:5432/jobundo"
    )

    # ── Internal auth ────────────────────────────────────────────────────
    # Must match INTERNAL_API_SECRET in Django's .env
    internal_api_secret: str = "insecure-dev-secret-change-me"

    # ── Ollama ────────────────────────────────────────────────────────────
    ollama_base_url: str = "http://localhost:11434"
    llm_model: str = "llama3.2:3b"     # set in .env when model is chosen
    embed_model: str = "nomic-embed-text"

    class Config:
        env_file = ".env"
        case_sensitive = False


# Singleton — imported everywhere
settings = Settings()
