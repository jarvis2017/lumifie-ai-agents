"""Small shared helpers (slugs, date math) used across the package."""

from __future__ import annotations

import re
from datetime import UTC, datetime, timedelta


def slugify(text: str) -> str:
    """Filesystem-safe slug, e.g. 'Food Service' -> 'food-service'."""
    return re.sub(r"[^a-z0-9]+", "-", (text or "").strip().lower()).strip("-") or "x"


def lookback_date(days: int, *, now: datetime | None = None) -> str:
    """Return the ISO date (YYYY-MM-DD) ``days`` before ``now`` (UTC)."""
    base = now or datetime.now(UTC)
    return (base - timedelta(days=max(days, 0))).date().isoformat()


__all__ = ["slugify", "lookback_date"]
