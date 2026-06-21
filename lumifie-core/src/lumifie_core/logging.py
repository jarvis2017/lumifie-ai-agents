"""Centralized loguru configuration shared by every Lumifie agent.

Call :func:`configure_logging` once at process start. Library code just does
``from lumifie_core import logger`` and logs; it never configures sinks.
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
            "<cyan>{extra[agent]}</cyan> - <level>{message}</level>"
        ),
        backtrace=False,
        diagnose=False,
    )
    # Default the bound "agent" field so logs never KeyError before binding.
    logger.configure(extra={"agent": "lumifie"})
    _CONFIGURED = True


__all__ = ["configure_logging", "logger"]
