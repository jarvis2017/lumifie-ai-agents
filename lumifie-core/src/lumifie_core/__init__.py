"""lumifie_core — shared foundation for Lumifie Consulting AI agents.

Exposes the provider abstraction (litellm-backed, multi-model), shared logging,
retry helpers, a config base, and a base agent class. Every agent in this repo
imports from here so they share one consistent, swappable foundation.
"""

from lumifie_core import chat, web
from lumifie_core.agent import BaseAgent
from lumifie_core.config import CoreSettings, env_float, env_int
from lumifie_core.logging import configure_logging, logger
from lumifie_core.provider import (
    MODEL_ALIASES,
    CompletionResult,
    LLMProvider,
    ToolCall,
    missing_credential,
    model_supports_tools,
    resolve_model,
)
from lumifie_core.retry import retrying

__version__ = "0.1.0"

__all__ = [
    "BaseAgent",
    "CompletionResult",
    "CoreSettings",
    "LLMProvider",
    "MODEL_ALIASES",
    "ToolCall",
    "chat",
    "configure_logging",
    "env_float",
    "env_int",
    "logger",
    "missing_credential",
    "model_supports_tools",
    "resolve_model",
    "retrying",
    "web",
    "__version__",
]
