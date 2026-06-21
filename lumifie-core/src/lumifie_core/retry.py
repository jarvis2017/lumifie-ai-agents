"""Shared tenacity retry helper with loguru logging."""

from __future__ import annotations

from collections.abc import Callable
from typing import TypeVar

from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from lumifie_core.logging import logger

T = TypeVar("T")


def retrying(
    exceptions: tuple[type[BaseException], ...],
    *,
    max_retries: int = 4,
    min_wait: float = 1.0,
    max_wait: float = 30.0,
) -> Callable[[Callable[..., T]], Callable[..., T]]:
    """Return a decorator that retries on ``exceptions`` with exponential backoff.

    Reraises the final exception after ``max_retries`` attempts.
    """

    def _before_sleep(state) -> None:  # tenacity RetryCallState
        exc = state.outcome.exception() if state.outcome else None
        logger.warning(
            "Transient error ({}); retry {}/{}",
            exc.__class__.__name__ if exc else "?",
            state.attempt_number,
            max_retries,
        )

    return retry(
        retry=retry_if_exception_type(exceptions),
        wait=wait_exponential(multiplier=1, min=min_wait, max=max_wait),
        stop=stop_after_attempt(max_retries),
        reraise=True,
        before_sleep=_before_sleep,
    )


__all__ = ["retrying"]
