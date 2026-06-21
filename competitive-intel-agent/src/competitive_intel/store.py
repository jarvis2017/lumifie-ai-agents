"""SQLite persistence for intel runs, enabling run-over-run diffs.

Each run is stored as a JSON blob keyed by (company, vertical) with a timestamp,
so the agent can fetch the most recent prior run and surface what changed.
"""

from __future__ import annotations

import sqlite3
from datetime import UTC, datetime
from pathlib import Path

from lumifie_core import logger

from competitive_intel.models import IntelReport

_SCHEMA = """
CREATE TABLE IF NOT EXISTS runs (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    company     TEXT NOT NULL,
    vertical    TEXT NOT NULL,
    model       TEXT NOT NULL,
    created_at  TEXT NOT NULL,
    payload     TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_runs_company_vertical
    ON runs (company, vertical, id);
"""


def _key(text: str) -> str:
    return text.strip().lower()


class IntelStore:
    """Thin SQLite wrapper for storing and retrieving :class:`IntelReport` runs."""

    def __init__(self, path: str | Path = "competitive_intel.db") -> None:
        self.path = str(path)
        self._conn = sqlite3.connect(self.path)
        self._conn.row_factory = sqlite3.Row
        self._conn.executescript(_SCHEMA)
        self._conn.commit()

    def close(self) -> None:
        self._conn.close()

    def __enter__(self) -> IntelStore:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    def latest(self, company: str, vertical: str) -> IntelReport | None:
        """Return the most recent stored run for (company, vertical), or None."""
        row = self._conn.execute(
            "SELECT payload FROM runs WHERE company = ? AND vertical = ? "
            "ORDER BY id DESC LIMIT 1",
            (_key(company), _key(vertical)),
        ).fetchone()
        if row is None:
            return None
        return IntelReport.model_validate_json(row["payload"])

    def save(self, report: IntelReport) -> int:
        """Persist a run; returns its row id."""
        cur = self._conn.execute(
            "INSERT INTO runs (company, vertical, model, created_at, payload) "
            "VALUES (?, ?, ?, ?, ?)",
            (
                _key(report.company),
                _key(report.vertical),
                report.model,
                datetime.now(UTC).isoformat(),
                report.model_dump_json(),
            ),
        )
        self._conn.commit()
        logger.info("Saved run #{} for {} / {}", cur.lastrowid, report.company, report.vertical)
        return int(cur.lastrowid)

    def count(self, company: str, vertical: str) -> int:
        row = self._conn.execute(
            "SELECT COUNT(*) AS n FROM runs WHERE company = ? AND vertical = ?",
            (_key(company), _key(vertical)),
        ).fetchone()
        return int(row["n"])


__all__ = ["IntelStore"]
