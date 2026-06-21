"""Produce the committed example digest in examples/.

Runs the REAL agent pipeline (planner → researcher → impact analyst → diff)
against deterministic offline fakes, twice: a baseline run and a follow-up run in
which one new regulatory item has appeared. The committed example is the second
run, so it genuinely exercises the "New This Week" diff via the production report
module. Run the CLI with credentials + live backends to reproduce against the web.

    python scripts/generate_example_output.py
"""

from __future__ import annotations

from pathlib import Path

from lumifie_core import CompletionResult, LLMProvider, ToolCall

from reg_monitor.agent import RegulatoryMonitorAgent
from reg_monitor.config import MonitorSettings
from reg_monitor.models import BusinessProfile, Source, SourceType
from reg_monitor.report import render_json, render_markdown
from reg_monitor.schemas import ANALYZE_TOOL, PLAN_TOOL
from reg_monitor.sources import FeedItem, SearchResult

PROFILE = BusinessProfile(
    industry="food service",
    location="California, USA",
    operational_keywords=["food safety", "labor law", "minimum wage", "tipped wages"],
    business_description=(
        "A small chain of fast-casual restaurants with three Bay Area locations and "
        "about 40 hourly staff."
    ),
)

SOURCES = [
    Source(
        type=SourceType.GOV,
        value="https://www.dir.ca.gov/dlse/",
        label="CA Division of Labor Standards Enforcement",
    ),
    Source(
        type=SourceType.RSS,
        value="https://www.dir.ca.gov/DIRNews/RSSNews.xml",
        label="CA Dept. of Industrial Relations — News",
    ),
]

_PLAN = {
    "search_queries": [
        "California fast food minimum wage update 2026",
        "California food safety regulation restaurants new rule",
        "California tipped wage labor law change",
    ],
    "source_focus": ["minimum wage", "food safety"],
    "rationale": (
        "Focus on California wage and food-safety obligations that hit a multi-site "
        "fast-casual restaurant employer most directly."
    ),
}

# Baseline finding present in both runs (so it is NOT new in run 2).
_WAGE_URL = "https://www.dir.ca.gov/news/2026/wage-order-update"
# New finding that appears only in run 2.
_SAFETY_URL = "https://www.cdph.ca.gov/news/2026/food-handler-rule"


def _search_run1(query: str, max_results: int = 5, after_date=None) -> list[SearchResult]:
    return [
        SearchResult(
            title="California raises fast-food minimum wage to $20.50",
            url=_WAGE_URL,
            snippet=(
                "The Fast Food Council approved a minimum wage increase to $20.50/hour for "
                "covered fast-food employees, effective next quarter."
            ),
            date="2026-06-16",
        )
    ]


def _search_run2(query: str, max_results: int = 5, after_date=None) -> list[SearchResult]:
    # Same wage item, plus a brand-new food-safety rule.
    base = _search_run1(query, max_results, after_date)
    base.append(
        SearchResult(
            title="New California food handler certification rule takes effect",
            url=_SAFETY_URL,
            snippet=(
                "CDPH finalized a rule requiring all food handlers to complete updated "
                "certification within 30 days of hire."
            ),
            date="2026-06-19",
        )
    )
    return base


class _Feed:
    def fetch(self, url: str) -> list[FeedItem]:
        return [
            FeedItem(
                title="DIR posts updated wage-theft enforcement guidance",
                url="https://www.dir.ca.gov/news/2026/wage-theft-guidance",
                summary="Updated guidance clarifies employer recordkeeping obligations.",
                published="2026-06-17",
            )
        ]


class _Search:
    def __init__(self, fn):
        self._fn = fn

    def search(self, query, max_results=5, after_date=None):
        return self._fn(query, max_results, after_date)


