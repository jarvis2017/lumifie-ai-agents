"""Produce the committed example briefing in examples/.

Runs the real supervisor pipeline end to end over the offline demo data (stub
provider + seeded backends, auto-approved), so the example reflects actual agent
behavior. Writes through the real report module.

    python scripts/generate_example_output.py
"""

from __future__ import annotations

import tempfile
from pathlib import Path

from sales_ops.config import DEFAULT_CONFIG, SalesOpsSettings
from sales_ops.factory import build_orchestrator
from sales_ops.report import render_json, render_markdown

_ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    db = Path(tempfile.mkdtemp()) / "example.db"
    settings = SalesOpsSettings(model="claude-opus-4-8", db_path=str(db))
    orch = build_orchestrator(settings, DEFAULT_CONFIG, dry_run=False, demo=True, force_stub=True)
    try:
        result = orch.run("demo-pipeline")
    finally:
        orch.store.close()

    out = _ROOT / "examples"
    out.mkdir(parents=True, exist_ok=True)
    (out / "demo-pipeline.pipeline.json").write_text(render_json(result), encoding="utf-8")
    (out / "demo-pipeline.pipeline.md").write_text(render_markdown(result), encoding="utf-8")
    print(
        f"Wrote examples/demo-pipeline.pipeline.{{json,md}} "
        f"({len(result.leads)} leads, {len(result.actions)} actions)"
    )


if __name__ == "__main__":
    main()
