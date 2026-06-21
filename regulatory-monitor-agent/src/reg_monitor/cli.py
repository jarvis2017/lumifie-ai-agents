"""Command-line entry point for the regulatory-monitor agent.

    reg-monitor --profile config/profile.example.json

Produces ``<industry-location>.digest.json`` and ``.digest.md`` and records the
run in SQLite so the next run can surface what changed (new this week).
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from lumifie_core import LLMProvider, configure_logging, logger
from lumifie_core.provider import missing_credential, resolve_model

from reg_monitor import __version__
from reg_monitor.agent import RegulatoryMonitorAgent
from reg_monitor.config import MonitorSettings
from reg_monitor.loader import load_config
from reg_monitor.report import render_json, render_markdown
from reg_monitor.sources import DDGSearchBackend, RSSFeedBackend
from reg_monitor.store import MonitorStore


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="reg-monitor",
        description=(
            "Monitor regulatory sources for a business, translate updates into "
            "plain-English impact, diff against prior runs, and emit a weekly digest."
        ),
    )
    parser.add_argument(
        "-p", "--profile", required=True,
        help="Path to the profile + sources JSON (see config/profile.example.json).",
    )
    parser.add_argument("-o", "--out-dir", default=".", help="Output directory.")
    parser.add_argument(
        "--db", default=None, help="SQLite path (default: RM_DB_PATH or ./reg_monitor.db)."
    )
    parser.add_argument(
        "--lookback-days", type=int, default=None,
        help="How many days back to constrain searches (default: 7).",
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
    parser.add_argument("--print", dest="print_md", action="store_true", help="Print the digest.")
    parser.add_argument("--log-level", default=None, help="DEBUG, INFO, WARNING, ERROR.")
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    return parser


def run(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    settings = MonitorSettings.from_env(
        model=args.model,
        reasoning_effort=args.reasoning_effort,
        log_level=args.log_level,
        db_path=args.db,
        region=args.region,
        lookback_days=args.lookback_days,
    )
    configure_logging(settings.log_level)

    try:
        config = load_config(args.profile)
    except (FileNotFoundError, ValueError) as exc:
        logger.error("{}", exc)
        return 2

    resolved = resolve_model(settings.model)
    missing = missing_credential(resolved)
    if missing:
        logger.error("Model '{}' needs {} to be set (see .env.example).", resolved, missing)
        return 2

    provider = LLMProvider.from_settings(settings)
    search = DDGSearchBackend(region=settings.region)
    feeds = RSSFeedBackend()
    agent = RegulatoryMonitorAgent(provider, settings, search, feeds)

    # Fetch the previous run for diffing, then run, then persist this run.
    store = MonitorStore(settings.db_path)
    try:
        previous = store.latest(config.profile)
        try:
            digest = agent.run(config.profile, config.sources, previous=previous)
        except Exception as exc:  # noqa: BLE001 - clean CLI exit
            logger.exception("Monitoring run failed: {}", exc)
            return 1
        store.save(digest)
    finally:
        store.close()

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    stem = config.profile.slug()
    json_path = out_dir / f"{stem}.digest.json"
    md_path = out_dir / f"{stem}.digest.md"
    json_path.write_text(render_json(digest), encoding="utf-8")
    markdown = render_markdown(digest)
    md_path.write_text(markdown, encoding="utf-8")

    logger.bind(agent=agent.name).success(
        "Done. {} item(s) on watchlist, {} new this week ({}).",
        len(digest.impacts),
        len(digest.new_impacts),
        "baseline" if digest.is_baseline else "vs last run",
    )
    logger.info("Wrote {} and {}", json_path, md_path)

    if args.print_md:
        print("\n" + markdown)
    return 0


def main() -> None:
    sys.exit(run())


if __name__ == "__main__":
    main()
