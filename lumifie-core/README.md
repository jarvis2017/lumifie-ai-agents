# lumifie-core

Shared foundation for every AI agent in the
[lumifie-ai-agents](https://github.com/jarvis2017/lumifie-ai-agents) portfolio.
Each agent imports from here so they share one consistent, swappable base.

## What it provides

| Module | Purpose |
|---|---|
| `provider` | `LLMProvider` — multi-model access via **litellm**. Alias resolution, capability detection (native tool use vs JSON-mode fallback), normalized results, retries. |
| `chat` | OpenAI-style message + function-tool builders used across providers. |
| `agent` | `BaseAgent` — common wiring (provider, settings, bound logger, token accounting). |
| `config` | `CoreSettings` dataclass + env loader; agents subclass it. |
| `logging` | One loguru setup (`configure_logging`, `logger`). |
| `retry` | `retrying(...)` — tenacity exponential backoff with logging. |

## Model selection

`LLMProvider` resolves a friendly alias (or `LITELLM_MODEL`) into a concrete model:

| Input (`--model` / `LITELLM_MODEL`) | Resolves to | Tool use |
|---|---|---|
| *(unset)* / `claude` | `claude-opus-4-8` (default) | native |
| `gpt-4o` | `gpt-4o` (OpenAI) | native |
| `ollama/llama3.1` | local Ollama instance | **JSON-mode fallback** (warned) |
| any other id | passed straight to litellm | detected |

`provider.supports_tools` tells an agent whether to use native function calling
or the JSON-mode structured-extraction fallback. Credentials are read from the
environment by litellm (`ANTHROPIC_API_KEY`, `OPENAI_API_KEY`, `OLLAMA_API_BASE`, …).

## Use it

```python
from lumifie_core import LLMProvider, CoreSettings, BaseAgent, chat

settings = CoreSettings.from_env(model="gpt-4o")
provider = LLMProvider.from_settings(settings)

result = provider.complete([chat.system("You are helpful."), chat.user("Hi")])
print(result.text)
```

The network call is injectable (`completion_fn`), so agents built on this package
are fully testable with no network or API keys.

## Develop

```bash
uv pip install -e ".[dev]"
pytest
ruff check .
```

MIT © 2026 Lumifie Consulting.
