"""Contract Intelligence Agent — production-grade AI contract analysis.

Lumifie Consulting. Ingests a PDF contract, extracts and analyzes key clauses,
flags risks, and produces a structured JSON report and a markdown summary.
"""

from contract_intelligence.models import (
    Clause,
    ClauseCategory,
    ContractReport,
    Risk,
    RiskLevel,
)

__all__ = [
    "Clause",
    "ClauseCategory",
    "ContractReport",
    "Risk",
    "RiskLevel",
    "__version__",
]

__version__ = "0.1.0"
