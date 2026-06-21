"""Produce the committed example run in examples/.

Runs the real agent against the offline demo source (seeded FakeCRMClient) with
the offline stub LLM provider, in DRY-RUN mode, and renders both files through
the real report module — so the example is a genuine artifact of the production
code. With credentials, the CLI reproduces this live:

    crm-automation run --source demo --dry-run --print

    python scripts/generate_example_output.py
"""

from __future__ import annotations

from pathlib import Path

from crm_automation.approval import auto_approve
from crm_automation.audit import AuditLog
from crm_automation.config import CRMSettings
from crm_automation.factory import build_agent
from crm_automation.report import render_json, render_markdown

_ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    out_dir = _ROOT / "examples"
    out_dir.mkdir(parents=True, exist_ok=True)

    settings = CRMSettings(
        model="claude",
        source="demo",
        rules_path=str(_ROOT / "config" / "rules.example.yaml"),
        db_path=":memory:",
    )
    # In-memory audit DB + stub provider so this runs fully offline.
    audit_log = AuditLog(":memory:")
    agent = build_agent(
        settings, approver=auto_approve, audit_log=audit_log, force_stub=True
    )
    summary = agent.run(dry_run=True)
    audit_log.close()

    (out_dir / "example_run.json").write_text(render_json(summary), encoding="utf-8")
    (out_dir / "example_run.md").write_text(render_markdown(summary), encoding="utf-8")
    print(
        f"Wrote example run with {len(summary.triggers)} trigger(s) and "
        f"{len(summary.proposed)} proposed action(s) to examples/"
    )


if __name__ == "__main__":
    main()
