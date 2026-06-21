# lumifie-ai-agents

[![CI](https://github.com/jarvis2017/lumifie-ai-agents/actions/workflows/ci.yml/badge.svg)](https://github.com/jarvis2017/lumifie-ai-agents/actions/workflows/ci.yml)

Production-grade AI agents by **Lumifie Consulting**. Each agent is a self-contained,
tested project built on a shared foundation, runnable against multiple model
providers (Anthropic Claude, OpenAI, local Ollama) through one abstraction.

## Agents

| Project | What it does | Supported models | Highlights |
|---|---|---|---|
| [**contract-intelligence-agent**](contract-intelligence-agent/) | Ingests a PDF contract, extracts & analyzes key clauses (payment, termination, IP, liability, dispute resolution), flags risks, and outputs a JSON report + Markdown summary. | `claude` (default), `gpt-4o`, `ollama/*` | Multi-step tool-use loop; page-aware chunking; JSON-mode fallback |
| [**competitive-intel-agent**](competitive-intel-agent/) | Researches a company's competitors via web search, synthesizes positioning/pricing/threats, **diffs against prior runs (SQLite)**, and emits an executive brief. Cron-ready. | `claude` (default), `gpt-4o`, `ollama/*` | Agentic web research; run-over-run change log; scheduled runs |
| [**lead-research-agent**](lead-research-agent/) | Given a target company URL, three sub-agents enrich it (web search + Jina Reader), score it against a configurable ICP, and draft personalized email + LinkedIn outreach. | `claude` (default), `gpt-4o`, `ollama/*` | **LangGraph** multi-agent; Pydantic structured outputs; configurable ICP |
| [**inbound-triage-agent**](inbound-triage-agent/) | A FastAPI webhook that classifies inbound replies (interested / objection / wrong-person / OOO / spam) and routes them: RAG rebuttal (Chroma), booking link, or contact extraction. | `claude` (default), `gpt-4o`, `ollama/*` | **FastAPI** async; **Chroma** RAG; `python main.py --mock-email` runs offline |
| [**rag-knowledge-chatbot**](rag-knowledge-chatbot/) | Upload documents (PDF/Word/text/URLs) and get a chatbot that answers with exact source citations and confidence scores. Incremental ingestion; demo dataset included. | `claude` (default), `gpt-4o`, `ollama/*` | **Chroma** + sentence-transformers; FastAPI + CLI + optional Gradio UI; cited answers |
| [**crm-automation-agent**](crm-automation-agent/) | Monitors HubSpot/Airtable for triggers (new lead, stale deal, overdue follow-up, missing fields) and takes rule-based actions behind a human approval gate, with a SQLite audit trail. | `claude` (default), `gpt-4o`, `ollama/*` | YAML rules; **human approval gate**; SQLite audit; offline `--source demo` |
| [**regulatory-monitor-agent**](regulatory-monitor-agent/) | Plans → researches → analyzes regulatory updates for a business profile, diffs against prior runs (SQLite), and emits a weekly digest of only what's new, in plain English. | `claude` (default), `gpt-4o`, `ollama/*` | 3-stage planner/researcher/analyst; run-over-run diff; cron-ready |
| [**lumifie-core**](lumifie-core/) | Shared foundation every agent imports. | — | Provider abstraction, logging, retries, config, base agent |

## The shared pattern (`lumifie-core`)

Every agent is built the same way, so they're consistent and swappable:

- **One model abstraction** — `lumifie_core.LLMProvider` (backed by
  [litellm](https://github.com/BerriAI/litellm)) resolves a friendly model name
  and handles tool-use vs. JSON-mode fallback:

  | `--model` / `LITELLM_MODEL` | Resolves to | Tool use |
  |---|---|---|
  | *(unset)* / `claude` | `claude-opus-4-8` (default) | native |
  | `gpt-4o` | OpenAI GPT-4o | native |
  | `ollama/llama3.1` | local Ollama | JSON-mode fallback (warned) |

- **Shared logging** (loguru), **retries** (tenacity), **config loader**
  (`CoreSettings`), and a **`BaseAgent`** base class — all in `lumifie-core`.
- **Injectable seams** (the LLM call and any external I/O like web search) so each
  agent's full pipeline is **tested with no network and no API keys** — see each
  project's test suite. CI runs `ruff` + `pytest` across all packages on every push.

### Adding a new agent

1. `src/<pkg>/` with `models.py`, `agent.py` (subclass `lumifie_core.BaseAgent`),
   `tools.py`, `config.py` (subclass `CoreSettings`), `cli.py`, `report.py`.
2. `tests/`, `config/`, `scripts/`, `examples/`, `pyproject.toml`
   (depend on `lumifie-core` via `[tool.uv.sources]`), `requirements`/`.env.example`,
   MIT `LICENSE`, `README.md`.
3. Inject the provider and external I/O so the pipeline is testable offline.

## Quickstart

```bash
# install the shared core, then an agent (each agent has its own venv)
uv pip install -e ./lumifie-core
cd contract-intelligence-agent
uv venv --python 3.12 && uv pip install -e ".[dev]"
cp .env.example .env   # set ANTHROPIC_API_KEY (or OPENAI_API_KEY)
pytest                 # full pipeline runs offline
```

## Stack

- **Python 3.12** managed with [`uv`](https://github.com/astral-sh/uv)
- **litellm** for provider-agnostic model access
- Default model: **Claude Opus 4.8** (`claude-opus-4-8`)

## License

MIT © 2026 Lumifie Consulting. Each project includes its own `LICENSE`.
