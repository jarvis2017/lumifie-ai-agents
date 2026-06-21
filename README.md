# lumifie-ai-agents

Production-grade AI agent projects — **Lumifie Consulting**.

This repository houses AI agent development, automation pipelines, and
client/Upwork delivery work.

## Stack

- **Python 3.12** managed with [`uv`](https://github.com/astral-sh/uv)
- **Docker** + Compose for reproducible runtimes
- Anthropic Claude models for agent reasoning

## Getting started

```bash
# create a project venv with uv
uv venv
source .venv/bin/activate
uv pip install -r requirements.txt   # or: uv add <pkg>
```

## Layout

| Path | Purpose |
|------|---------|
| `agents/`   | Agent implementations |
| `pipelines/`| Automation / data pipelines |
| `infra/`    | Docker, compose, deployment |

## License

Proprietary — © Lumifie Consulting. All rights reserved.
