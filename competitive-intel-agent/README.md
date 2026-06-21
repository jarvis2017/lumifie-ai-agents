# Competitive Intelligence Agent

> Autonomous competitor research, on demand or on a schedule. Give it a **company**
> and a **market vertical**; it researches competitors via web search, synthesizes
> positioning / pricing / threat landscape, **diffs against the previous run** to
> surface what changed, and emits an executive brief in **Markdown** and **JSON**.
>
> Built by **[Lumifie Consulting](https://github.com/jarvis2017/lumifie-ai-agents)** on
> [`lumifie-core`](../lumifie-core) • MIT licensed

## What it does

1. **Researches** — a tool-using agent issues focused `web_search` queries
   (DuckDuckGo, no API key), digging into each serious competitor.
2. **Synthesizes** — records competitors (positioning, pricing, strengths,
   weaknesses) and material threats with actionable recommendations.
3. **Diffs** — compares this run to the most recent prior run stored in SQLite and
   reports new/dropped competitors, pricing & positioning shifts, and threat-level
   changes.
4. **Briefs** — writes `<company>_<vertical>.brief.md` and `.brief.json`.
5. **Runs on a schedule** — a cron wrapper appends to the SQLite history so each
   brief leads with "what changed since last run".

## Multi-model (via lumifie-core)

```bash
competitive-intel -c "Acme" -m "project management SaaS"                 # claude (default)
competitive-intel -c "Acme" -m "project management SaaS" --model gpt-4o  # OpenAI
competitive-intel -c "Acme" -m "project management SaaS" --model ollama/llama3.1  # local
```

Claude and GPT-4o use native tool use for the research loop; Ollama and other
local models fall back to a fixed-query research pass plus a single JSON-mode
synthesis call (with a warning). Model also settable via `LITELLM_MODEL`.

## Architecture

```
 company + vertical
        │
        ▼
   ┌─────────┐   web_search tool   ┌──────────────┐
   │  agent  │ ──────────────────▶ │ SearchBackend│ (DuckDuckGo / injectable)
   │ (loop)  │ ◀────────────────── └──────────────┘
   │         │ record_competitor / record_threat / finalize_brief
   └────┬────┘  via lumifie_core LLMProvider (litellm, retries)
        ▼
   IntelReport ──▶ store.py (SQLite history)
        │              │ latest() previous run
        ▼              ▼
     diff.py ◀─────────┘   → list[Change]
        ▼
    report.py  → <company>_<vertical>.brief.md / .brief.json
```

| Module | Responsibility |
|---|---|
| `search.py` | `SearchBackend` protocol + DuckDuckGo backend (injectable for tests). |
| `agent.py` | Agentic research loop (tool path) + JSON-mode fallback. |
| `store.py` | SQLite persistence of every run, keyed by (company, vertical). |
| `diff.py` | Run-over-run change detection. |
| `report.py` | Markdown + JSON brief, including the change log. |
| `models.py` | Pydantic models (Competitor, Threat, IntelReport, Change). |
| `config.py` | `CompetitiveSettings` (extends `lumifie_core.CoreSettings`). |
| `cli.py` | `competitive-intel` entry point; orchestrates research → diff → render. |

## Install

```bash
# from the repo root, install the shared core first
uv pip install -e ./lumifie-core
cd competitive-intel-agent
uv venv --python 3.12 && uv pip install -e ".[dev]"
cp .env.example .env   # set ANTHROPIC_API_KEY (or OPENAI_API_KEY)
```

## Run

```bash
set -a; . ./.env; set +a
competitive-intel --company "Northwind Analytics" \
                  --vertical "product analytics SaaS" \
                  --out-dir ./reports --print
```

Run it again later and the brief's **"What Changed Since Last Run"** section
populates automatically from the SQLite history.

### Scheduled (cron)

```bash
chmod +x scripts/run_scheduled.sh
# Every Monday 07:00:
# 0 7 * * 1 cd /opt/competitive-intel-agent && \
#   scripts/run_scheduled.sh "Northwind Analytics" "product analytics SaaS" >> /var/log/ci.log 2>&1
```

## Example output

See [`examples/`](examples/) — a brief for a fictional "Northwind Analytics" with a
populated change log (PostHog newly emerged, Mixpanel repricing, threat level
risen). Generated through the real report code via
`python scripts/generate_example_output.py`.

## Testing

The LLM **and** the search backend are injected, so the full pipeline — research
loop, JSON fallback, SQLite persistence, diffing, rendering — runs in tests with
no network and no API keys.

```bash
pytest
ruff check .
```

## Limitations

- Web results reflect what DuckDuckGo returns at run time; always verify before
  acting. Output is informational, not advice.

MIT © 2026 Lumifie Consulting.
