"""SQLite audit trail.

Every proposed action — and every decision and result against it — is written
here, so there is a complete, queryable record of what the agent did and why.
The DB path is configurable; the schema is created on connect.
"""

from __future__ import annotations

import json
import sqlite3
from datetime import UTC, datetime
from pathlib import Path

from lumifie_core import logger

from crm_automation.models import AuditEntry, Decision, RunSummary

_SCHEMA = """
CREATE TABLE IF NOT EXISTS audit (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp     TEXT NOT NULL,
    rule_name     TEXT NOT NULL,
    trigger_type  TEXT NOT NULL,
    action_type   TEXT NOT NULL,
    target_id     TEXT NOT NULL,
    params        TEXT NOT NULL,
    decision      TEXT NOT NULL,
    result        TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_audit_target ON audit (target_id);
CREATE INDEX IF NOT EXISTS idx_audit_decision ON audit (decision);
"""


class AuditLog:
    """Thin SQLite wrapper for appending and querying audit entries."""

    def __init__(self, path: str | Path = "crm_audit.db") -> None:
        self.path = str(path)
        self._conn = sqlite3.connect(self.path)
        self._conn.row_factory = sqlite3.Row
        self._conn.executescript(_SCHEMA)
        self._conn.commit()

    def close(self) -> None:
        self._conn.close()

    def __enter__(self) -> AuditLog:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    def record(self, entry: AuditEntry) -> AuditEntry:
        """Persist one audit entry; returns it with its assigned row id."""
        cur = self._conn.execute(
            "INSERT INTO audit "
            "(timestamp, rule_name, trigger_type, action_type, target_id, "
            " params, decision, result) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                (entry.timestamp or datetime.now(UTC)).isoformat(),
                entry.rule_name,
                entry.trigger_type.value,
                entry.action_type.value,
                entry.target_id,
                json.dumps(entry.params, default=str),
                entry.decision.value,
                entry.result,
            ),
        )
        self._conn.commit()
        entry.id = int(cur.lastrowid)
        logger.debug(
            "Audited {} -> {} [{}]", entry.action_type.value, entry.decision.value, entry.target_id
        )
        return entry

    def all_entries(self) -> list[AuditEntry]:
        rows = self._conn.execute("SELECT * FROM audit ORDER BY id").fetchall()
        return [self._row_to_entry(r) for r in rows]

    def by_decision(self, decision: Decision) -> list[AuditEntry]:
        rows = self._conn.execute(
            "SELECT * FROM audit WHERE decision = ? ORDER BY id", (decision.value,)
        ).fetchall()
        return [self._row_to_entry(r) for r in rows]

    def count(self) -> int:
        row = self._conn.execute("SELECT COUNT(*) AS n FROM audit").fetchone()
        return int(row["n"])

    @staticmethod
    def _row_to_entry(row: sqlite3.Row) -> AuditEntry:
        return AuditEntry(
            id=row["id"],
            timestamp=datetime.fromisoformat(row["timestamp"]),
            rule_name=row["rule_name"],
            trigger_type=row["trigger_type"],
            action_type=row["action_type"],
            target_id=row["target_id"],
            params=json.loads(row["params"]),
            decision=row["decision"],
            result=row["result"],
        )


def record_run(log: AuditLog, summary: RunSummary) -> None:
    """Persist every audit entry collected during a run."""
    for entry in summary.audit:
        log.record(entry)


__all__ = ["AuditLog", "record_run"]
