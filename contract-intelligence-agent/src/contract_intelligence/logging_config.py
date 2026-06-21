"""Centralized loguru configuration.

Call :func:`configure_logging` once at process start (the CLI does this). Library
code just does ``from loguru import logger`` and logs; it never configures sinks.
"""

from __future__ import annotations

import sys

from loguru import logger

_CONFIGURED = False


def configure_logging(level: str = "INFO") -> None:
    """Install a single stderr sink at ``level``. Idempotent."""
    global _CONFIGURED
    logger.remove()
    logger.add(
        sys.stderr,
        level=level.upper(),
        format=(
            "<green>{time:HH:mm:ss}</green> | "
            "<level>{level: <8}</level> | "
            "<cyan>{name}</cyan> - <level>{message}</level>"
        ),
        backtrace=False,
        diagnose=False,
    )
    _CONFIGURED = True


__all__ = ["configure_logging", "logger"]
