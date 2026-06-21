"""Base class for all Lumifie agents.

Provides the common wiring — provider, settings, a bound logger, and token
accounting — so each agent only implements its own ``run`` logic. Keeping this
shared keeps every agent in the portfolio consistent and swappable.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from lumifie_core.config import CoreSettings
from lumifie_core.logging import logger
from lumifie_core.provider import CompletionResult, LLMProvider


class BaseAgent(ABC):
    """Common base for agents. Subclasses set ``name``/``description`` and ``run``."""

    name: str = "agent"
    description: str = ""

    def __init__(self, provider: LLMProvider, settings: CoreSettings) -> None:
        self.provider = provider
        self.settings = settings
        self.log = logger.bind(agent=self.name)
        self.token_usage: dict[str, int] = {
            "input_tokens": 0,
            "output_tokens": 0,
            "total_tokens": 0,
        }

    def complete(self, messages: list[dict[str, Any]], **kwargs: Any) -> CompletionResult:
        """Call the provider and accumulate token usage."""
        result = self.provider.complete(messages, **kwargs)
        for key in self.token_usage:
            self.token_usage[key] += int(result.usage.get(key, 0))
        return result

    @abstractmethod
    def run(self, *args: Any, **kwargs: Any) -> Any:
        """Execute the agent's task. Implemented by each agent."""
        raise NotImplementedError


__all__ = ["BaseAgent"]
