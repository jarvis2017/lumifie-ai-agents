"""SQLite persistence: pipeline runs, lead history, and the action audit trail.

This is durable cross-run state (separate from LangGraph checkpointing, which holds
the in-flight conversation/graph state). Lead history is what powers stale-deal
detection across runs.
"""

from __future__ import annotations

import sqlite3
from datetime import UTC, datetime, timedelta
from pathlib import Path

from sales_ops.models import ActionOutcome, ScoredLead, StaleDeal

_SCHEMA = """
CREATE TABLE IF NOT EXISTS pipelines (
    id          TEXT PRIMARY KEY,
    created_at  TEXT NOT NULL,
    model       TEXT NOT NULL,
    dry_run     INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS leads (
    lead_id       TEXT PRIMARY KEY,
    company       TEXT NOT NULL,
    stage         TEXT NOT NULL,
    icp_fit       INTEGER NOT NULL,
    last_seen     TEXT NOT NULL,
    last_pipeline TEXT
);
CREATE TABLE IF NOT EXISTS actions (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    pipeline_id TEXT NOT NULL,
    action_id   TEXT NOT NULL,
    type        TEXT NOT NULL,
    lead_id     TEXT,
    decision    TEXT NOT NULL,
    detail      TEXT,
    ok          INTEGER NOT NULL,
    ts          TEXT NOT NULL
);
"""

_TERMINAL_STAGES = {"qualified", "disqualified"}


def _now() -> str:
    return datetime.now(UTC).isoformat()


class SalesOpsStore:
    def __init__(self, path: str | Path = "sales_ops.db") -> None:
        self.path = str(path)
        self._conn = sqlite3.connect(self.path)
        self._conn.row_factory = sqlite3.Row
        self._conn.executescript(_SCHEMA)
        self._conn.commit()

    def close(self) -> None:
        self._conn.close()

    def __enter__(self) -> SalesOpsStore:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    def save_pipeline(self, pipeline_id: str, model: str, dry_run: bool) -> None:
        self._conn.execute(
            "INSERT OR REPLACE INTO pipelines (id, created_at, model, dry_run) VALUES (?,?,?,?)",
            (pipeline_id, _now(), model, int(dry_run)),
        )
        self._conn.commit()

    def upsert_lead(
        self, lead: ScoredLead, pipeline_id: str, *, last_seen: str | None = None
    ) -> None:
        self._conn.execute(
            "INSERT INTO leads (lead_id, company, stage, icp_fit, last_seen, last_pipeline) "
            "VALUES (?,?,?,?,?,?) "
            "ON CONFLICT(lead_id) DO UPDATE SET company=excluded.company, stage=excluded.stage, "
            "icp_fit=excluded.icp_fit, last_seen=excluded.last_seen, "
            "last_pipeline=excluded.last_pipeline",
            (
                lead.id,
                lead.company,
                lead.stage.value,
                int(lead.icp_fit),
                last_seen or _now(),
                pipeline_id,
            ),
        )
        self._conn.commit()

    def record_action(self, pipeline_id: str, outcome: ActionOutcome) -> None:
        self._conn.execute(
            "INSERT INTO actions (pipeline_id, action_id, type, lead_id, decision, detail, ok, ts) "
            "VALUES (?,?,?,?,?,?,?,?)",
            (
                pipeline_id,
                outcome.action_id,
                outcome.type.value,
                outcome.lead_id,
                outcome.decision.value,
                outcome.detail,
                int(outcome.ok),
                _now(),
            ),
        )
        self._conn.commit()

    def stale_deals(self, stale_after_days: int, *, now: datetime | None = None) -> list[StaleDeal]:
        """Leads not touched in > N days and not in a terminal stage."""
        now = now or datetime.now(UTC)
        cutoff = now - timedelta(days=stale_after_days)
        out: list[StaleDeal] = []
        for row in self._conn.execute("SELECT lead_id, company, stage, last_seen FROM leads"):
            if row["stage"] in _TERMINAL_STAGES:
                continue
            try:
                seen = datetime.fromisoformat(row["last_seen"])
            except ValueError:
                continue
            if seen < cutoff:
                out.append(
                    StaleDeal(
                        lead_id=row["lead_id"],
                        company=row["company"],
                        stage=row["stage"],
                        days_stale=(now - seen).days,
                    )
                )
        return sorted(out, key=lambda d: d.days_stale, reverse=True)

    def action_count(self, pipeline_id: str | None = None) -> int:
        if pipeline_id:
            cur = self._conn.execute(
                "SELECT COUNT(*) AS n FROM actions WHERE pipeline_id = ?", (pipeline_id,)
            )
        else:
            cur = self._conn.execute("SELECT COUNT(*) AS n FROM actions")
        return int(cur.fetchone()["n"])

    def lead_count(self) -> int:
        return int(self._conn.execute("SELECT COUNT(*) AS n FROM leads").fetchone()["n"])


__all__ = ["SalesOpsStore"]
