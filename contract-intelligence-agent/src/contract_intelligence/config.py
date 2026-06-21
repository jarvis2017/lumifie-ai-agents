"""Runtime configuration, resolved from environment variables with sane defaults.

A single :class:`Settings` object is threaded through the agent so behaviour
(model, effort, chunking, retries) is configurable without touching code.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field

# Default to the latest, most capable Claude model. See the model catalog in the
# claude-api reference; do not append a date suffix to this alias.
DEFAULT_MODEL = "claude-opus-4-8"


def _env_int(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None or raw.strip() == "":
        return default
    try:
        return int(raw)
    except ValueError:
        return default


@dataclass(slots=True)
class Settings:
    """Resolved configuration for one run of the agent."""

    api_key: str | None = field(default=None)
    model: str = DEFAULT_MODEL
    # Reasoning depth: low | medium | high | max. "high" balances rigor and cost
    # for legal analysis; bump to "max" for high-stakes contracts.
    effort: str = "high"
    # Per-response output cap. Kept under ~16k so non-streaming calls stay well
    # inside SDK HTTP timeouts.
    max_tokens: int = 8000
    # Approximate characters per chunk fed to the model. ~12k chars ≈ 3k tokens,
    # leaving generous room for the system prompt, tools, and accumulated state.
    max_chunk_chars: int = 12_000
    # Safety valve on the tool-execution loop within a single chunk.
    max_iterations_per_chunk: int = 8
    # tenacity retry budget for transient API failures (on top of SDK retries).
    max_retries: int = 4
    log_level: str = "INFO"

    @classmethod
    def from_env(cls) -> Settings:
        """Build settings from the process environment."""
        return cls(
            api_key=os.getenv("ANTHROPIC_API_KEY"),
            model=os.getenv("CONTRACT_AGENT_MODEL", DEFAULT_MODEL),
            effort=os.getenv("CONTRACT_AGENT_EFFORT", "high"),
            max_tokens=_env_int("CONTRACT_AGENT_MAX_TOKENS", 8000),
            max_chunk_chars=_env_int("CONTRACT_AGENT_MAX_CHUNK_CHARS", 12_000),
            max_iterations_per_chunk=_env_int("CONTRACT_AGENT_MAX_ITERS", 8),
            max_retries=_env_int("CONTRACT_AGENT_MAX_RETRIES", 4),
            log_level=os.getenv("CONTRACT_AGENT_LOG_LEVEL", "INFO"),
        )
