"""Command-line entry point for the contract-intelligence agent.

    contract-intelligence path/to/contract.pdf --out-dir ./reports

Produces ``<name>.report.json`` and ``<name>.report.md`` in the output directory.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from loguru import logger

from contract_intelligence import __version__
from contract_intelligence.agent import ContractIntelligenceAgent
from contract_intelligence.config import Settings
from contract_intelligence.llm_client import AnthropicLLMClient
from contract_intelligence.logging_config import configure_logging
from contract_intelligence.pdf_loader import PDFLoadError, load_contract
from contract_intelligence.report import render_json, render_markdown


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="contract-intelligence",
        description=(
            "Analyze a PDF contract: extract key clauses, flag risks, and emit a "
            "structured JSON report plus a markdown summary."
        ),
    )
    parser.add_argument("pdf", help="Path to the contract PDF.")
    parser.add_argument(
        "-o",
        "--out-dir",
        default=".",
        help="Directory to write the report files into (default: current dir).",
    )
    parser.add_argument(
        "--model",
        default=None,
        help="Override the Claude model id (default: from env or claude-opus-4-8).",
    )
    parser.add_argument(
        "--effort",
        choices=["low", "medium", "high", "max"],
        default=None,
        help="Reasoning effort (default: high).",
    )
    parser.add_argument(
        "--print",
        dest="print_md",
        action="store_true",
        help="Also print the markdown summary to stdout.",
    )
    parser.add_argument(
        "--log-level",
        default=None,
        help="Log level: DEBUG, INFO, WARNING, ERROR (default: INFO).",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    return parser


def run(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    settings = Settings.from_env()
    if args.model:
        settings.model = args.model
    if args.effort:
        settings.effort = args.effort
    if args.log_level:
        settings.log_level = args.log_level

    configure_logging(settings.log_level)

    if not settings.api_key:
        logger.error(
            "ANTHROPIC_API_KEY is not set. Export it (or copy .env.example to "
            ".env and fill it in) before running a live analysis."
        )
        return 2

    try:
        document = load_contract(args.pdf, max_chunk_chars=settings.max_chunk_chars)
    except PDFLoadError as exc:
        logger.error("Failed to load PDF: {}", exc)
        return 1

    client = AnthropicLLMClient(api_key=settings.api_key, max_retries=settings.max_retries)
    agent = ContractIntelligenceAgent(client, settings)

    try:
        report = agent.analyze(document)
    except Exception as exc:  # noqa: BLE001 - top-level guard for a clean CLI exit
        logger.exception("Analysis failed: {}", exc)
        return 1

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    stem = Path(document.name).stem
    json_path = out_dir / f"{stem}.report.json"
    md_path = out_dir / f"{stem}.report.md"

    json_path.write_text(render_json(report), encoding="utf-8")
    markdown = render_markdown(report)
    md_path.write_text(markdown, encoding="utf-8")

    logger.success(
        "Done. {} clause(s), {} risk(s), overall risk: {}.",
        len(report.clauses),
        len(report.risks),
        report.overall_risk_level.label,
    )
    logger.info("Wrote {} and {}", json_path, md_path)

    if args.print_md:
        print("\n" + markdown)

    return 0


def main() -> None:
    sys.exit(run())


if __name__ == "__main__":
    main()
