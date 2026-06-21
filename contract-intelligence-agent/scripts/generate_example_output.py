"""Produce the committed example reports in examples/.

This builds a `ContractReport` whose findings reflect the bundled
`sample_contract.pdf` (a vendor-favorable MSA) and renders it through the real
`report` module — so the example JSON/Markdown are genuine artifacts of the
production rendering code. The findings here are representative of what the agent
extracts on a live run; run the CLI with an ANTHROPIC_API_KEY to reproduce
against the live model.

    python scripts/generate_example_output.py
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from contract_intelligence.models import (
    Clause,
    ClauseCategory,
    ContractReport,
    Risk,
    RiskLevel,
    TokenUsage,
)
from contract_intelligence.report import render_json, render_markdown

C = ClauseCategory
R = RiskLevel


def build_report() -> ContractReport:
    clauses = [
        Clause(category=C.PAYMENT_TERMS, page=1, title="Net-15 payment, non-refundable",
                summary="Provider invoices monthly in arrears; invoices are due within 15 days, and all fees are non-refundable.",
                verbatim_excerpt="All invoices are due and payable within fifteen (15) days of the invoice date. ... All fees are non-refundable."),
        Clause(category=C.PAYMENT_TERMS, page=1, title="Late interest and suspension",
                summary="Overdue amounts accrue 1.5%/month and Provider may suspend services after 10 days past due.",
                verbatim_excerpt="any amount not paid when due shall accrue interest at the rate of one and one-half percent (1.5%) per month ... Provider may suspend services if any undisputed invoice remains unpaid for more than ten (10) days"),
        Clause(category=C.TERMINATION, page=2, title="Auto-renewal with 90-day notice",
                summary="12-month term auto-renews for successive 12-month periods unless either party gives 90 days' written notice.",
                verbatim_excerpt="shall automatically renew for successive twelve (12) month periods unless either party provides written notice of non-renewal at least ninety (90) days prior"),
        Clause(category=C.TERMINATION, page=2, title="Unilateral termination for convenience",
                summary="Provider may terminate at any time on 30 days' notice; Client may terminate only for uncured material breach after 60 days.",
                verbatim_excerpt="Provider may terminate this Agreement at any time, for any reason or no reason, upon thirty (30) days' written notice ... Client may terminate only for Provider's material breach that remains uncured for sixty (60) days"),
        Clause(category=C.IP_OWNERSHIP, page=2, title="Assignment of work product to Client",
                summary="All work product and IP developed under the Agreement is assigned to Client; Provider keeps pre-existing tools and grants a license.",
                verbatim_excerpt="Provider hereby irrevocably assigns to Client all right, title, and interest therein. ... grants Client a non-exclusive license to use them solely as embedded in the deliverables."),
        Clause(category=C.LIABILITY, page=2, title="Consequential-damages waiver with carve-outs",
                summary="Mutual waiver of indirect/consequential damages, except indemnity and confidentiality breaches.",
                verbatim_excerpt="IN NO EVENT SHALL EITHER PARTY BE LIABLE FOR INDIRECT, INCIDENTAL, OR CONSEQUENTIAL DAMAGES"),
        Clause(category=C.LIABILITY, page=2, title="Uncapped Client indemnification",
                summary="Client's indemnification is explicitly unlimited and not subject to any liability cap.",
                verbatim_excerpt="Client's indemnification obligations under Section 5.3 shall be unlimited and shall not be subject to any cap on liability."),
        Clause(category=C.DISPUTE_RESOLUTION, page=3, title="Nevada law, Clark County arbitration, jury waiver",
                summary="Governed by Nevada law; disputes resolved by binding arbitration in Clark County; jury trial and class actions waived.",
                verbatim_excerpt="resolved exclusively by binding arbitration administered in Clark County, Nevada. ... EACH PARTY WAIVES ANY RIGHT TO A TRIAL BY JURY AND TO PARTICIPATE IN A CLASS ACTION."),
    ]

    risks = [
        Risk(severity=R.CRITICAL, category=C.LIABILITY, title="Uncapped client indemnification",
             description="Section 5.2 makes the client's indemnity explicitly unlimited and carves it out of the mutual limitation-of-liability cap, exposing the client to potentially unbounded liability for third-party claims.",
             recommendation="Cap total indemnity at fees paid in the trailing 12 months and make the carve-out mutual; require Provider indemnity for IP infringement.",
             related_excerpt="shall be unlimited and shall not be subject to any cap on liability"),
        Risk(severity=R.HIGH, category=C.TERMINATION, title="Asymmetric termination rights",
             description="Provider can terminate for convenience on 30 days' notice while the client can only terminate for uncured material breach, leaving the client without an exit and exposed to mid-project abandonment.",
             recommendation="Add a reciprocal termination-for-convenience right for the client, and a transition-assistance/wind-down obligation on Provider.",
             related_excerpt="Provider may terminate this Agreement at any time, for any reason or no reason"),
        Risk(severity=R.HIGH, category=C.DISPUTE_RESOLUTION, title="Distant mandatory venue and jury/class waiver",
             description="Mandatory arbitration in Clark County, Nevada under Nevada law, plus a jury-trial and class-action waiver, raises the cost and friction of enforcing the client's rights if the client is not Nevada-based.",
             recommendation="Negotiate a neutral or client-favorable venue, or at minimum allow remote arbitration; reconsider the class-action waiver.",
             related_excerpt="binding arbitration administered in Clark County, Nevada"),
        Risk(severity=R.MEDIUM, category=C.TERMINATION, title="Auto-renewal with long notice window",
             description="The agreement auto-renews for 12-month terms unless 90 days' written notice is given, which can trap the client into an unwanted renewal if the deadline is missed.",
             recommendation="Add a calendar reminder for the notice deadline, shorten the renewal term to month-to-month after the initial term, or reduce the notice period to 30 days.",
             related_excerpt="automatically renew for successive twelve (12) month periods"),
        Risk(severity=R.MEDIUM, category=C.PAYMENT_TERMS, title="Short payment window with non-refundable fees",
             description="Net-15 payment combined with non-refundable fees and a 10-day suspension trigger gives the client little tolerance and no recourse for prepaid amounts.",
             recommendation="Negotiate net-30, a cure period before suspension, and pro-rata refunds for terminated-but-prepaid services.",
             related_excerpt="due and payable within fifteen (15) days"),
    ]

    return ContractReport(
        contract_name="sample_contract.pdf",
        analyzed_at=datetime(2026, 6, 20, 18, 0, tzinfo=UTC),
        page_count=3,
        model="claude-opus-4-8",
        overall_risk_level=R.HIGH,
        executive_summary=(
            "This Master Services Agreement is materially vendor-favorable. The client "
            "bears unlimited, uncapped indemnification while the provider may terminate "
            "for convenience on 30 days' notice; broad IP assignment, 12-month auto-renewal, "
            "and a jury-trial/class-action waiver in a distant arbitration venue compound the "
            "exposure. Recommend negotiating a liability cap, mutual termination rights, and a "
            "more neutral venue before signing."
        ),
        clauses=clauses,
        risks=risks,
        token_usage=TokenUsage(input_tokens=18432, output_tokens=2987, cache_read_input_tokens=12010),
    )


def main() -> None:
    out_dir = Path("examples")
    out_dir.mkdir(parents=True, exist_ok=True)
    report = build_report()
    (out_dir / "sample_contract.report.json").write_text(render_json(report), encoding="utf-8")
    (out_dir / "sample_contract.report.md").write_text(render_markdown(report), encoding="utf-8")
    print("Wrote examples/sample_contract.report.json and .md")


if __name__ == "__main__":
    main()
