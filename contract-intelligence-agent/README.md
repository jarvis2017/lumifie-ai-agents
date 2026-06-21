# Contract Intelligence Agent

> Production-grade AI agent that reads a PDF contract, extracts and analyzes its
> key clauses, flags risks with actionable recommendations, and produces both a
> structured **JSON** report and a formatted **Markdown** summary.
>
> Built by **[Lumifie Consulting](https://github.com/jarvis2017/lumifie-ai-agents)** • MIT licensed

It focuses on the five clause families that drive most contract risk — **payment
terms, termination, IP ownership, liability, and dispute resolution** — and rates
each contract from a buyer's/counterparty's perspective.

---

## Why this is built the way it is

This is a real multi-step **agent**, not a single prompt:

- It walks the contract **page-aware, chunk-by-chunk** in one running
  conversation, so analysis of later sections is informed by earlier ones and
  large/multi-page PDFs never blow the context window.
- On each chunk the model drives a **tool-execution loop** — it repeatedly calls
  `record_clause` and `flag_risk` until it has nothing more to extract — then
  calls `finalize_analysis` once at the end for an overall rating and summary.
- The harness owns the loop, tool execution, logging, retries, and state; the
  model owns the judgement. This is the standard manual agentic-loop pattern,
  and it keeps the system debuggable and testable.

It uses the **Anthropic Python SDK** with **tool use** (strict schemas) for
reliable structured extraction, **adaptive thinking** + configurable **effort**
for legal-grade reasoning, **loguru** for logging, and **tenacity** for retry on
transient API failures.

---

## Architecture

```
                 ┌──────────────┐
   contract.pdf ─▶  pdf_loader  │  pypdf → pages → page-aware chunks
                 └──────┬───────┘
                        ▼
                 ┌──────────────┐      tools.py (strict schemas)
                 │    agent     │◀────  record_clause / flag_risk / finalize
                 │  (loop)      │
                 │              │──────▶ llm_client  ──▶  Anthropic Messages API
                 │              │        (tenacity retry, adaptive thinking,
                 └──────┬───────┘         effort, token accounting)
                        ▼
                 ┌──────────────┐
                 │  models.py   │  Pydantic: Clause / Risk / ContractReport
                 └──────┬───────┘
                        ▼
                 ┌──────────────┐
                 │   report.py  │  → <name>.report.json
                 └──────────────┘  → <name>.report.md
```

| Module | Responsibility |
|---|---|
| `pdf_loader.py` | Extract text per page; group pages into context-sized chunks (boundaries preserved for page citations). |
| `tools.py` | Anthropic tool schemas (`strict: true`) mirroring the data models. |
| `agent.py` | The multi-step loop: chunk feeding, tool execution, finalization, state. |
| `llm_client.py` | Retrying wrapper around the Messages API; the single seam tests stub. |
| `models.py` | Pydantic models — the source of truth for output shape. |
| `report.py` | JSON serialization + executive Markdown rendering. |
| `config.py` | Env-driven settings (model, effort, chunking, retries). |
| `cli.py` | `contract-intelligence` command-line entry point. |

---

## Install

Requires **Python 3.12+**. Using [uv](https://github.com/astral-sh/uv):

```bash
cd contract-intelligence-agent
uv venv --python 3.12
uv pip install -e ".[dev]"      # dev extras add pytest, reportlab, ruff
```

Or with pip:

```bash
python3.12 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
pip install -e .
```

## Configure

```bash
cp .env.example .env
# edit .env and set ANTHROPIC_API_KEY=sk-ant-...
set -a; . ./.env; set +a       # load it into your shell
```

All settings have sane defaults and can be overridden via environment variables
(see `.env.example`) or CLI flags.

## Run

```bash
# Generate the bundled sample contract (or bring your own PDF)
python scripts/make_sample_pdf.py examples/sample_contract.pdf

# Analyze it
contract-intelligence examples/sample_contract.pdf --out-dir ./reports --print
```

This writes `reports/sample_contract.report.json` and
`reports/sample_contract.report.md`.

```
usage: contract-intelligence [-h] [-o OUT_DIR] [--model MODEL]
                             [--effort {low,medium,high,max}] [--print]
                             [--log-level LOG_LEVEL] [--version]
                             pdf
```

You can also run it as a module: `python -m contract_intelligence <pdf>`.

---

## Example output

See [`examples/`](examples/) for a full sample run against the bundled
[`sample_contract.pdf`](examples/sample_contract.pdf) — a deliberately
vendor-favorable Master Services Agreement:

- [`sample_contract.report.json`](examples/sample_contract.report.json) — machine-readable
- [`sample_contract.report.md`](examples/sample_contract.report.md) — human-readable

Markdown excerpt:

```markdown
# Contract Analysis — sample_contract.pdf

**Overall risk:** 🟠 High
**Pages analyzed:** 3

## Executive Summary

This Master Services Agreement is materially vendor-favorable. The client bears
unlimited, uncapped indemnification while the provider may terminate for
convenience on 30 days' notice; IP assignment, auto-renewal, and a jury-trial
waiver compound the exposure. Recommend negotiating a liability cap and
mutual termination rights before signing.

## Risk Register
_5 risk(s) identified: 1 critical, 2 high, 2 medium._

### 1. 🔴 Critical — Uncapped client indemnification
*Category: Liability*

Section 5.2 makes the client's indemnification obligations explicitly unlimited
and carves them out of the mutual limitation-of-liability cap...

**Recommendation:** Cap total indemnity at fees paid in the trailing 12 months
and make the carve-out mutual.
```

---

## How extraction works (the agent loop)

1. **Load & chunk** — `pdf_loader` extracts text per page and groups pages into
   chunks of `~max_chunk_chars`, labeling each with `[Page N]` so the model can
   cite pages. A single oversized page is never truncated.
2. **Per-chunk extraction** — for each chunk the agent sends the section and runs
   a tool loop: the model emits `record_clause` / `flag_risk` calls, the harness
   validates each against the Pydantic models and records it, and returns
   tool results until the model is done with that section.
3. **Finalize** — after the last chunk, the agent asks for `finalize_analysis`,
   yielding the overall risk level and executive summary.
4. **Render** — state is assembled into a `ContractReport` and written as JSON
   and Markdown. Token usage is accumulated across every call for cost visibility.

Model behavior is tuned for legal review: `thinking={"type": "adaptive"}` with
`effort` (default `high`, raise to `max` for high-stakes deals).

---

## Testing

The agent's only external dependency (the LLM) is injected, so the **entire
pipeline runs in tests with no API key and no network** via a deterministic
scripted client — exercising chunking, the multi-step loop, finalization, and
rendering exactly as the live path does.

```bash
pytest                 # full suite
pytest --cov=contract_intelligence --cov-report=term-missing
ruff check .
```

---

## Configuration reference

| Env var | Default | Meaning |
|---|---|---|
| `ANTHROPIC_API_KEY` | — | **Required** for live runs. |
| `CONTRACT_AGENT_MODEL` | `claude-opus-4-8` | Claude model id. |
| `CONTRACT_AGENT_EFFORT` | `high` | Reasoning effort: `low`/`medium`/`high`/`max`. |
| `CONTRACT_AGENT_MAX_TOKENS` | `8000` | Per-response output cap. |
| `CONTRACT_AGENT_MAX_CHUNK_CHARS` | `12000` | Approx. chars per chunk. |
| `CONTRACT_AGENT_MAX_ITERS` | `8` | Max tool iterations per chunk. |
| `CONTRACT_AGENT_MAX_RETRIES` | `4` | tenacity retry attempts on transient errors. |
| `CONTRACT_AGENT_LOG_LEVEL` | `INFO` | loguru level. |

---

## Limitations

- **No OCR.** Scanned-image PDFs with no text layer are rejected with a clear
  error rather than silently returning nothing.
- **Not legal advice.** Output is an informational aid for review, not a
  substitute for a qualified attorney.

---

## License

MIT © 2026 Lumifie Consulting. See [LICENSE](LICENSE).