def _make_provider(impacts: list[dict]) -> LLMProvider:
    """A fake provider: returns the plan, then the given impact statements."""
    state = {"n": 0}

    def completion_fn(**kwargs):
        state["n"] += 1
        tools = kwargs.get("tools") or []
        names = {t["function"]["name"] for t in tools}
        usage = {"prompt_tokens": 900, "completion_tokens": 220, "total_tokens": 1120}
        if PLAN_TOOL in names:
            tc = ToolCall("c1", PLAN_TOOL, _PLAN)
        elif ANALYZE_TOOL in names:
            tc = ToolCall("c2", ANALYZE_TOOL, {"impacts": impacts})
        else:  # pragma: no cover - not exercised here
            return _as_raw(CompletionResult(text="{}", usage={}))
        return _as_raw(CompletionResult(text=None, tool_calls=[tc], usage={
            "input_tokens": usage["prompt_tokens"],
            "output_tokens": usage["completion_tokens"],
            "total_tokens": usage["total_tokens"],
        }))

    provider = LLMProvider("claude-opus-4-8", completion_fn=lambda **kw: completion_fn(**kw))
    provider.supports_tools = True
    return provider


def _as_raw(result: CompletionResult) -> dict:
    """Shape a CompletionResult back into the litellm-style dict the provider normalizes."""
    return {
        "choices": [
            {
                "message": {
                    "content": result.text,
                    "tool_calls": [
                        {
                            "id": tc.id,
                            "function": {"name": tc.name, "arguments": __import__("json").dumps(tc.arguments)},
                        }
                        for tc in result.tool_calls
                    ],
                },
                "finish_reason": "tool_calls" if result.tool_calls else "stop",
            }
        ],
        "usage": {
            "prompt_tokens": result.usage.get("input_tokens", 0),
            "completion_tokens": result.usage.get("output_tokens", 0),
            "total_tokens": result.usage.get("total_tokens", 0),
        },
        "model": "claude-opus-4-8",
    }


_WAGE_IMPACT = {
    "url": _WAGE_URL,
    "title": "California fast-food minimum wage rises to $20.50/hour",
    "plain_english": (
        "California's Fast Food Council raised the minimum wage for covered fast-food "
        "workers to $20.50/hour. As a Bay Area fast-casual operator with ~40 hourly "
        "staff, your payroll costs will rise next quarter and you must update pay rates "
        "and posted wage notices."
    ),
    "relevance": "high",
    "recommended_action": (
        "Recalculate labor budgets at $20.50/hour, update payroll before the effective "
        "date, and post the new wage notice at each location."
    ),
}
_SAFETY_IMPACT = {
    "url": _SAFETY_URL,
    "title": "New food-handler certification rule (30-day deadline)",
    "plain_english": (
        "CDPH now requires every food handler to complete updated certification within "
        "30 days of hire. With three locations and regular hourly turnover, you need a "
        "tracking process so new hires are certified on time."
    ),
    "relevance": "high",
    "recommended_action": (
        "Add certification to onboarding, track completion dates per employee, and "
        "verify all current staff hold a valid certificate."
    ),
}
_THEFT_IMPACT = {
    "url": "https://www.dir.ca.gov/news/2026/wage-theft-guidance",
    "title": "Updated wage-theft recordkeeping guidance",
    "plain_english": (
        "DIR clarified employer recordkeeping obligations around wages and hours. You "
        "should confirm your time-tracking records meet the clarified standard."
    ),
    "relevance": "medium",
    "recommended_action": "Audit time and payroll records against the updated guidance.",
}


def _run(search_fn, impacts, previous=None) -> object:
    settings = MonitorSettings(model="claude-opus-4-8", lookback_days=7)
    provider = _make_provider(impacts)
    agent = RegulatoryMonitorAgent(provider, settings, _Search(search_fn), _Feed())
    return agent.run(PROFILE, SOURCES, previous=previous)


def main() -> None:
    out_dir = Path("examples")
    out_dir.mkdir(parents=True, exist_ok=True)

    # Run 1 (baseline): wage item + feed item only.
    baseline = _run(_search_run1, [_WAGE_IMPACT, _THEFT_IMPACT])

    # Run 2 (current): the baseline items plus a new food-safety rule.
    current = _run(_search_run2, [_WAGE_IMPACT, _SAFETY_IMPACT, _THEFT_IMPACT], previous=baseline)

    stem = PROFILE.slug()
    (out_dir / f"{stem}.digest.json").write_text(render_json(current), encoding="utf-8")
    (out_dir / f"{stem}.digest.md").write_text(render_markdown(current), encoding="utf-8")
    print(
        f"Wrote example digest to examples/ — {len(current.impacts)} watchlist item(s), "
        f"{len(current.new_impacts)} new this week."
    )


if __name__ == "__main__":
    main()
