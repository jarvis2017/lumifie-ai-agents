"""Generate a realistic multi-page sample contract PDF for demos and tests.

    python scripts/make_sample_pdf.py [output.pdf]

Requires reportlab (a dev dependency):  uv pip install -e ".[dev]"
"""

from __future__ import annotations

import sys
from pathlib import Path

from reportlab.lib.pagesizes import LETTER
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer

# A deliberately imperfect Master Services Agreement: it contains several
# realistic, flaggable terms (uncapped IP assignment, broad indemnity, auto-
# renewal, unilateral termination, distant venue) so the agent has something to find.
SECTIONS: list[tuple[str, str]] = [
    (
        "Master Services Agreement",
        "This Master Services Agreement (the “Agreement”) is entered into as of "
        "March 1, 2026 (the “Effective Date”) by and between Northwind Analytics, "
        "Inc., a Delaware corporation (“Client”), and Vertex Software Labs, LLC "
        "(“Provider”). The parties agree as follows.",
    ),
    (
        "1. Services and Term",
        "1.1 Provider shall perform the services described in one or more Statements "
        "of Work (each, an “SOW”). 1.2 The initial term of this Agreement is "
        "twelve (12) months from the Effective Date and shall automatically renew for "
        "successive twelve (12) month periods unless either party provides written "
        "notice of non-renewal at least ninety (90) days prior to the end of the "
        "then-current term.",
    ),
    (
        "2. Fees and Payment",
        "2.1 Client shall pay the fees set forth in each SOW. 2.2 Provider shall "
        "invoice Client monthly in arrears. 2.3 All invoices are due and payable "
        "within fifteen (15) days of the invoice date. 2.4 Any amount not paid when "
        "due shall accrue interest at the rate of one and one-half percent (1.5%) per "
        "month, or the maximum rate permitted by law, whichever is lower. 2.5 Provider "
        "may suspend services if any undisputed invoice remains unpaid for more than "
        "ten (10) days after the due date. All fees are non-refundable.",
    ),
    (
        "3. Intellectual Property",
        "3.1 Except for Provider’s pre-existing materials, all work product, "
        "deliverables, inventions, and intellectual property conceived or developed by "
        "Provider in the course of performing the Services shall be the sole and "
        "exclusive property of Client, and Provider hereby irrevocably assigns to "
        "Client all right, title, and interest therein. 3.2 Provider retains ownership "
        "of its pre-existing tools and grants Client a non-exclusive license to use "
        "them solely as embedded in the deliverables.",
    ),
    (
        "4. Confidentiality",
        "4.1 Each party shall protect the other’s Confidential Information using at "
        "least the same degree of care it uses for its own, and no less than a "
        "reasonable degree of care. 4.2 Confidentiality obligations survive for three "
        "(3) years following termination of this Agreement.",
    ),
    (
        "5. Limitation of Liability and Indemnification",
        "5.1 EXCEPT FOR A PARTY’S INDEMNIFICATION OBLIGATIONS AND BREACHES OF "
        "CONFIDENTIALITY, IN NO EVENT SHALL EITHER PARTY BE LIABLE FOR INDIRECT, "
        "INCIDENTAL, OR CONSEQUENTIAL DAMAGES. 5.2 Notwithstanding the foregoing, "
        "Client’s indemnification obligations under Section 5.3 shall be unlimited "
        "and shall not be subject to any cap on liability. 5.3 Client shall indemnify, "
        "defend, and hold harmless Provider from any and all claims arising out of or "
        "relating to Client’s use of the deliverables.",
    ),
    (
        "6. Termination",
        "6.1 Provider may terminate this Agreement at any time, for any reason or no "
        "reason, upon thirty (30) days’ written notice to Client. 6.2 Client may "
        "terminate only for Provider’s material breach that remains uncured for "
        "sixty (60) days after written notice. 6.3 Upon termination, Client shall pay "
        "all fees accrued through the effective date of termination.",
    ),
    (
        "7. Governing Law and Dispute Resolution",
        "7.1 This Agreement shall be governed by the laws of the State of Nevada, "
        "without regard to its conflict-of-laws principles. 7.2 Any dispute arising "
        "under this Agreement shall be resolved exclusively by binding arbitration "
        "administered in Clark County, Nevada. 7.3 EACH PARTY WAIVES ANY RIGHT TO A "
        "TRIAL BY JURY AND TO PARTICIPATE IN A CLASS ACTION.",
    ),
]


def build_pdf(out_path: Path) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    doc = SimpleDocTemplate(
        str(out_path),
        pagesize=LETTER,
        topMargin=1 * inch,
        bottomMargin=1 * inch,
    )
    styles = getSampleStyleSheet()
    story = []
    for i, (heading, body) in enumerate(SECTIONS):
        style = styles["Title"] if i == 0 else styles["Heading2"]
        story.append(Paragraph(heading, style))
        story.append(Spacer(1, 0.15 * inch))
        story.append(Paragraph(body, styles["BodyText"]))
        story.append(Spacer(1, 0.3 * inch))
    doc.build(story)


def main() -> None:
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("examples/sample_contract.pdf")
    build_pdf(out)
    print(f"Wrote {out}")


if __name__ == "__main__":
    main()
