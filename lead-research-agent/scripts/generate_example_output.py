"""Produce the committed example lead brief in examples/.

Builds a representative LeadReport and renders it through the real report module.
Run the CLI with credentials to reproduce against live search + a real URL.

    python scripts/generate_example_output.py
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from lead_research.models import (
    Enrichment,
    Executive,
    ICPScore,
    LeadReport,
    Outreach,
)
from lead_research.report import render_json, render_markdown


def build_report() -> LeadReport:
    return LeadReport(
        company_url="https://acme-analytics.com",
        generated_at=datetime(2026, 6, 21, 9, 0, tzinfo=UTC),
        model="claude-opus-4-8",
        icp_name="B2B SaaS — mid-market",
        enrichment=Enrichment(
            company_name="Acme Analytics",
            industry="B2B SaaS — product analytics",
            value_proposition=(
                "Warehouse-native product analytics that lets mid-market teams answer "
                "product questions directly against their data warehouse, without "
                "duplicating data into a separate analytics silo."
            ),
            recent_news=[
                "Raised a $20M Series B led by Acme Ventures (May 2026)",
                "Launched an AI-assisted insights feature",
                "Hired a new VP of Engineering from a larger analytics incumbent",
            ],
            key_executives=[
                Executive(name="Jane Doe", title="CEO & Co-founder"),
                Executive(name="Sam Lee", title="VP Engineering"),
            ],
            summary=(
                "Recently funded mid-market analytics vendor differentiating on a "
                "warehouse-native architecture; actively investing in engineering and AI."
            ),
        ),
        icp_score=ICPScore(
            fit_score=84,
            tier="Strong",
            reasoning=(
                "Acme is B2B SaaS in the developer/data-tooling space at mid-market size "
                "with a VP Engineering persona in place — a direct match to the ICP's "
                "target industries, sizes, and personas. The fresh Series B signals budget "
                "and a mandate to scale tooling, aligning with the 'tooling that scales with "
                "headcount' pain point. Minor gap: public pricing is unclear."
            ),
            matched_criteria=[
                "B2B SaaS / developer tools",
                "mid-market (50-200 employees)",
                "VP Engineering persona present",
                "recent funding → budget",
            ],
            gaps=["pricing not publicly listed"],
            disqualified=False,
        ),
        outreach=Outreach(
            email_subject="Congrats on the Series B — a thought on scaling Acme's tooling",
            email_body=(
                "Hi Jane,\n\nCongrats on the $20M Series B — and on bringing Sam in to lead "
                "engineering. As Acme scales headcount, the repetitive, manual workflows that "
                "were fine at 50 people tend to quietly become a tax at 150.\n\nWe help teams "
                "like yours automate exactly that, with fast time-to-value and integrations "
                "into the stack you already run. Worth a 20-minute look?\n\nBest,\n[Your name]"
            ),
            linkedin_message=(
                "Hi Jane — congrats on the raise and the warehouse-native launch. We help "
                "scaling SaaS teams automate the manual workflows that creep in with headcount. "
                "Would love to connect."
            ),
            personalization_signals=[
                "$20M Series B (May 2026)",
                "new VP Engineering hire",
                "warehouse-native positioning",
            ],
        ),
        sources=[
            "https://acme-analytics.com",
            "https://news.example.com/acme-series-b",
            "https://acme-analytics.com/about",
        ],
        token_usage={"input_tokens": 9120, "output_tokens": 1340},
    )


def main() -> None:
    out_dir = Path("examples")
    out_dir.mkdir(parents=True, exist_ok=True)
    report = build_report()
    (out_dir / "acme-analytics.lead.json").write_text(render_json(report), encoding="utf-8")
    (out_dir / "acme-analytics.lead.md").write_text(render_markdown(report), encoding="utf-8")
    print("Wrote examples/acme-analytics.lead.json and .md")


if __name__ == "__main__":
    main()
