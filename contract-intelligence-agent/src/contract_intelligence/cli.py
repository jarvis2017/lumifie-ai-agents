"""Command-line entry point for the contract-intelligence agent.

    contract-intelligence path/to/contract.pdf --out-dir ./reports --model claude

Produces ``<name>.report.json`` and ``<name>.report.md`` in the output directory.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from lumifie_core import LLMProvider, configure_logging, logger
from lumifie_core.provider import missing_credential, resolve_model

from contract_intelligence import __version__
from contract_intelligence.agent import ContractIntelligenceAgent
from contract_intelligence.config import ContractSettings
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
        "-o", "--out-dir", default=".",
        help="Directory to write the report files into (default: current dir).",
    )
    parser.add_argument(
        "--model", default=None,
        help="Model alias or id: claude (default), gpt-4o, ollama/llama3.1, ... "
        "Falls back to the LITELLM_MODEL env var.",
    )
    parser.add_argument(
        "--reasoning-effort", default=None, choices=["low", "medium", "high"],
        help="Optional cross-provider reasoning effort (only sent if supported).",
    )
    parser.add_argument(
        "--print", dest="print_md", action="store_true",
        help="Also print the markdown summary to stdout.",
    )
    parser.add_argument("--log-level", default=None, help="DEBUG, INFO, WARNING, ERROR.")
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    return parser


def run(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    settings = ContractSettings.from_env(
        model=args.model, reasoning_effort=args.reasoning_effort, log_level=args.log_level
    )
    configure_logging(settings.log_level)

    resolved = resolve_model(settings.model)
    missing = missing_credential(resolved)
    if missing:
        logger.error(
            "Model '{}' needs {} to be set. Export it (or copy .env.example to .env).",
            resolved, missing,
        )
        return 2

    try:
        document = load_contract(args.pdf, max_chunk_chars=settings.max_chunk_chars)
    except PDFLoadError as exc:
        logger.error("Failed to load PDF: {}", exc)
        return 1

    provider = LLMProvider.from_settings(settings)
    agent = ContractIntelligenceAgent(provider, settings)

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

    logger.bind(agent=agent.name).success(
        "Done. {} clause(s), {} risk(s), overall risk: {}.",
        len(report.clauses), len(report.risks), report.overall_risk_level.label,
    )
    logger.info("Wrote {} and {}", json_path, md_path)

    if args.print_md:
        print("\n" + markdown)
    return 0


def main() -> None:
    sys.exit(run())


if __name__ == "__main__":
    main()
