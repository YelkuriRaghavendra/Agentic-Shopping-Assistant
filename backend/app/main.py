"""
FastAPI application entry point.

Responsibilities:
  - Create the FastAPI app
  - Register middleware (CORS, request logging, request ID)
  - Register exception handlers
  - Mount routers
  - Lifespan events (startup / shutdown)
"""

import uuid
import time
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.routes.v1 import chat as chat_routes
from app.api.routes.v1 import health as health_routes
from app.core.config import get_settings
from app.core.exceptions import ChatServiceError
from app.core.logging import setup_logging, get_logger
from app.db.session import init_db
from app.clients.redis_client import init_redis, close_redis

settings = get_settings()
setup_logging()
logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown logic."""
    logger.info("app.starting", version=settings.APP_VERSION)
    await init_db()
    await init_redis()
    yield
    await close_redis()
    logger.info("app.shutdown")


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="E-commerce shopping assistant chat service.",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# ── CORS ──────────────────────────────────────────────────────────────────────
# TODO: restrict allow_origins to known frontend domains in production
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Request ID + latency logging middleware ───────────────────────────────────
@app.middleware("http")
async def request_middleware(request: Request, call_next):
    """
    Attaches a unique request ID to every request.
    Logs method, path, status, and latency on every response.
    The request_id propagates through all log lines via structlog context vars.
    """
    request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
    structlog.contextvars.clear_contextvars()
    structlog.contextvars.bind_contextvars(request_id=request_id)

    t_start = time.monotonic()
    response = await call_next(request)
    latency_ms = int((time.monotonic() - t_start) * 1000)

    logger.info(
        "http.request",
        method=request.method,
        path=request.url.path,
        status=response.status_code,
        latency_ms=latency_ms,
    )

    response.headers["X-Request-ID"] = request_id
    return response


# ── Global exception handlers ─────────────────────────────────────────────────
@app.exception_handler(ChatServiceError)
async def domain_exception_handler(request: Request, exc: ChatServiceError):
    """Converts domain exceptions to HTTP responses."""
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
app.include_router(health_routes.router)
app.include_router(chat_routes.router, prefix=settings.API_V1_PREFIX)
