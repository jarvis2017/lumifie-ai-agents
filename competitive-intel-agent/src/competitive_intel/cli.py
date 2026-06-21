"""Command-line entry point for the competitive-intelligence agent.

    competitive-intel --company "Acme" --vertical "project management SaaS"

Produces ``<company>_<vertical>.brief.json`` and ``.brief.md`` and records the
run in SQLite so the next run can surface what changed.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

from lumifie_core import LLMProvider, configure_logging, logger
from lumifie_core.provider import missing_credential, resolve_model

from competitive_intel import __version__
from competitive_intel.agent import CompetitiveIntelAgent
from competitive_intel.config import CompetitiveSettings
from competitive_intel.diff import diff_reports
from competitive_intel.report import render_json, render_markdown
from competitive_intel.search import DDGSearchBackend
from competitive_intel.store import IntelStore


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="competitive-intel",
        description=(
            "Research a company's competitors, synthesize positioning/pricing/"
            "threats, diff against prior runs, and emit an executive brief."
        ),
    )
    parser.add_argument("-c", "--company", required=True, help="Company under study.")
    parser.add_argument("-m", "--vertical", required=True, help="Market vertical.")
    parser.add_argument("-o", "--out-dir", default=".", help="Output directory.")
    parser.add_argument(
        "--db", default=None, help="SQLite path (default: CI_DB_PATH or ./competitive_intel.db)."
    )
    parser.add_argument("--region", default=None, help="Search region (default: us-en).")
    parser.add_argument(
        "--model", default=None,
        help="Model alias/id: claude (default), gpt-4o, ollama/llama3.1, ... "
        "(or LITELLM_MODEL env var).",
    )
    parser.add_argument(
        "--reasoning-effort", default=None, choices=["low", "medium", "high"],
        help="Optional cross-provider reasoning effort.",
    )
    parser.add_argument("--print", dest="print_md", action="store_true", help="Print the brief.")
    parser.add_argument("--log-level", default=None, help="DEBUG, INFO, WARNING, ERROR.")
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    return parser


def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.strip().lower()).strip("-") or "x"


def run(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    settings = CompetitiveSettings.from_env(
        model=args.model,
        reasoning_effort=args.reasoning_effort,
        log_level=args.log_level,
        db_path=args.db,
        region=args.region,
    )
    configure_logging(settings.log_level)

    resolved = resolve_model(settings.model)
    missing = missing_credential(resolved)
    if missing:
        logger.error("Model '{}' needs {} to be set (see .env.example).", resolved, missing)
        return 2

    provider = LLMProvider.from_settings(settings)
    search = DDGSearchBackend(region=settings.region)
    agent = CompetitiveIntelAgent(provider, settings, search)

    try:
        report = agent.run(args.company, args.vertical)
    except Exception as exc:  # noqa: BLE001 - clean CLI exit
        logger.exception("Research failed: {}", exc)
        return 1

    # Diff against the previous run, then persist this one.
    store = IntelStore(settings.db_path)
    try:
        previous = store.latest(args.company, args.vertical)
        changes = diff_reports(previous, report)
        store.save(report)
    finally:
        store.close()

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    stem = f"{_slug(args.company)}_{_slug(args.vertical)}"
    json_path = out_dir / f"{stem}.brief.json"
    md_path = out_dir / f"{stem}.brief.md"
    json_path.write_text(render_json(report, changes), encoding="utf-8")
    markdown = render_markdown(report, changes)
    md_path.write_text(markdown, encoding="utf-8")

    logger.bind(agent=agent.name).success(
        "Done. {} competitor(s), {} threat(s), {} change(s) vs last run. Overall threat: {}.",
        len(report.competitors), len(report.threats), len(changes),
        report.overall_threat_level.label,
    )
    logger.info("Wrote {} and {}", json_path, md_path)

    if args.print_md:
        print("\n" + markdown)
    return 0


def main() -> None:
    sys.exit(run())


if __name__ == "__main__":
    main()
