"""
Structured logging configuration.

Provides consistent, structured logging across all modules.
Log level is configurable via LOG_LEVEL environment variable.
"""

from __future__ import annotations

import logging
import structlog


def setup_logging(log_level: str = "DEBUG") -> None:
    """Configure structured logging for the application."""
    logging.basicConfig(
        format="%(message)s",
        level=getattr(logging, log_level.upper(), logging.DEBUG),
    )

    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.dev.ConsoleRenderer(),
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
    )


def get_logger(name: str) -> structlog.stdlib.BoundLogger:
    """Get a named structured logger."""
    return structlog.get_logger(name)
