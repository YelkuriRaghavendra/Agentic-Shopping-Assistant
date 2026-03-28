from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    # ── App ──────────────────────────────────────────
    APP_NAME:    str  = "RAG Service"
    APP_VERSION: str  = "2.0.0"
    DEBUG:       bool = False
    API_PREFIX:  str  = "/api/v1"

    # ── Database ─────────────────────────────────────
    DATABASE_URL:     str = "postgresql+asyncpg://postgres:postgres@localhost:5432/ragdb"
    DB_POOL_SIZE:     int = 10
    DB_MAX_OVERFLOW:  int = 20
    DB_POOL_TIMEOUT:  int = 30

    # ── OpenAI ───────────────────────────────────────
    USE_AZURE:                  bool = False
    OPENAI_API_KEY:             str  = ""
    AZURE_OPENAI_API_KEY:       str  = ""
    AZURE_OPENAI_ENDPOINT:      str  = ""
    AZURE_OPENAI_API_VERSION:   str  = "2024-02-15-preview"
    OPENAI_EMBEDDING_MODEL:     str  = "text-embedding-3-large"
    EMBEDDING_DIMENSIONS:       int  = 1536

    # ── Commerce service (order embedding events) ────────────────────────────
    COMMERCE_SERVICE_URL:     str = "http://localhost:3001"
    COMMERCE_SERVICE_API_KEY: str = ""

    # ── Security ──────────────────────────────────────
    API_KEY_HEADER: str = "X-API-Key"
    API_KEY:        str = ""          # must be set via env in production

    # ── Logging ───────────────────────────────────────
    LOG_LEVEL: str  = "INFO"
    LOG_JSON:  bool = False           # set True in production

    class Config:
        env_file      = ".env"
        case_sensitive = True


@lru_cache()
def get_settings() -> Settings:
    return Settings()
