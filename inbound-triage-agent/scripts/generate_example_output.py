"""Produce the committed example triage output in examples/.

Runs the real pipeline over the bundled mock payload using the offline stub
provider (no key/network), so the example reflects actual agent behavior.

    python scripts/generate_example_output.py
"""

from __future__ import annotations

import json
from pathlib import Path

from inbound_triage.agent import InboundTriageAgent
from inbound_triage.config import TriageSettings
from inbound_triage.knowledge import RebuttalKnowledgeBase
from inbound_triage.models import InboundMessage
from inbound_triage.stub import StubProvider

_ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    messages = [
        InboundMessage.model_validate(m)
        for m in json.loads((_ROOT / "data" / "mock_email.json").read_text())
    ]
    agent = InboundTriageAgent(StubProvider(), TriageSettings(), RebuttalKnowledgeBase())
    results = [agent.triage(m) for m in messages]

    out_dir = _ROOT / "examples"
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "example_triage.json").write_text(
        json.dumps([r.model_dump(mode="json") for r in results], indent=2), encoding="utf-8"
    )

    lines = ["# Inbound Triage — example run", "",
             "_Five mock messages, one per intent (offline stub provider)._", ""]
    for r in results:
        lines.append(f"## {r.message_id} → {r.intent.value} → `{r.action.value}`")
        lines.append("")
        lines.append(f"_{r.reasoning}_")
        lines.append("")
        if r.booking:
            lines.append(f"- **Booking link:** {r.booking.link}")
            lines.append(f"- **Reply:** {r.booking.reply}")
        if r.rebuttal:
            lines.append(f"- **Rebuttal** (KB sources: {', '.join(r.rebuttal.sources)}):")
            lines.append(f"  > {r.rebuttal.body}")
        if r.contact:
            c = r.contact
            lines.append(f"- **Referred contact:** {c.referred_name or '—'} "
                         f"| emails: {', '.join(c.emails) or '—'} | phones: {', '.join(c.phones) or '—'}")
        lines.append("")
    (out_dir / "example_triage.md").write_text("\n".join(lines), encoding="utf-8")
    print(f"Wrote examples/example_triage.json and .md ({len(results)} results)")


if __name__ == "__main__":
    main()
