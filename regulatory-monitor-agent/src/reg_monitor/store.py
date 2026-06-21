"""SQLite persistence for monitoring runs, enabling run-over-run diffs.

Each run is stored as a JSON blob keyed by the business profile hash (industry +
location) with a timestamp, so the agent can fetch the most recent prior run and
surface which findings are new this week.
"""

from __future__ import annotations

import sqlite3
from datetime import UTC, datetime
from pathlib import Path

from lumifie_core import logger

from reg_monitor.models import BusinessProfile, Digest

_SCHEMA = """
CREATE TABLE IF NOT EXISTS runs (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    profile_key   TEXT NOT NULL,
    profile_hash  TEXT NOT NULL,
    industry      TEXT NOT NULL,
    location      TEXT NOT NULL,
    model         TEXT NOT NULL,
    created_at    TEXT NOT NULL,
    payload       TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_runs_profile
    ON runs (profile_hash, id);
"""


class MonitorStore:
    """Thin SQLite wrapper for storing and retrieving :class:`Digest` runs."""

    def __init__(self, path: str | Path = "reg_monitor.db") -> None:
        self.path = str(path)
        self._conn = sqlite3.connect(self.path)
        self._conn.row_factory = sqlite3.Row
        self._conn.executescript(_SCHEMA)
        self._conn.commit()

    def close(self) -> None:
        self._conn.close()

    def __enter__(self) -> MonitorStore:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    def latest(self, profile: BusinessProfile) -> Digest | None:
        """Return the most recent stored run for this profile, or None."""
        row = self._conn.execute(
            "SELECT payload FROM runs WHERE profile_hash = ? ORDER BY id DESC LIMIT 1",
            (profile.hash(),),
        ).fetchone()
        if row is None:
            return None
        return Digest.model_validate_json(row["payload"])

    def save(self, digest: Digest) -> int:
        """Persist a run; returns its row id."""
        profile = digest.profile
        cur = self._conn.execute(
            "INSERT INTO runs "
            "(profile_key, profile_hash, industry, location, model, created_at, payload) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                profile.key(),
                profile.hash(),
                profile.industry.strip().lower(),
                profile.location.strip().lower(),
                digest.model,
                datetime.now(UTC).isoformat(),
                digest.model_dump_json(),
            ),
        )
        self._conn.commit()
        logger.info(
            "Saved run #{} for {} / {}", cur.lastrowid, profile.industry, profile.location
        )
        return int(cur.lastrowid)

    def count(self, profile: BusinessProfile) -> int:
        row = self._conn.execute(
            "SELECT COUNT(*) AS n FROM runs WHERE profile_hash = ?",
            (profile.hash(),),
        ).fetchone()
        return int(row["n"])


__all__ = ["MonitorStore"]
