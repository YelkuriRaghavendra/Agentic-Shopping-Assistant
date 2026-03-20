import logging
import structlog
from app.core.config import get_settings

settings = get_settings()
_configured = False


def setup_logging() -> None:
    global _configured
    if _configured:
        return
    _configured = True

    log_level  = getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO)
    # Note: add_logger_name requires stdlib logger — omit when using PrintLoggerFactory
    processors = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.processors.TimeStamper(fmt="%Y-%m-%d %H:%M:%S"),
        structlog.processors.StackInfoRenderer(),
    ]
    if settings.LOG_JSON:
        processors.append(structlog.processors.JSONRenderer())
    else:
        processors.append(structlog.dev.ConsoleRenderer())

    structlog.configure(
        processors=processors,
        wrapper_class=structlog.make_filtering_bound_logger(log_level),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=False,
    )


def get_logger(name: str = __name__):
    return structlog.get_logger(name)
