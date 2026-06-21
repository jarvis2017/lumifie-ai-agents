"""Tests for the CLI (offline; uses a temp Chroma path and stub provider)."""

from __future__ import annotations

import sys

from rag_chatbot.cli import run


def test_ingest_then_ask(tmp_path, capsys, demo_files):
    db = str(tmp_path / "db")
    assert run(["--db", db, "--offline", "ingest", demo_files[0]]) == 0
    out = capsys.readouterr().out
    assert "added" in out

    assert run(["--db", db, "--offline", "ask", "What is the warranty?"]) == 0
    out = capsys.readouterr().out
    assert "confidence" in out


def test_demo_command(tmp_path, capsys):
    assert run(["--db", str(tmp_path / "db"), "--offline", "demo"]) == 0
    out = capsys.readouterr().out
    assert "Q:" in out
    assert "confidence" in out


def test_ui_command_errors_gracefully_without_gradio(tmp_path, monkeypatch):
    # Force gradio unavailable (it's an optional [ui] extra) -> graceful exit 2.
    monkeypatch.setitem(sys.modules, "gradio", None)
    assert run(["--db", str(tmp_path / "db"), "--offline", "ui"]) == 2
