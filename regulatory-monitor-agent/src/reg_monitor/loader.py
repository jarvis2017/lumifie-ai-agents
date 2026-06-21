"""Load a business profile + sources from a single JSON file."""

from __future__ import annotations

import json
from pathlib import Path

from reg_monitor.models import MonitoringConfig


def load_config(path: str | Path) -> MonitoringConfig:
    """Parse and validate a monitoring config JSON file.

    Raises ``FileNotFoundError`` if missing and ``ValueError`` on invalid JSON or
    schema so the CLI can report a clear boundary error.
    """
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"Profile file not found: {p}")
    try:
        raw = json.loads(p.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid JSON in {p}: {exc}") from exc
    try:
        return MonitoringConfig.model_validate(raw)
    except Exception as exc:  # pydantic ValidationError
        raise ValueError(f"Invalid profile config in {p}: {exc}") from exc


__all__ = ["load_config"]
