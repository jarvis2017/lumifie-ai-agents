"""Produce the committed example brief in examples/.

Builds a representative "previous" and "current" run for a fictional company,
computes the run-over-run diff, and renders both files through the real report
module — so the example is a genuine artifact of the production code, including
the change log. Run the CLI with credentials to reproduce against live search.

    python scripts/generate_example_output.py
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from competitive_intel.diff import diff_reports
from competitive_intel.models import Competitor, IntelReport, Threat, ThreatLevel
from competitive_intel.report import render_json, render_markdown

T = ThreatLevel


def _previous() -> IntelReport:
    return IntelReport(
        company="Northwind Analytics",
        vertical="product analytics SaaS",
        generated_at=datetime(2026, 5, 20, 7, 0, tzinfo=UTC),
        model="claude-opus-4-8",
        overall_threat_level=T.MEDIUM,
        market_summary="Crowded mid-market analytics space; consolidation underway.",
        executive_summary="Three incumbents dominate; Northwind competes on price and ease of use.",
        competitors=[
            Competitor(name="Amplitude", positioning="Enterprise product analytics leader",
                       pricing="Usage-based; Growth tier from ~$49k/yr",
                       strengths=["brand", "depth"], weaknesses=["price", "complexity"]),
            Competitor(name="Mixpanel", positioning="Self-serve product analytics",
                       pricing="Free tier; Growth ~$28/mo+",
                       strengths=["self-serve", "pricing"], weaknesses=["enterprise gaps"]),
            Competitor(name="Heap", positioning="Autocapture analytics",
                       pricing="Quote-based", strengths=["autocapture"], weaknesses=["opaque pricing"]),
        ],
        threats=[
            Threat(severity=T.MEDIUM, competitor="Mixpanel",
                   description="Mixpanel's free tier erodes Northwind's price advantage at the low end.",
                   recommendation="Differentiate on onboarding speed and support SLAs."),
        ],
        sources=["https://amplitude.com/pricing", "https://mixpanel.com/pricing"],
    )


def _current() -> IntelReport:
    return IntelReport(
        company="Northwind Analytics",
        vertical="product analytics SaaS",
        generated_at=datetime(2026, 6, 20, 7, 0, tzinfo=UTC),
        model="claude-opus-4-8",
        overall_threat_level=T.HIGH,
        market_summary=(
            "The product-analytics market is consolidating and shifting toward warehouse-native, "
            "AI-assisted analytics. Incumbents are bundling experimentation and session replay, "
            "raising the feature bar for mid-market challengers like Northwind."
        ),
        executive_summary=(
            "Competitive pressure has risen since the last run. PostHog has emerged as a fast-growing, "
            "open-source, all-in-one challenger, and Mixpanel has moved upmarket with enterprise pricing. "
            "Northwind's price advantage is narrowing; differentiation should pivot to warehouse-native "
            "integration and white-glove onboarding."
        ),
        competitors=[
            Competitor(name="Amplitude", positioning="Enterprise product analytics leader",
                       pricing="Usage-based; Growth tier from ~$49k/yr",
                       strengths=["brand", "depth", "experimentation suite"],
                       weaknesses=["price", "complexity"],
                       source_url="https://amplitude.com/pricing"),
            Competitor(name="Mixpanel", positioning="Product analytics moving upmarket",
                       pricing="Free tier; Enterprise from ~$60k/yr (was ~$28/mo self-serve focus)",
                       strengths=["self-serve", "brand"], weaknesses=["pricing creep"],
                       source_url="https://mixpanel.com/pricing"),
            Competitor(name="PostHog", positioning="Open-source all-in-one product OS",
                       pricing="Generous free tier; usage-based paid",
                       strengths=["open-source", "all-in-one", "developer love"],
                       weaknesses=["enterprise maturity"],
                       source_url="https://posthog.com/pricing"),
        ],
        threats=[
            Threat(severity=T.HIGH, competitor="PostHog",
                   description=(
                       "PostHog's open-source, all-in-one platform (analytics + session replay + "
                       "feature flags + experiments) at an aggressive free tier directly threatens "
                       "Northwind's value proposition with developer-led teams."),
                   recommendation=(
                       "Lead with warehouse-native integration and managed-service reliability; "
                       "publish a migration guide and TCO comparison vs. self-hosting PostHog.")),
            Threat(severity=T.MEDIUM, competitor="Mixpanel",
                   description="Mixpanel's move upmarket vacates the low end but validates higher pricing, pressuring Northwind's positioning.",
                   recommendation="Capture displaced self-serve Mixpanel users with a focused migration offer."),
        ],
        sources=[
            "https://amplitude.com/pricing",
            "https://mixpanel.com/pricing",
            "https://posthog.com/pricing",
        ],
        token_usage={"input_tokens": 41280, "output_tokens": 5120},
    )


def main() -> None:
    out_dir = Path("examples")
    out_dir.mkdir(parents=True, exist_ok=True)
    current = _current()
    changes = diff_reports(_previous(), current)
    (out_dir / "northwind-analytics_product-analytics-saas.brief.json").write_text(
        render_json(current, changes), encoding="utf-8"
    )
    (out_dir / "northwind-analytics_product-analytics-saas.brief.md").write_text(
        render_markdown(current, changes), encoding="utf-8"
    )
    print(f"Wrote example brief with {len(changes)} change(s) to examples/")


if __name__ == "__main__":
    main()
