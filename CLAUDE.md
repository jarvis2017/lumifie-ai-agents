# CLAUDE.md — Working in this repository

Guidance for any Claude Code session operating in **lumifie-ai-agents**. Read this
first; it gives you the context, standards, and current state without being told.

---

## Project Identity

This is **Lumifie Consulting's public AI agent portfolio**. Everything here is
**production-grade and client-facing**. Code quality, documentation, and
architecture decisions reflect directly on Lumifie Consulting's professional
reputation. Treat every change as something a prospective client will read.

## Business Context

This portfolio supports **active Upwork client acquisition**. Agents should solve
**real business problems a non-technical client would immediately recognize and
pay for** (e.g. "review this contract for risks", "watch my competitors").

- Lead with the business problem, not the technology.
- **When in doubt, optimize for client-facing clarity over technical cleverness.**
- Every agent must produce output an executive can act on (Markdown brief + JSON).

> Public-facing note: keep the **root README free of explicit "Upwork" mentions**
> (per the owner's preference). Describe the work as client delivery.

## Code Standards

- **Python 3.12+**.
- **ruff** for linting — must pass clean (`ruff check .`) before any commit.
- **Type hints on everything** — all functions, parameters, and returns typed.
- **loguru** for logging (via `lumifie_core.logger` / `configure_logging`).
- **tenacity** for retries on transient failures (via `lumifie_core.retrying`).
- **pytest** for tests — every package has a suite that runs **offline** (inject
  the LLM and any external I/O so there are no network calls or API keys in tests).
- **No shortcuts on error handling.** Validate at boundaries, fail with clear
  messages, never swallow errors silently.
- **Every agent must actually run end to end** — a real CLI, a real pipeline, and
  a committed example output produced by the real rendering code.

## Architecture Rules

- **All agents import shared infrastructure from `lumifie_core`** — never
  re-implement provider access, logging, retries, config, or the base agent
  locally.
- **All agents support multiple LLM providers via litellm** through
  `lumifie_core.LLMProvider`. Selection via `--model` flag or `LITELLM_MODEL` env.
- **Default model is `claude-opus-4-8`** (alias `claude`). Do not change the
  default or downgrade for cost without the owner's say-so.
- **Tool use is preferred over JSON mode where supported.** Claude and GPT-4o use
  native function/tool calling; models without it (e.g. Ollama) fall back to
  JSON-mode structured extraction **with a logged warning** — every agent should
  implement both paths.
- Use the **OpenAI/litellm message + function-tool format** everywhere (via
  `lumifie_core.chat`), not Anthropic-native blocks.
- `temperature` is left unset by default (Opus 4.8 rejects sampling params); only
  send it when a chosen model supports it.

## README Standard

Every **agent** README follows this **exact 10-section structure**, in order.
Use `contract-intelligence-agent/README.md` as the canonical reference.

1. **The Business Problem** — 2-3 paragraphs for a non-technical business owner:
   the pain point and what it costs in time/money. No jargon, no code.
2. **Who This Is For** — bullet list of specific roles/industries served.
3. **How It Works** — a **Mermaid.js flowchart** of the full pipeline from input
   to output, **accurate to the actual code**.
4. **Agent Architecture** — a table listing each agent/module, its role, inputs,
   outputs, and tools it uses.
5. **Example Output** — real representative output (a JSON snippet **and** a
   Markdown summary), not placeholder text.
6. **Technical Stack** — shields.io badges **and** a table (Language, Framework,
   LLM provider, vector DB if used, etc.).
7. **Setup & Usage** — step by step, assuming zero prior knowledge.
8. **Configuration** — full `.env` reference table with a description and default
   for **every** variable.
9. **Supported Models** — a table showing Claude / GPT-4o / Ollama support level
   (Full / Partial / Experimental) **per feature**.
10. **Limitations & Roadmap** — honest about what it can't do yet and what's next.

The root README is the **portfolio index** (agent table + shared pattern), not an
agent README, so it does not follow the 10-section structure.

## Git Discipline

- **Meaningful commit messages** — explain what changed and why.
- **Never commit `.env` files** (only `.env.example`). Never commit secrets, API
  keys, `.venv/`, `__pycache__/`, `*.db`, or generated reports (keep `examples/`).
- **Always update the root README index** (the agent table) when adding a new agent.
- End commit messages with the standard co-author trailer.
- Keep commits scoped; don't mix unrelated changes.

## Directory Structure

```
lumifie-ai-agents/
├── CLAUDE.md                     # this file
├── README.md                     # portfolio index (agent table + shared pattern)
├── .github/workflows/ci.yml      # CI: ruff + pytest across all packages on push to main
├── lumifie-core/                 # SHARED foundation — import package `lumifie_core`
│   └── src/lumifie_core/         #   provider (litellm), chat, agent (BaseAgent),
│                                 #   config (CoreSettings), logging, retry
├── contract-intelligence-agent/  # agent: PDF contract analysis
├── competitive-intel-agent/      # agent: competitor research + run-over-run diffs
└── docs/                         # (optional) shared cross-agent documentation
```

- **`lumifie-core/`** — the shared package. Directory is hyphenated
  (`lumifie-core`); the importable Python package is `lumifie_core`. Installed
  editable; each agent depends on it via `[tool.uv.sources]` (path).
- **Each agent in its own directory**, self-contained with the standard layout:
  `src/<pkg>/`, `tests/`, `config/`, `scripts/`, `examples/`, `pyproject.toml`
  (hatchling, `[project.scripts]` CLI), `requirements.txt`, `.env.example`,
  MIT `LICENSE`, `README.md`.
- **`.github/workflows/`** — CI. Install `lumifie-core` editable first, then each
  agent `[dev]`, then run ruff + pytest per package.
- **`docs/`** — for any shared documentation that spans agents (create when needed).

### New-agent checklist

1. `src/<pkg>/`: `models.py`, `agent.py` (subclass `lumifie_core.BaseAgent`),
   `tools.py`, `config.py` (subclass `CoreSettings`), `cli.py`, `report.py`.
2. Inject the provider and any external I/O so the full pipeline tests offline.
3. Implement **both** a native tool-use path and a JSON-mode fallback.
4. `tests/`, `config/`, `scripts/`, `examples/`, `pyproject.toml`
   (depend on `lumifie-core`), `requirements.txt`, `.env.example`, MIT `LICENSE`,
   a 10-section `README.md`.
5. Add a committed example produced by the real code.
6. **Update the root README agent table.**

## Current State

**Built:**

- **`lumifie-core`** — provider abstraction (litellm, multi-model, tool-use
  capability detection + JSON fallback, injectable for tests), shared logging,
  retries, `CoreSettings`, `BaseAgent`, `chat` helpers. Tests + ruff clean.
- **`contract-intelligence-agent`** — ingests a PDF contract, extracts/analyzes
  clauses (payment, termination, IP, liability, dispute resolution), flags risks,
  outputs JSON + Markdown. Multi-step tool loop; page-aware chunking; JSON fallback.
- **`competitive-intel-agent`** — researches competitors via web search, synthesizes
  positioning/pricing/threats, stores runs in SQLite, **diffs run-over-run**, emits
  an executive brief (Markdown + JSON). Cron wrapper for scheduled runs.
- **CI** — GitHub Actions running ruff + pytest across all packages (green); badge
  in the root README.

**Planned next:**

- Migrate the two existing agent READMEs to the 10-section standard above.
- Additional agents that map to recognizable client jobs (e.g. invoice/document
  extraction, lead-research, support-ticket triage).
- Optional: `uv` workspace for one-command monorepo installs; per-agent CI badges;
  a `docs/` page describing the shared pattern in depth.

---

_Last updated: 2026-06-21. Keep this file current — it is the first thing a new
session reads._
