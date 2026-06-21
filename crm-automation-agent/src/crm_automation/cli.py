"""Command-line entry point for the CRM automation agent.

    crm-automation run --rules config/rules.example.yaml --source demo --dry-run

``--source demo`` runs entirely offline against seeded sample data, so the tool
works immediately with no credentials. External mutations are gated: default
prompts per action, ``--yes`` auto-approves (for automation), ``--dry-run``
proposes and audits without executing or prompting.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from lumifie_core import configure_logging, logger

from crm_automation import __version__
from crm_automation.approval import auto_approve, interactive_approval
from crm_automation.audit import AuditLog
from crm_automation.config import CRMSettings
from crm_automation.factory import build_agent
from crm_automation.report import render_json, render_markdown


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="crm-automation",
        description=(
            "Monitor a CRM (HubSpot/Airtable) for trigger conditions and take "
            "human-gated actions per a YAML rules file, auditing everything."
        ),
    )
    sub = parser.add_subparsers(dest="command")
    run = sub.add_parser("run", help="Run one monitoring + action cycle.")
    run.add_argument(
        "--rules", default=None,
        help="Path to the YAML rules file (default: config/rules.example.yaml).",
    )
    run.add_argument(
        "--source", default=None, choices=["demo", "hubspot", "airtable"],
        help="CRM source. 'demo' runs offline on seeded data (default).",
    )
    gate = run.add_mutually_exclusive_group()
    gate.add_argument(
        "--dry-run", action="store_true",
        help="Propose and audit only; execute nothing and never prompt.",
    )
    gate.add_argument(
        "--yes", action="store_true",
        help="Auto-approve every external action (for automation/cron).",
    )
    run.add_argument("--db", default=None, help="Audit SQLite path (default: crm_audit.db).")
    run.add_argument(
        "--model", default=None,
        help="Model alias/id: claude (default), gpt-4o, ollama/llama3.1 (or LITELLM_MODEL).",
    )
    run.add_argument(
        "--out-dir", default=None, help="Optional dir to write the run report (.json/.md)."
    )
    run.add_argument("--print", dest="print_md", action="store_true", help="Print the run summary.")
    run.add_argument("--offline", action="store_true", help="Force the offline stub LLM provider.")
    run.add_argument("--log-level", default=None, help="DEBUG, INFO, WARNING, ERROR.")
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    return parser


def run(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command != "run":
        build_parser().print_help()
        return 0

    settings = CRMSettings.from_env(
        model=args.model,
        log_level=args.log_level,
        db_path=args.db,
        source=args.source,
        rules_path=args.rules,
    )
    configure_logging(settings.log_level)

    approver = auto_approve if args.yes else interactive_approval

    try:
        audit_log = AuditLog(settings.db_path)
    except Exception as exc:  # noqa: BLE001
        logger.error("Could not open audit DB {}: {}", settings.db_path, exc)
        return 1

    try:
        agent = build_agent(
            settings, approver=approver, audit_log=audit_log, force_stub=args.offline
        )
    except Exception as exc:  # noqa: BLE001 - clean CLI exit (e.g. missing creds/rules)
        logger.error("Could not build agent: {}", exc)
        audit_log.close()
        return 2

    try:
        summary = agent.run(dry_run=args.dry_run)
    except Exception as exc:  # noqa: BLE001
        logger.exception("Run failed: {}", exc)
        return 1
    finally:
        audit_log.close()

    markdown = render_markdown(summary)
    if args.out_dir:
        out_dir = Path(args.out_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / "run.json").write_text(render_json(summary), encoding="utf-8")
        (out_dir / "run.md").write_text(markdown, encoding="utf-8")
        logger.info("Wrote {} and {}", out_dir / "run.json", out_dir / "run.md")

    logger.bind(agent=agent.name).success(
        "Done. {} trigger(s), {} proposed, {} executed. Audit rows: {}.",
        len(summary.triggers), len(summary.proposed),
        len(summary.executed()), audit_log_count(settings.db_path),
    )

    if args.print_md or not args.out_dir:
        print("\n" + markdown)
    return 0


def audit_log_count(db_path: str) -> int:
    """Re-open the audit DB read-only to report the persisted row count."""
    log = AuditLog(db_path)
    try:
        return log.count()
    finally:
        log.close()


def main() -> None:
    sys.exit(run())


if __name__ == "__main__":
    main()
