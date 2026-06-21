"""Detect which impact statements are new versus the previous run.

New-detection is by fingerprint (normalized URL, or title fallback): any impact
whose fingerprint was not present in the previous run's impacts is "new this
week". The first run has no previous, so everything is new (the baseline).
"""

from __future__ import annotations

from reg_monitor.models import Digest, ImpactStatement


def seen_fingerprints(previous: Digest | None) -> set[str]:
    """Fingerprints of every impact recorded in the previous run."""
    if previous is None:
        return set()
    return {i.fingerprint() for i in previous.impacts}


def new_impacts(
    previous: Digest | None, current: list[ImpactStatement]
) -> list[ImpactStatement]:
    """Return the impacts in ``current`` not seen in ``previous``.

    With no previous run, every current impact is new (this is the baseline).
    """
    seen = seen_fingerprints(previous)
    out: list[ImpactStatement] = []
    emitted: set[str] = set()
    for impact in current:
        fp = impact.fingerprint()
        if fp in seen or fp in emitted:
            continue
        emitted.add(fp)
        out.append(impact)
    return out


__all__ = ["new_impacts", "seen_fingerprints"]
