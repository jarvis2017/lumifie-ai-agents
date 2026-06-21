"""Shared test fixtures, including a scripted (no-network) LLM client.

The scripted client implements the same ``create(**kwargs)`` surface as the real
:class:`AnthropicLLMClient`, so the agent runs end-to-end in tests with no API
key and no network — exercising chunking, the tool loop, finalization, and report
rendering exactly as the live path does.
"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from contract_intelligence.config import Settings


def _block(**kw: Any) -> SimpleNamespace:
    return SimpleNamespace(**kw)


def _usage() -> SimpleNamespace:
    return _block(
        input_tokens=120,
        output_tokens=60,
        cache_read_input_tokens=0,
        cache_creation_input_tokens=0,
    )


def _response(content: list[SimpleNamespace], stop_reason: str) -> SimpleNamespace:
    return _block(content=content, stop_reason=stop_reason, usage=_usage())


class ScriptedLLMClient:
    """A deterministic stand-in for the Anthropic client.

    It reacts to the last user message the agent sends:

    * a chunk instruction (string)  -> returns record_clause + flag_risk calls
    * a tool_result follow-up (list) -> returns an empty end_turn (section done)
    * the finalize instruction       -> returns a finalize_analysis call
    """

    def __init__(self) -> None:
        self.calls = 0
        self._uid = 0

    def _next_id(self) -> str:
        self._uid += 1
        return f"toolu_{self._uid}"

    def create(self, **kwargs: Any) -> SimpleNamespace:
        self.calls += 1
        last = kwargs["messages"][-1]
        content = last["content"]

        # Follow-up turn carrying tool_result blocks -> section complete.
        if isinstance(content, list):
            return _response([_block(type="text", text="Section complete.")], "end_turn")

        # Final pass.
        if "finalize_analysis exactly once" in content:
            return _response(
                [
                    _block(
                        type="tool_use",
                        id=self._next_id(),
                        name="finalize_analysis",
                        input={
                            "overall_risk_level": "high",
                            "executive_summary": (
                                "Vendor-favorable MSA with unlimited client indemnity "
                                "and unilateral termination. Negotiate before signing."
                            ),
                        },
                    )
                ],
                "tool_use",
            )

        # A contract section -> extract one clause and one risk.
        return _response(
            [
                _block(
                    type="tool_use",
                    id=self._next_id(),
                    name="record_clause",
                    input={
                        "category": "payment_terms",
                        "title": "Payment due within 15 days",
                        "summary": "Invoices are due within fifteen days of issue.",
                        "verbatim_excerpt": "due and payable within fifteen (15) days",
                        "page": 1,
                    },
                ),
                _block(
                    type="tool_use",
                    id=self._next_id(),
                    name="flag_risk",
                    input={
                        "severity": "high",
                        "category": "liability",
                        "title": "Uncapped client indemnification",
                        "description": "Client indemnity is explicitly uncapped.",
                        "recommendation": "Cap indemnity at fees paid in the prior 12 months.",
                        "related_excerpt": "shall be unlimited",
                    },
                ),
            ],
            "tool_use",
        )


@pytest.fixture
def scripted_client() -> ScriptedLLMClient:
    return ScriptedLLMClient()


@pytest.fixture
def settings() -> Settings:
    # Small chunk size forces multiple chunks from the sample PDF, exercising the
    # multi-step loop.
    return Settings(
        api_key="test-key",
        model="claude-opus-4-8",
        effort="high",
        max_tokens=2000,
        max_chunk_chars=900,
        max_iterations_per_chunk=6,
    )


@pytest.fixture(scope="session")
def sample_pdf(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """Generate the multi-page sample contract PDF once per test session."""
    pytest.importorskip("reportlab", reason="reportlab is needed to build the PDF fixture")
    from scripts.make_sample_pdf import build_pdf  # noqa: PLC0415

    out = tmp_path_factory.mktemp("contract") / "sample_contract.pdf"
    build_pdf(out)
    return out
