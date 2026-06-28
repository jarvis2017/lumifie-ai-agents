"""Two-tier LLM access: a quality tier and a fast/cheap tier.

Route by intent, not by model id:

* ``tier="quality"`` → Claude Opus 4.8 (via ``ANTHROPIC_API_KEY``). Use where output
  quality directly affects revenue (e.g. client-facing proposals, deep analysis).
* ``tier="fast"`` → an OpenRouter free model (via ``OPENROUTER_API_KEY``) for
  parsing, formatting, classification, and boilerplate.

Both tiers are :class:`LLMProvider` instances under the hood, so the network call is
injectable and the whole thing is testable offline.
"""

from __future__ import annotations

import os
from typing import Any

from lumifie_core.logging import logger
from lumifie_core.provider import CompletionResult, LLMProvider

QUALITY_DEFAULT = "claude-opus-4-8"
FAST_DEFAULT = "openrouter/google/gemini-2.0-flash-exp:free"

# Nvidia Build (OpenAI-compatible) hosting Meta's Llama 3.3 70B Instruct. When the
# NVIDIA_BUILD_API env var is set, the quality tier routes here instead of Claude.
# NOTE: do NOT use Chinese-origin models here (Kimi/DeepSeek/Qwen) — they leak CJK
# characters and control tokens on English business content (moonshotai/kimi-k2.6 was
# confirmed broken 2026-06-28). Llama 3.3 70B is English-native and emits clean output.
NVIDIA_BUILD_BASE = "https://integrate.api.nvidia.com/v1"
NVIDIA_QUALITY_MODEL = "openai/meta/llama-3.3-70b-instruct"

_TIERS = ("quality", "fast")


def _empty_usage() -> dict[str, int]:
    return {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0}


def nvidia_quality_override() -> tuple[str, str, str] | None:
    """If ``NVIDIA_BUILD_API`` is set, return (model, api_base, api_key) for the
    quality tier (Nvidia Build serving Llama 3.3 70B); otherwise ``None``."""
    key = os.getenv("NVIDIA_BUILD_API")
    if not key:
        return None
    return (NVIDIA_QUALITY_MODEL, NVIDIA_BUILD_BASE, key)


class TieredLLM:
    """A two-tier façade over two :class:`LLMProvider` instances."""

    def __init__(
        self,
        *,
        quality_model: str | None = None,
        fast_model: str | None = None,
        max_tokens: int = 4096,
        max_retries: int = 4,
        request_timeout: int = 600,
        quality: LLMProvider | None = None,
        fast: LLMProvider | None = None,
    ) -> None:
        self.quality = quality or self._build_quality(
            quality_model, max_tokens=max_tokens, max_retries=max_retries,
            request_timeout=request_timeout,
        )
        self.fast = fast or LLMProvider(
            fast_model or FAST_DEFAULT,
            max_tokens=max_tokens,
            max_retries=max_retries,
            request_timeout=request_timeout,
        )
        self.usage: dict[str, dict[str, int]] = {"quality": _empty_usage(), "fast": _empty_usage()}

    @staticmethod
    def _build_quality(
        quality_model: str | None, *, max_tokens: int, max_retries: int, request_timeout: int
    ) -> LLMProvider:
        """Build the quality provider, auto-routing to Nvidia Build (Llama 3.3 70B)
        when ``NVIDIA_BUILD_API`` is set."""
        override = nvidia_quality_override()
        if override:
            model, api_base, api_key = override
            logger.info("Quality tier -> Nvidia Build ({}).", model)
            return LLMProvider(
                model, api_base=api_base, api_key=api_key, max_tokens=max_tokens,
                max_retries=max_retries, request_timeout=request_timeout,
            )
        return LLMProvider(
            quality_model or QUALITY_DEFAULT, max_tokens=max_tokens,
            max_retries=max_retries, request_timeout=request_timeout,
        )

    @classmethod
    def from_env(cls, *, max_tokens: int = 4096) -> TieredLLM:
        """Build from env: QUALITY_MODEL / FAST_MODEL override the defaults."""
        return cls(
            quality_model=os.getenv("QUALITY_MODEL") or QUALITY_DEFAULT,
            fast_model=os.getenv("FAST_MODEL") or FAST_DEFAULT,
            max_tokens=max_tokens,
        )

    def provider_for(self, tier: str) -> LLMProvider:
        if tier not in _TIERS:
            raise ValueError(f"tier must be one of {_TIERS}, got {tier!r}")
        return self.quality if tier == "quality" else self.fast

    def complete(
        self,
        prompt: str,
        *,
        tier: str = "fast",
        system: str | None = None,
        max_tokens: int | None = None,
        response_format: dict[str, Any] | None = None,
        tools: list[dict[str, Any]] | None = None,
        tool_choice: str | dict[str, Any] | None = None,
    ) -> CompletionResult:
        """Run a single-prompt completion on the chosen tier; track token usage."""
        from lumifie_core import chat  # local import avoids import-order coupling

        messages = ([chat.system(system)] if system else []) + [chat.user(prompt)]
        result = self.provider_for(tier).complete(
            messages,
            tools=tools,
            tool_choice=tool_choice,
            response_format=response_format,
            max_tokens=max_tokens,
        )
        acc = self.usage[tier]
        for key in acc:
            acc[key] += int(result.usage.get(key, 0))
        return result

    def call(
        self,
        prompt: str,
        *,
        tier: str = "fast",
        system: str | None = None,
        max_tokens: int | None = None,
    ) -> str:
        """Convenience: return just the text for ``prompt`` on ``tier``."""
        return self.complete(prompt, tier=tier, system=system, max_tokens=max_tokens).text or ""

    def total_usage(self) -> dict[str, int]:
        out = _empty_usage()
        for tier in _TIERS:
            for key in out:
                out[key] += self.usage[tier][key]
        return out


__all__ = [
    "TieredLLM",
    "QUALITY_DEFAULT",
    "FAST_DEFAULT",
    "nvidia_quality_override",
    "NVIDIA_BUILD_BASE",
    "NVIDIA_QUALITY_MODEL",
]
