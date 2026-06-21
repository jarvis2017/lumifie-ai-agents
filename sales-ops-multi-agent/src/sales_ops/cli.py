"""CLI for the sales-ops multi-agent."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from lumifie_core import configure_logging, logger

from sales_ops import __version__
from sales_ops.config import SalesOpsSettings, load_config
from sales_ops.factory import build_orchestrator
from sales_ops.report import render_json, render_markdown


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="sales-ops",
        description=(
            "Run the B2B sales pipeline: prospect → outreach → reply-handling → "
            "CRM sync → report, supervised by LangGraph with a human approval gate."
        ),
    )
    p.add_argument("run", nargs="?", default="run", choices=["run"], help="Run the pipeline.")
    p.add_argument("--config", default=None, help="Path to the YAML business config.")
    p.add_argument("--demo", action="store_true", help="Use seeded offline demo data (no network).")
    p.add_argument(
        "--dry-run", action="store_true", help="Show what would happen; execute nothing."
    )
    p.add_argument(
        "--yes", action="store_true", help="Auto-approve external actions (non-interactive)."
    )
    p.add_argument(
        "--db", default=None, help="SQLite path (default: SALESOPS_DB or ./sales_ops.db)."
    )
    p.add_argument("--model", default=None, help="Model alias/id (or LITELLM_MODEL).")
    p.add_argument("-o", "--out-dir", default=".", help="Where to write the briefing files.")
    p.add_argument("--print", dest="print_md", action="store_true", help="Print the briefing.")
    p.add_argument("--log-level", default=None)
    p.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    return p


def run(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    settings = SalesOpsSettings.from_env(
        model=args.model, log_level=args.log_level, config_path=args.config, db_path=args.db
    )
    configure_logging(settings.log_level)

    try:
        config = load_config(settings.config_path)
    except Exception as exc:  # noqa: BLE001
        logger.error("Could not load config {}: {}", settings.config_path, exc)
        return 1
    if args.yes:
        config.approval.channel = "auto"

    orch = build_orchestrator(settings, config, dry_run=args.dry_run, demo=args.demo)
    try:
        result = orch.run()
    except Exception as exc:  # noqa: BLE001
        logger.exception("Pipeline failed: {}", exc)
        return 1
    finally:
        orch.store.close()

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    stem = result.pipeline_id
    (out_dir / f"{stem}.pipeline.json").write_text(render_json(result), encoding="utf-8")
    markdown = render_markdown(result)
    (out_dir / f"{stem}.pipeline.md").write_text(markdown, encoding="utf-8")

    m = result.report.metrics if result.report else None
    logger.bind(agent="sales-ops").success(
        "Pipeline {} done ({}). {} leads, {} actions executed.",
        stem,
        "dry-run" if result.dry_run else "live",
        len(result.leads),
        m.actions_executed if m else 0,
    )
    logger.info("Wrote {}/{}.pipeline.json and .md", out_dir, stem)

    if args.print_md:
        print("\n" + markdown)
    return 0


def main() -> None:
    sys.exit(run())


if __name__ == "__main__":
    main()
