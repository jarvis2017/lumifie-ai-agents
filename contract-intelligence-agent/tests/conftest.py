"""Shared fixtures, including fake providers (no network, no API keys).

These fakes implement the same surface the agent uses from ``LLMProvider``
(``model``, ``supports_tools``, ``complete(...) -> CompletionResult``), so the
whole pipeline runs in tests exactly as the live path does — for both the native
tool-use path and the JSON-mode fallback.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from lumifie_core import CompletionResult, ToolCall

from contract_intelligence.config import ContractSettings

_USAGE = {"input_tokens": 120, "output_tokens": 60, "total_tokens": 180}


class FakeToolProvider:
    """A provider that supports tools and scripts a clause+risk per chunk."""

    supports_tools = True

    def __init__(self, model: str = "claude-opus-4-8") -> None:
        self.model = model
        self.calls = 0
        self._uid = 0

    def _id(self) -> str:
        self._uid += 1
        return f"call_{self._uid}"

    def complete(self, messages: list[dict[str, Any]], **kwargs: Any) -> CompletionResult:
        self.calls += 1
        last = messages[-1]

        # Follow-up turn carrying tool results -> section complete.
        if last["role"] == "tool":
            return CompletionResult(text="Section complete.", finish_reason="stop", usage=_USAGE)

        content = last["content"]
        if "finalize_analysis exactly once" in content:
            return CompletionResult(
                text=None,
                tool_calls=[
                    ToolCall(
                        id=self._id(),
                        name="finalize_analysis",
                        arguments={
                            "overall_risk_level": "high",
                            "executive_summary": (
                                "Vendor-favorable MSA with uncapped client indemnity and "
                                "unilateral termination. Negotiate before signing."
                            ),
                        },
                    )
                ],
                finish_reason="tool_calls",
                usage=_USAGE,
            )

        return CompletionResult(
            text=None,
            tool_calls=[
                ToolCall(
                    id=self._id(),
                    name="record_clause",
                    arguments={
                        "category": "payment_terms",
                        "title": "Payment due within 15 days",
                        "summary": "Invoices are due within fifteen days.",
                        "verbatim_excerpt": "due and payable within fifteen (15) days",
                        "page": 1,
                    },
                ),
                ToolCall(
                    id=self._id(),
                    name="flag_risk",
                    arguments={
                        "severity": "high",
                        "category": "liability",
                        "title": "Uncapped client indemnification",
                        "description": "Client indemnity is explicitly uncapped.",
                        "recommendation": "Cap indemnity at fees paid in the prior 12 months.",
                        "related_excerpt": "shall be unlimited",
                    },
                ),
            ],
            finish_reason="tool_calls",
            usage=_USAGE,
        )


class FakeJSONProvider:
    """A provider without tool support; returns JSON per the fallback path."""

    supports_tools = False

    def __init__(self, model: str = "ollama/llama3.1") -> None:
        self.model = model
        self.calls = 0

    def complete(self, messages: list[dict[str, Any]], **kwargs: Any) -> CompletionResult:
        self.calls += 1
        content = messages[-1]["content"]
        if '"clauses"' in content:  # per-chunk extraction
            payload = {
                "clauses": [
                    {
                        "category": "termination",
                        "title": "Auto-renewal",
                        "summary": "Renews annually unless 90 days notice.",
                        "verbatim_excerpt": "automatically renew",
                        "page": 2,
                    }
                ],
                "risks": [
                    {
                        "severity": "medium",
                        "category": "termination",
                        "title": "Auto-renewal trap",
                        "description": "Easy to miss the 90-day window.",
                        "recommendation": "Set a renewal reminder.",
                        "related_excerpt": "automatically renew",
                    }
                ],
            }
        else:  # finalize
            payload = {
                "overall_risk_level": "medium",
                "executive_summary": "Standard MSA with manageable risks.",
            }
        return CompletionResult(text=json.dumps(payload), finish_reason="stop", usage=_USAGE)


@pytest.fixture
def tool_provider() -> FakeToolProvider:
    return FakeToolProvider()


@pytest.fixture
def json_provider() -> FakeJSONProvider:
    return FakeJSONProvider()


@pytest.fixture
def settings() -> ContractSettings:
    # Small chunk size forces multiple chunks, exercising the multi-step loop.
    return ContractSettings(
        model="claude-opus-4-8",
        max_tokens=2000,
        max_chunk_chars=900,
        max_iterations_per_chunk=6,
    )


@pytest.fixture(scope="session")
def sample_pdf(tmp_path_factory: pytest.TempPathFactory) -> Path:
    pytest.importorskip("reportlab", reason="reportlab is needed to build the PDF fixture")
    from scripts.make_sample_pdf import build_pdf  # noqa: PLC0415

    out = tmp_path_factory.mktemp("contract") / "sample_contract.pdf"
    build_pdf(out)
    return out
