"""Offline rule-based provider so dry-run demos work with zero credentials.

Returns deterministic structured results for each sub-agent's forced tool, so the
full supervisor pipeline runs end to end without an API key or network.
"""

from __future__ import annotations

from typing import Any

from lumifie_core import CompletionResult, ToolCall

_USAGE = {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0}

_LEADS = {
    "leads": [
        {
            "company": "Acme Analytics",
            "domain": "acme-analytics.com",
            "contact_name": "Jane Doe",
            "contact_email": "jane@acme-analytics.com",
            "title": "VP Engineering",
            "source_url": "https://acme-analytics.com",
            "signals": ["Series B raise", "hiring engineers"],
            "icp_fit": 88,
            "tier": "A",
            "reasoning": "Mid-market B2B SaaS, VP Eng persona, scaling fast — strong ICP fit.",
        },
        {
            "company": "Globex Data",
            "domain": "globexdata.io",
            "contact_name": "Sam Lee",
            "contact_email": "sam@globexdata.io",
            "title": "Head of Product",
            "source_url": "https://globexdata.io",
            "signals": ["manual reporting workflows"],
            "icp_fit": 74,
            "tier": "B",
            "reasoning": "Right size and persona; pain around manual workflows.",
        },
        {
            "company": "Initech Cloud",
            "domain": "initech.cloud",
            "contact_name": None,
            "contact_email": "ops@initech.cloud",
            "title": None,
            "source_url": "https://initech.cloud",
            "signals": ["legacy tooling"],
            "icp_fit": 61,
            "tier": "C",
            "reasoning": "Plausible fit but unclear persona and budget.",
        },
    ]
}

_SEQUENCE = {
    "steps": [
        {
            "channel": "email",
            "day": 0,
            "subject": "A quick idea for your team",
            "body": "Hi {first} — saw your recent momentum. Teams like yours often hit a wall "
            "where manual workflows stop scaling with headcount; we automate exactly that, with "
            "fast time-to-value. Worth a 15-minute look?",
        },
        {
            "channel": "linkedin",
            "day": 2,
            "subject": None,
            "body": "Following up with a short note — happy to share a quick "
            "teardown relevant to your stack.",
        },
    ],
    "personalization_signals": ["recent growth", "manual workflows"],
}

_REPORT = {
    "recommended_next_actions": [
        "Prioritize the A-tier lead for a same-day personalized follow-up.",
        "Send the prepared rebuttal to the pricing objection and offer a pilot.",
        "Book the interested reply before momentum fades.",
    ],
    "summary": "Healthy top of funnel: strong A-tier lead identified, sequences drafted, and two "
    "replies triaged. One interested prospect is ready to book; one objection needs a rebuttal.",
}


def _classify_reply(text: str) -> dict[str, Any]:
    t = text.lower()
    if any(w in t for w in ("too expensive", "budget", "already use", "pricing")):
        return {
            "intent": "objection",
            "suggested_action": "Acknowledge cost, reframe on ROI, offer a pilot.",
        }
    if any(w in t for w in ("interested", "demo", "book", "call", "sounds great")):
        return {
            "intent": "interested",
            "suggested_action": "Send a booking link and confirm a time.",
        }
    if any(w in t for w in ("not the right person", "reach out to", "wrong person")):
        return {
            "intent": "wrong_person",
            "suggested_action": "Ask for the right contact and re-route.",
        }
    if "unsubscribe" in t:
        return {"intent": "unsubscribe", "suggested_action": "Suppress and stop outreach."}
    return {"intent": "not_now", "suggested_action": "Nurture and follow up next quarter."}


class StubProvider:
    supports_tools = True
    model = "stub:offline"

    def complete(self, messages: list[dict[str, Any]], **kwargs: Any) -> CompletionResult:
        name = (kwargs.get("tool_choice") or {}).get("function", {}).get("name", "")
        user_text = " ".join(m.get("content", "") for m in messages if m.get("role") == "user")
        if name == "scored_leads":
            args: dict[str, Any] = _LEADS
        elif name == "outreach_sequence":
            args = _SEQUENCE
        elif name == "reply_classification":
            args = _classify_reply(user_text)
        elif name == "pipeline_report":
            args = _REPORT
        else:
            args = {}
        return CompletionResult(
            text=None,
            tool_calls=[ToolCall(id="stub", name=name or "stub", arguments=args)],
            finish_reason="tool_calls",
            usage=_USAGE,
        )


__all__ = ["StubProvider"]
