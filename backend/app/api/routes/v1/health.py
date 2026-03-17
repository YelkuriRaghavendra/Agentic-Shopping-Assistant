from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from app.db.session import get_db
from app.clients.rag_client import RAGClient
from app.core.config import get_settings

router = APIRouter(tags=["Health"])
settings = get_settings()


@router.get("/health", include_in_schema=False)
async def health(db: AsyncSession = Depends(get_db)):
    """Health check — called by load balancer every 30s."""
    db_ok  = False
    rag_ok = False

    try:
        await db.execute(text("SELECT 1"))
        db_ok = True
    except Exception:
        pass

    try:
        rag_ok = await RAGClient().health_check()
    except Exception:
        pass

    overall = "ok" if db_ok else "degraded"
    return {
        "status":      overall,
        "version":     settings.APP_VERSION,
        "db":          "ok" if db_ok  else "error",
        "rag_service": "ok" if rag_ok else "unavailable",
        "llm_provider": "azure" if settings.USE_AZURE else "openai",
    }
