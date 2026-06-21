"""Tests for the CLI (offline; uses a temp Chroma path and stub provider)."""

from __future__ import annotations

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


def test_ui_command_errors_gracefully_without_gradio(tmp_path):
    # gradio is an optional extra not installed in dev/CI -> exit code 2.
    assert run(["--db", str(tmp_path / "db"), "--offline", "ui"]) == 2
