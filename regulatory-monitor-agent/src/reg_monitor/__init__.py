"""Regulatory Monitor Agent — plain-English regulatory change monitoring.

Lumifie Consulting. A three-stage pipeline (planner → researcher → impact
analyst) that monitors regulatory sources for a business, translates updates into
plain-English business impact, diffs against prior runs (SQLite) to surface
what's new, and emits a weekly digest in Markdown and JSON. Built on lumifie_core.
"""

from reg_monitor.models import (
    BusinessProfile,
    Digest,
    Finding,
    ImpactStatement,
    MonitoringConfig,
    MonitoringPlan,
    Relevance,
    Source,
    SourceType,
)

__version__ = "0.1.0"

__all__ = [
    "BusinessProfile",
    "Digest",
    "Finding",
    "ImpactStatement",
    "MonitoringConfig",
    "MonitoringPlan",
    "Relevance",
    "Source",
    "SourceType",
    "__version__",
]
