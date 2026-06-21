"""Contract-agent settings: the shared :class:`CoreSettings` plus chunking knobs."""

from __future__ import annotations

from dataclasses import dataclass

from lumifie_core import CoreSettings, env_int


@dataclass
class ContractSettings(CoreSettings):
    """Core settings extended with PDF-chunking and loop controls."""

    # Approx. characters per chunk fed to the model (page boundaries preserved).
    max_chunk_chars: int = 12_000
    # Safety valve on the per-chunk tool-execution loop.
    max_iterations_per_chunk: int = 8

    @classmethod
    def from_env(cls, **overrides):
        settings = super().from_env(**overrides)
        settings.max_chunk_chars = env_int("CONTRACT_AGENT_MAX_CHUNK_CHARS", 12_000)
        settings.max_iterations_per_chunk = env_int("CONTRACT_AGENT_MAX_ITERS", 8)
        return settings


__all__ = ["ContractSettings"]
