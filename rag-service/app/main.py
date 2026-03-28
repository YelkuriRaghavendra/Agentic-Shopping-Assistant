"""
RAG Service v2 — FastAPI entry point.

Responsibilities:
  - Create the FastAPI app
  - Register middleware (CORS, request ID logging)
  - Register exception handlers
  - Mount v1 routers
  - Lifespan: DB init on startup
"""
import uuid
import time
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.routes import health as health_v1
from app.api.routes import ingest as ingest_v1
from app.api.routes import retrieve as retrieve_v1
from app.api.routes import sources as sources_v1
from app.core.config import get_settings
from app.core.exceptions import RAGServiceError
from app.core.logging import setup_logging, get_logger
from app.db.session import init_db

settings = get_settings()
setup_logging()
logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("app.starting", version=settings.APP_VERSION)
    await init_db()
    try:
        from app.clients.cross_encoder_client import _load_model
        from app.config.loader import RETRIEVAL_CONFIG
        model_name = RETRIEVAL_CONFIG["reranking"]["model"]
        _load_model(model_name)
    except Exception as exc:
        logger.warning("cross_encoder.preload_failed", error=str(exc))
    yield
    logger.info("app.shutdown")


app = FastAPI(
    title="RAG Service",
    version=settings.APP_VERSION,
    description="Retrieval-Augmented Generation service with pgvector + PageIndex routing.",
    docs_url="/docs" if settings.DEBUG else None,
    redoc_url=None,
    lifespan=lifespan,
)

# ── CORS ──────────────────────────────────────────────────────────────────────
# TODO: Restrict allow_origins to specific production domains instead of ["*"]
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Request ID + latency logging ──────────────────────────────────────────────
@app.middleware("http")
async def request_middleware(request: Request, call_next):
    request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
    structlog.contextvars.clear_contextvars()
    structlog.contextvars.bind_contextvars(request_id=request_id)

    t_start  = time.monotonic()
    response = await call_next(request)
    latency  = int((time.monotonic() - t_start) * 1000)

    logger.info(
        "http.request",
        method=request.method,
        path=request.url.path,
        status=response.status_code,
        latency_ms=latency,
    )
    response.headers["X-Request-ID"] = request_id
    return response


# ── Exception handlers ────────────────────────────────────────────────────────
@app.exception_handler(RAGServiceError)
async def domain_exception_handler(request: Request, exc: RAGServiceError):
    return JSONResponse(
        status_code=exc.http_status,
        content={"error": exc.message},
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    logger.error("app.unhandled_exception", error=str(exc), exc_info=True)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"error": "An unexpected error occurred."},
    )


# ── Routers ───────────────────────────────────────────────────────────────────
app.include_router(health_v1.router)
app.include_router(ingest_v1.router,   prefix=settings.API_PREFIX)
app.include_router(retrieve_v1.router, prefix=settings.API_PREFIX)
app.include_router(sources_v1.router,  prefix=settings.API_PREFIX)
