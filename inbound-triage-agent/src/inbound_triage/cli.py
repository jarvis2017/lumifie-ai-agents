"""CLI for the inbound-triage agent: run on a mock payload or serve the webhook."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from lumifie_core import configure_logging, logger

from inbound_triage import __version__
from inbound_triage.config import TriageSettings
from inbound_triage.factory import build_agent
from inbound_triage.models import InboundMessage

# data/ lives at the agent root (src/inbound_triage/cli.py -> parents[2]).
_ROOT = Path(__file__).resolve().parents[2]
_DEFAULT_MOCK = _ROOT / "data" / "mock_email.json"


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="inbound-triage",
        description="Classify and route inbound messages. Defaults to a mock-email demo.",
    )
    p.add_argument(
        "--mock-email", action="store_true", help="Run the bundled mock payload (default)."
    )
    p.add_argument("--mock-file", default=str(_DEFAULT_MOCK), help="Path to a mock payload JSON.")
    p.add_argument("--serve", action="store_true", help="Run the FastAPI webhook server instead.")
    p.add_argument("--host", default="127.0.0.1")
    p.add_argument("--port", type=int, default=8000)
    p.add_argument("--model", default=None, help="Model alias/id (or LITELLM_MODEL).")
    p.add_argument("--offline", action="store_true", help="Force the offline stub provider.")
    p.add_argument("--log-level", default=None)
    p.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    return p


def _load_messages(path: str) -> list[InboundMessage]:
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    items = raw if isinstance(raw, list) else [raw]
    return [InboundMessage.model_validate(x) for x in items]


def run(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    settings = TriageSettings.from_env(model=args.model, log_level=args.log_level)
    configure_logging(settings.log_level)

    if args.serve:
        try:
            import uvicorn  # noqa: PLC0415
        except ImportError:
            logger.error("uvicorn is required to serve: uv pip install uvicorn")
            return 2
        from inbound_triage.api import create_app  # noqa: PLC0415

        agent = build_agent(settings, force_stub=args.offline)
        logger.info(
            "Serving triage webhook on http://{}:{} (model: {})",
            args.host, args.port, agent.provider.model,
        )
        uvicorn.run(create_app(agent), host=args.host, port=args.port)
        return 0

    # Default: mock-email demo.
    try:
        messages = _load_messages(args.mock_file)
    except Exception as exc:  # noqa: BLE001
        logger.error("Could not load mock payload {}: {}", args.mock_file, exc)
        return 1

    agent = build_agent(settings, force_stub=args.offline)
    logger.info("Triaging {} mock message(s) with model '{}'.", len(messages), agent.provider.model)
    for msg in messages:
        result = agent.triage(msg)
        _print_result(result)
    return 0


def _print_result(result) -> None:
    print("\n" + "=" * 70)
    print(f"message: {result.message_id}")
    print(f"intent : {result.intent.value}  (confidence {result.confidence:.2f})")
    print(f"action : {result.action.value}")
    if result.booking:
        print(f"booking: {result.booking.link}")
        print(f"  reply: {result.booking.reply}")
    if result.rebuttal:
        print(f"rebuttal (sources={result.rebuttal.sources}):")
        print(f"  {result.rebuttal.body}")
    if result.contact:
        c = result.contact
        print(f"contact: name={c.referred_name} emails={c.emails} phones={c.phones}")


def main() -> None:
    sys.exit(run())


if __name__ == "__main__":
    main()
