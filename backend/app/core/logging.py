"""Setup logging utilities for the application."""

from collections import OrderedDict
from logging import INFO
from typing import Final
import structlog
import logging
import sys
import json

ORDER = [
    "timestamp",
    "level",
    "event",
    "filename",
    "module",
    "lineno",
    "logger",
]

DEFAULT_LOGGING_LEVEL: Final[int] = INFO
DEFAULT_LOGGING_FORMAT: Final[str] = (
    "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)

# Structlog configuration
STRUCTLOG_PROCESSORS = [
    "structlog.contextvars.merge_contextvars",
    "structlog.processors.add_log_level",
    "structlog.processors.StackInfoRenderer()",
    "structlog.dev.set_exc_info",
    "structlog.processors.TimeStamper(fmt='iso')",
]

def _dumps(event_dict, **kwargs):
    out = {}
    for key in ORDER:
        if key in event_dict:
            out[key] = event_dict[key]
    for k, v in event_dict.items():
        if k not in out:
            out[k] = v
    return json.dumps(out, **kwargs)


def setup_logging() -> structlog.BoundLogger:
    """Set up and configure logging for the application with structlog.

    Uses JSON formatting for structured logging output, integrating stdlib logging.

    Returns:
        structlog.BoundLogger: Configured structlog logger.
    """
    # Define the shared processors
    shared_processors = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.processors.CallsiteParameterAdder(
            {
                structlog.processors.CallsiteParameter.FILENAME,
                structlog.processors.CallsiteParameter.MODULE,
                structlog.processors.CallsiteParameter.LINENO,
            }
        ),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.stdlib.ExtraAdder(),
    ]

    # Configure structlog
    structlog.configure(
        processors=shared_processors
        + [structlog.stdlib.ProcessorFormatter.wrap_for_formatter],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        context_class=OrderedDict,
        cache_logger_on_first_use=True,
    )

    # Configure standard library logging to use structlog's formatting
    formatter = structlog.stdlib.ProcessorFormatter(
        foreign_pre_chain=shared_processors,
        processors=[
            structlog.stdlib.ProcessorFormatter.remove_processors_meta,
            structlog.processors.JSONRenderer(serializer=_dumps),
        ],
    )

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)

    # Configure root logger
    root_logger = logging.getLogger()
    if root_logger.handlers:
        for h in root_logger.handlers[:]:
            root_logger.removeHandler(h)

    root_logger.addHandler(handler)
    root_logger.setLevel(DEFAULT_LOGGING_LEVEL)

    return structlog.get_logger("product_augmentation")


def get_logger(name: str) -> structlog.stdlib.BoundLogger:
    """Return a named structlog logger.

    Args:
        name: Typically ``__name__`` of the calling module.

    Returns:
        A bound structlog logger instance.
    """
    return structlog.get_logger(name)
