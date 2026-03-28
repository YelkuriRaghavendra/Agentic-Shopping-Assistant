from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    # ── App ──────────────────────────────────────────
    APP_NAME: str = "Chat Service"
    APP_VERSION: str = "2.0.0"
    DEBUG: bool = False
    API_V1_PREFIX: str = "/api/v1"

    # ── Database ──────────────────────────────────────
    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@localhost:5433/chatdb"
    DB_POOL_SIZE: int = 10
    DB_MAX_OVERFLOW: int = 20
    DB_POOL_TIMEOUT: int = 30

    # ── OpenAI / Azure OpenAI ─────────────────────────
    USE_AZURE: bool = False
    OPENAI_API_KEY: str = ""
    AZURE_OPENAI_API_KEY: str = ""
    AZURE_OPENAI_ENDPOINT: str = ""
    AZURE_OPENAI_API_VERSION: str = "2024-02-15-preview"
    AZURE_OPENAI_DEPLOYMENT_CHAT: str = ""
    AZURE_OPENAI_DEPLOYMENT_FALLBACK: str = ""
    OPENAI_CHAT_MODEL: str = "gpt-4o"
    OPENAI_FALLBACK_MODEL: str = "gpt-4o-mini"
    OPENAI_MAX_TOKENS: int = 1024
    OPENAI_TEMPERATURE: float = 0.3

    # ── RAG Service ───────────────────────────────────
    RAG_SERVICE_URL: str = "http://rag-service:8001"
    RAG_API_KEY: str = "dev-secret-change-in-prod"
    RAG_TIMEOUT_SECONDS: int = 15
    RAG_TOP_K: int = 5

    # ── Session ───────────────────────────────────────
    # Session idle TTL — sessions inactive longer than this are auto-expired
    SESSION_TTL_MINUTES: int = 60
    # Max turns before session requires a new one
    SESSION_MAX_TURNS: int = 100
    # Max tokens per session before budget warning
    SESSION_TOKEN_BUDGET: int = 50_000

    # ── Rate limiting ─────────────────────────────────
    # Max messages per customer per minute
    RATE_LIMIT_PER_MINUTE: int = 20
    # Max messages per customer per day
    RATE_LIMIT_PER_DAY: int = 500

    # ── Conversation ─────────────────────────────────
    CONVERSATION_WINDOW_TURNS: int = 6
    CONVERSATION_MAX_TURNS_BEFORE_SUMMARY: int = 20

    # ── Security ─────────────────────────────────────
    API_KEY_HEADER: str = "X-API-Key"
    API_KEY: str = "dev-secret-change-in-prod"

    # ── Guardrails ────────────────────────────────────
    BLOCKED_PATTERNS: list[str] = [
        "ignore previous instructions",
        "ignore your instructions",
        "ignore all instructions",
        "you are now",
        "act as",
        "jailbreak",
        "disregard your",
        "forget your instructions",
        "new instructions:",
        "system prompt",
        "do whatever i say",
        "override your",
    ]

    # ── Redis ────────────────────────────────────────
    REDIS_URL: str = "redis://localhost:6379/0"
    REDIS_ENABLED: bool = True
    CACHE_RAG_TTL: int = 300       # 5 minutes
    CACHE_PROFILE_TTL: int = 300   # 5 minutes

    # ── Commerce Service ──────────────────────────────
    COMMERCE_SERVICE_URL: str = "http://checkout-order-service:3001"
    COMMERCE_SERVICE_API_KEY: str = ""
    COMMERCE_TIMEOUT_SECONDS: int = 15

    # ── Feature Flags (LaunchDarkly) ──────────────────
    LAUNCHDARKLY_SDK_KEY: str = ""

    # ── Logging ───────────────────────────────────────
    LOG_LEVEL: str = "INFO"
    LOG_JSON: bool = False

    class Config:
        env_file = ".env"
        case_sensitive = True


@lru_cache
def get_settings() -> Settings:
    return Settings()
