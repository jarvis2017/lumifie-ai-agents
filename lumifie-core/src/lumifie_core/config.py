"""Shared configuration base for Lumifie agents.

:class:`CoreSettings` holds the provider-agnostic knobs every agent needs.
Individual agents subclass it to add their own fields (see how the contract agent
adds chunking settings) and reuse the env helpers here.

Model resolution precedence: explicit value > ``LITELLM_MODEL`` env var > default
``"claude"`` (which the provider expands to ``claude-opus-4-8``).
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any, TypeVar

T = TypeVar("T", bound="CoreSettings")


def env_int(name: str, default: int) -> int:
    raw = os.getenv(name)
    if not raw or not raw.strip():
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def env_float(name: str, default: float | None) -> float | None:
    raw = os.getenv(name)
    if not raw or not raw.strip():
        return default
    try:
        return float(raw)
    except ValueError:
        return default


@dataclass
class CoreSettings:
    """Provider-agnostic settings common to all agents."""

    # Model alias ("claude" / "gpt-4o" / "ollama/llama3.1") or a full id.
    model: str = "claude"
    max_tokens: int = 8000
    # Left as None by default: some models (e.g. Claude Opus 4.8) reject sampling
    # params, so we only send temperature when explicitly set.
    temperature: float | None = None
    # Optional cross-provider reasoning effort ("low"/"medium"/"high"); only sent
    # when set, since not every model accepts it.
    reasoning_effort: str | None = None
    max_retries: int = 4
    request_timeout: int = 600
    log_level: str = "INFO"

    @classmethod
    def from_env(cls: type[T], **overrides: Any) -> T:
        """Build settings from environment variables, then apply ``overrides``.

        Overrides whose value is ``None`` are ignored, so callers can pass CLI
        flags straight through without clobbering env/defaults.
        """
        base = cls(
            model=os.getenv("LITELLM_MODEL") or "claude",
            max_tokens=env_int("LUMIFIE_MAX_TOKENS", 8000),
            temperature=env_float("LUMIFIE_TEMPERATURE", None),
            reasoning_effort=os.getenv("LUMIFIE_REASONING_EFFORT") or None,
            max_retries=env_int("LUMIFIE_MAX_RETRIES", 4),
            request_timeout=env_int("LUMIFIE_REQUEST_TIMEOUT", 600),
            log_level=os.getenv("LUMIFIE_LOG_LEVEL", "INFO"),
        )
        for key, value in overrides.items():
            if value is not None and hasattr(base, key):
                setattr(base, key, value)
        return base


__all__ = ["CoreSettings", "env_int", "env_float", "field"]
