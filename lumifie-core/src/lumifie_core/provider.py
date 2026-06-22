"""Provider-agnostic LLM access via litellm.

A single :class:`LLMProvider` is the only place an agent talks to a model. It:

* resolves friendly aliases (``claude`` → ``claude-opus-4-8``, ``gpt-4o``,
  ``ollama/llama3.1``) and reads ``LITELLM_MODEL`` as the default,
* exposes ``supports_tools`` so agents can branch between native tool use
  (Claude, GPT-4o) and a JSON-mode fallback (Ollama and other local models),
* normalizes litellm's OpenAI-shaped response into a small :class:`CompletionResult`,
* retries transient API failures with exponential backoff.

The actual network call is injectable (``completion_fn``) so agents and this
package are fully testable without a network or API keys.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

import litellm
from litellm import exceptions as _ex

from lumifie_core.config import CoreSettings
from lumifie_core.logging import logger
from lumifie_core.retry import retrying

# Friendly aliases -> concrete litellm model ids.
MODEL_ALIASES: dict[str, str] = {
    "claude": "claude-opus-4-8",
    "claude-opus": "claude-opus-4-8",
    "gpt-4o": "gpt-4o",
    "gpt4o": "gpt-4o",
    # OpenRouter free models (for the "fast" tier). litellm routes openrouter/*
    # via OPENROUTER_API_KEY.
    "fast": "openrouter/google/gemini-2.0-flash-exp:free",
    "openrouter-free": "openrouter/google/gemini-2.0-flash-exp:free",
    "gemini-flash-free": "openrouter/google/gemini-2.0-flash-exp:free",
    "llama-free": "openrouter/meta-llama/llama-3.1-8b-instruct:free",
}

# Transient litellm errors worth retrying.
_RETRYABLE: tuple[type[BaseException], ...] = tuple(
    getattr(_ex, name)
    for name in (
        "Timeout",
        "APIConnectionError",
        "RateLimitError",
        "InternalServerError",
        "ServiceUnavailableError",
    )
    if hasattr(_ex, name)
)


def resolve_model(spec: str | None) -> str:
    """Resolve an alias or env default into a concrete litellm model id."""
    chosen = spec or "claude"
    return MODEL_ALIASES.get(chosen, chosen)


def missing_credential(model: str) -> str | None:
    """Return the env var a hosted model needs but that is unset, else None.

    Local models (Ollama) need no key. Unknown providers return None — litellm
    validates them at call time.
    """
    import os

    if model.startswith(("ollama/", "ollama_chat/")):
        return None
    if model.startswith("openrouter/"):
        return None if os.getenv("OPENROUTER_API_KEY") else "OPENROUTER_API_KEY"
    if model.startswith(("claude", "anthropic/")):
        return None if os.getenv("ANTHROPIC_API_KEY") else "ANTHROPIC_API_KEY"
    if model.startswith(("gpt", "openai/", "o1", "o3")):
        return None if os.getenv("OPENAI_API_KEY") else "OPENAI_API_KEY"
    return None


def model_supports_tools(model: str) -> bool:
    """Whether native function/tool calling should be used for ``model``.

    Ollama / local models are routed to the JSON-mode fallback regardless of any
    partial tool support, per the Lumifie standard. Hosted models (Claude, GPT-4o)
    use native tools.
    """
    if model.startswith(("ollama/", "ollama_chat/")):
        return False
    try:
        return bool(litellm.supports_function_calling(model=model))
    except Exception:  # unknown model id — assume hosted tool support
        return True


@dataclass(slots=True)
class ToolCall:
    """A normalized tool/function call requested by the model."""

    id: str
    name: str
    arguments: dict[str, Any]


@dataclass(slots=True)
class CompletionResult:
    """Normalized result of one completion, independent of provider."""

    text: str | None
    tool_calls: list[ToolCall] = field(default_factory=list)
    finish_reason: str | None = None
    usage: dict[str, int] = field(default_factory=dict)
    model: str = ""


class LLMProvider:
    """The single seam every agent uses to call a model."""

    def __init__(
        self,
        model: str | None = None,
        *,
        max_tokens: int = 8000,
        temperature: float | None = None,
        reasoning_effort: str | None = None,
        max_retries: int = 4,
        request_timeout: int = 600,
        api_base: str | None = None,
        api_key: str | None = None,
        completion_fn: Callable[..., Any] | None = None,
    ) -> None:
        self.model = resolve_model(model)
        self.supports_tools = model_supports_tools(self.model)
        self.max_tokens = max_tokens
        self.temperature = temperature
        self.reasoning_effort = reasoning_effort
        self.request_timeout = request_timeout
        # Optional overrides for OpenAI-compatible endpoints (e.g. Nvidia Build,
        # local gateways). When set, they are forwarded to litellm per call.
        self.api_base = api_base
        self.api_key = api_key
        self._completion = completion_fn or litellm.completion
        self._max_retries = max_retries

        if not self.supports_tools:
            logger.warning(
                "Model '{}' does not support native tool use; agents will fall "
                "back to JSON-mode structured extraction.",
                self.model,
            )

    @classmethod
    def from_settings(
        cls, settings: CoreSettings, *, completion_fn: Callable[..., Any] | None = None
    ) -> LLMProvider:
        return cls(
            settings.model,
            max_tokens=settings.max_tokens,
            temperature=settings.temperature,
            reasoning_effort=settings.reasoning_effort,
            max_retries=settings.max_retries,
            request_timeout=settings.request_timeout,
            completion_fn=completion_fn,
        )

    def complete(
        self,
        messages: list[dict[str, Any]],
        *,
        tools: list[dict[str, Any]] | None = None,
        tool_choice: str | dict[str, Any] | None = None,
        response_format: dict[str, Any] | None = None,
        max_tokens: int | None = None,
    ) -> CompletionResult:
        """Run one completion and return a normalized result.

        ``tools`` are only forwarded when the model supports tool use; otherwise
        they are dropped (callers should provide ``response_format`` for the
        JSON-mode fallback instead).
        """
        kwargs: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "max_tokens": max_tokens or self.max_tokens,
            "timeout": self.request_timeout,
        }
        if self.temperature is not None:
            kwargs["temperature"] = self.temperature
        if self.reasoning_effort is not None:
            kwargs["reasoning_effort"] = self.reasoning_effort
        if self.api_base is not None:
            kwargs["api_base"] = self.api_base
        if self.api_key is not None:
            kwargs["api_key"] = self.api_key
        if tools and self.supports_tools:
            kwargs["tools"] = tools
            kwargs["tool_choice"] = tool_choice or "auto"
        if response_format is not None:
            kwargs["response_format"] = response_format

        call = retrying(_RETRYABLE, max_retries=self._max_retries)(self._completion)
        try:
            raw = call(**kwargs)
        except _ex.BadRequestError as exc:
            logger.error("Model rejected the request: {}", exc)
            raise

        return self._normalize(raw)

    # -- normalization -----------------------------------------------------

    @staticmethod
    def _normalize(raw: Any) -> CompletionResult:
        choice = _index(_get(raw, "choices"), 0)
        message = _get(choice, "message")
        finish = _get(choice, "finish_reason")

        tool_calls: list[ToolCall] = []
        for tc in _get(message, "tool_calls") or []:
            fn = _get(tc, "function")
            raw_args = _get(fn, "arguments") or "{}"
            try:
                args = json.loads(raw_args) if isinstance(raw_args, str) else dict(raw_args)
            except (json.JSONDecodeError, TypeError):
                logger.warning("Could not parse tool arguments; using empty dict.")
                args = {}
            tool_calls.append(
                ToolCall(id=_get(tc, "id") or "", name=_get(fn, "name") or "", arguments=args)
            )

        usage_obj = _get(raw, "usage")
        usage = {
            "input_tokens": int(_get(usage_obj, "prompt_tokens") or 0),
            "output_tokens": int(_get(usage_obj, "completion_tokens") or 0),
            "total_tokens": int(_get(usage_obj, "total_tokens") or 0),
        }

        return CompletionResult(
            text=_get(message, "content"),
            tool_calls=tool_calls,
            finish_reason=finish,
            usage=usage,
            model=_get(raw, "model") or "",
        )


def _get(obj: Any, key: str) -> Any:
    """Attribute-or-key accessor (litellm returns objects; tests may use dicts)."""
    if obj is None:
        return None
    if isinstance(obj, dict):
        return obj.get(key)
    return getattr(obj, key, None)


def _index(seq: Any, i: int) -> Any:
    try:
        return seq[i]
    except (TypeError, IndexError, KeyError):
        return None


__all__ = [
    "LLMProvider",
    "CompletionResult",
    "ToolCall",
    "resolve_model",
    "model_supports_tools",
    "missing_credential",
    "MODEL_ALIASES",
]
