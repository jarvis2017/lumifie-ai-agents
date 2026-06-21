"""Command-line entry point for the lead-research agent.

    lead-research https://acme.com --icp config/icp.example.json

Writes ``<host>.lead.json`` and ``<host>.lead.md``.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

from lumifie_core import LLMProvider, configure_logging, logger
from lumifie_core.provider import missing_credential, resolve_model

from lead_research import __version__
from lead_research.agent import LeadResearchAgent, _host
from lead_research.backends import DDGSearchBackend, JinaReader
from lead_research.config import LeadSettings
from lead_research.icp import load_icp
from lead_research.report import render_json, render_markdown


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="lead-research",
        description=(
            "Research a target company (enrich → ICP-score → draft outreach) and "
            "emit a JSON + Markdown lead brief."
        ),
    )
    parser.add_argument("url", help="Target company URL.")
    parser.add_argument("--icp", default=None, help="Path to an ICP JSON file (default: built-in).")
    parser.add_argument("-o", "--out-dir", default=".", help="Output directory.")
    parser.add_argument("--region", default=None, help="Search region (default: us-en).")
    parser.add_argument(
        "--model", default=None,
        help="Model alias/id: claude (default), gpt-4o, ollama/llama3.1 (or LITELLM_MODEL).",
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
    return re.sub(r"[^a-z0-9]+", "-", text.strip().lower()).strip("-") or "lead"


def run(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    settings = LeadSettings.from_env(
        model=args.model,
        reasoning_effort=args.reasoning_effort,
        log_level=args.log_level,
        icp_path=args.icp,
        region=args.region,
    )
    configure_logging(settings.log_level)

    resolved = resolve_model(settings.model)
    missing = missing_credential(resolved)
    if missing:
        logger.error("Model '{}' needs {} to be set (see .env.example).", resolved, missing)
        return 2

    try:
        icp = load_icp(settings.icp_path)
    except Exception as exc:  # noqa: BLE001
        logger.error("Could not load ICP from {}: {}", settings.icp_path, exc)
        return 1

    provider = LLMProvider.from_settings(settings)
    agent = LeadResearchAgent(
        provider,
        settings,
        icp,
        DDGSearchBackend(region=settings.region),
        JinaReader(base=settings.jina_base, max_chars=settings.max_page_chars),
    )

    try:
        report = agent.run(args.url)
    except Exception as exc:  # noqa: BLE001
        logger.exception("Lead research failed: {}", exc)
        return 1

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    stem = _slug(_host(args.url))
    (out_dir / f"{stem}.lead.json").write_text(render_json(report), encoding="utf-8")
    markdown = render_markdown(report)
    (out_dir / f"{stem}.lead.md").write_text(markdown, encoding="utf-8")

    logger.bind(agent=agent.name).success(
        "Done. {} — ICP fit {} ({}).",
        report.enrichment.company_name, report.icp_score.fit_score, report.icp_score.tier,
    )
    logger.info("Wrote {}/{}.lead.json and .lead.md", out_dir, stem)

    if args.print_md:
        print("\n" + markdown)
    return 0


def main() -> None:
    sys.exit(run())


if __name__ == "__main__":
    main()
