"""Thin, retrying wrapper around the Anthropic Messages API.

Why a wrapper:

* It is the single seam the agent depends on (a ``create(**kwargs)`` callable),
  so tests can inject a scripted fake client with no network and no API key.
* It adds a tenacity retry layer with logging on top of the SDK's built-in
  retries, for transient failures (429 / 5xx / connection errors).
"""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

from loguru import logger
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

try:  # The SDK is a hard runtime dep, but keep import errors actionable.
    import anthropic
    from anthropic import (
        APIConnectionError,
        APIStatusError,
        InternalServerError,
        RateLimitError,
    )
except ImportError as exc:  # pragma: no cover - environment misconfiguration
    raise ImportError(
        "The 'anthropic' package is required. Install with: uv pip install anthropic"
    ) from exc


# Transient errors worth retrying. 4xx errors other than 429 are not retried.
_RETRYABLE = (RateLimitError, APIConnectionError, InternalServerError)


@runtime_checkable
class MessageCreator(Protocol):
    """Structural type for anything that can create a message.

    Both the real wrapper below and the test fake satisfy this, so the agent
    depends only on this protocol.
    """

    def create(self, **kwargs: Any) -> Any: ...


class AnthropicLLMClient:
    """Production LLM client backed by ``anthropic.Anthropic``."""

    def __init__(
        self,
        api_key: str | None = None,
        *,
        max_retries: int = 4,
    ) -> None:
        # The SDK reads ANTHROPIC_API_KEY itself when api_key is None.
        self._client = anthropic.Anthropic(api_key=api_key)
        self._max_retries = max_retries

    def create(self, **kwargs: Any) -> Any:
        """Call ``messages.create`` with exponential-backoff retries."""

        @retry(
            retry=retry_if_exception_type(_RETRYABLE),
            wait=wait_exponential(multiplier=1, min=1, max=30),
            stop=stop_after_attempt(self._max_retries),
            reraise=True,
            before_sleep=lambda state: logger.warning(
                "Transient API error ({}); retry {}/{}",
                state.outcome.exception().__class__.__name__
                if state.outcome
                else "?",
                state.attempt_number,
                self._max_retries,
            ),
        )
        def _call() -> Any:
            return self._client.messages.create(**kwargs)

        try:
            return _call()
        except APIStatusError as exc:
            # Non-retryable HTTP error (4xx). Surface a clean message.
            logger.error("Anthropic API error {}: {}", exc.status_code, exc.message)
            raise


__all__ = ["AnthropicLLMClient", "MessageCreator"]
