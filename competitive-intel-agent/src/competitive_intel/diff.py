"""Compute run-over-run changes between two intel reports."""

from __future__ import annotations

from competitive_intel.models import Change, ChangeKind, Competitor, IntelReport


def _by_name(report: IntelReport) -> dict[str, Competitor]:
    return {c.name.strip().lower(): c for c in report.competitors}


def diff_reports(previous: IntelReport | None, current: IntelReport) -> list[Change]:
    """Return the list of changes from ``previous`` to ``current``.

    If there is no previous run, returns an empty list (nothing to compare).
    """
    if previous is None:
        return []

    changes: list[Change] = []
    prev = _by_name(previous)
    curr = _by_name(current)

    # New and dropped competitors.
    for key in sorted(curr.keys() - prev.keys()):
        c = curr[key]
        changes.append(
            Change(
                kind=ChangeKind.NEW_COMPETITOR,
                competitor=c.name,
                summary=f"New competitor identified: {c.name}.",
                after=c.positioning,
            )
        )
    for key in sorted(prev.keys() - curr.keys()):
        c = prev[key]
        changes.append(
            Change(
                kind=ChangeKind.DROPPED_COMPETITOR,
                competitor=c.name,
                summary=f"{c.name} no longer appears in the landscape.",
                before=c.positioning,
            )
        )

    # Pricing and positioning changes for competitors present in both runs.
    for key in sorted(curr.keys() & prev.keys()):
        before, after = prev[key], curr[key]
        if _norm(before.pricing) != _norm(after.pricing):
            changes.append(
                Change(
                    kind=ChangeKind.PRICING_CHANGE,
                    competitor=after.name,
                    summary=f"{after.name} pricing changed.",
                    before=before.pricing,
                    after=after.pricing,
                )
            )
        if _norm(before.positioning) != _norm(after.positioning):
            changes.append(
                Change(
                    kind=ChangeKind.POSITIONING_CHANGE,
                    competitor=after.name,
                    summary=f"{after.name} repositioned.",
                    before=before.positioning,
                    after=after.positioning,
                )
            )

    # Overall threat level shift.
    if previous.overall_threat_level != current.overall_threat_level:
        changes.append(
            Change(
                kind=ChangeKind.OVERALL_THREAT_CHANGE,
                summary=(
                    f"Overall threat moved from {previous.overall_threat_level.label} "
                    f"to {current.overall_threat_level.label}."
                ),
                before=previous.overall_threat_level.label,
                after=current.overall_threat_level.label,
            )
        )

    return changes


def _norm(text: str) -> str:
    return " ".join((text or "").split()).lower()


__all__ = ["diff_reports"]
