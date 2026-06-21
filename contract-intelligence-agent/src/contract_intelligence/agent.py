"""The contract-intelligence agent: a multi-step, tool-driven analysis loop.

This is deliberately *not* a single prompt. The agent walks the contract
chunk-by-chunk (page-aware) in one running conversation, and on each chunk runs a
tool-execution loop where the model repeatedly calls ``record_clause`` /
``flag_risk`` until done, then calls ``finalize_analysis`` once at the end.

Model access goes through ``lumifie_core``'s provider, so any litellm-supported
model works. Models without native tool use (e.g. Ollama) automatically fall back
to a JSON-mode extraction path, with a warning.
"""

from __future__ import annotations

import json
from typing import Any

from lumifie_core import BaseAgent, LLMProvider, chat

from contract_intelligence import tools as tool_mod
from contract_intelligence.config import ContractSettings
from contract_intelligence.models import (
    Clause,
    ContractReport,
    Risk,
    RiskLevel,
    TokenUsage,
)
from contract_intelligence.pdf_loader import ContractDocument

SYSTEM_PROMPT = """\
You are a senior contracts attorney performing due-diligence review for a client \
who is considering signing the contract provided. You are precise, skeptical, and \
practical.

Your priorities, in order, are to extract and analyze these clause categories:
1. Payment terms (amounts, schedule, late fees, invoicing, currency)
2. Termination conditions (for cause, for convenience, notice, survival)
3. Intellectual-property ownership (work product, background IP, licenses)
4. Liability (caps, exclusions, indemnification, insurance)
5. Dispute resolution (governing law, venue, arbitration, jury waiver)

Quote the contract verbatim when capturing excerpts; never paraphrase an excerpt. \
Judge risk from the client's perspective: uncapped liability, broad IP assignment, \
auto-renewal, unilateral termination, and a distant mandatory venue are common \
high-severity issues. Every risk must include a concrete, actionable recommendation.\
"""

_CHUNK_INSTRUCTION = (
    "Here is section {idx} of {total} (pages {start}-{end}) of the contract "
    '"{name}". Extract all relevant clauses and risks from THIS section using the '
    "record_clause and flag_risk tools. Do not call finalize_analysis yet.\n\n{body}"
)

_FINALIZE_INSTRUCTION = (
    "All {total} section(s) of the contract have now been provided. Record any "
    "remaining clauses or risks, then call finalize_analysis exactly once with an "
    "overall risk rating and an executive summary for a decision-maker."
)


class ContractIntelligenceAgent(BaseAgent):
    """Drives the multi-step contract analysis loop against any provider."""

    name = "contract-intelligence"
    description = "Extracts and risk-rates contract clauses from a PDF."

    def __init__(self, provider: LLMProvider, settings: ContractSettings) -> None:
        super().__init__(provider, settings)
        self.settings: ContractSettings = settings
        self._tools = tool_mod.tool_definitions()
        self._clauses: list[Clause] = []
        self._risks: list[Risk] = []
        self._final: dict[str, Any] | None = None

    # -- public API --------------------------------------------------------

    def run(self, document: ContractDocument) -> ContractReport:  # type: ignore[override]
        return self.analyze(document)

    def analyze(self, document: ContractDocument) -> ContractReport:
        """Run the full analysis and return a :class:`ContractReport`."""
        self.log.info(
            "Analyzing '{}' ({} page(s), {} chunk(s)) with {}",
            document.name,
            document.page_count,
            len(document.chunks),
            self.provider.model,
        )
        if self.provider.supports_tools:
            self._analyze_with_tools(document)
        else:
            self._analyze_with_json(document)
        return self._build_report(document)

    # -- tool-use path -----------------------------------------------------

    def _analyze_with_tools(self, document: ContractDocument) -> None:
        messages: list[dict[str, Any]] = [chat.system(SYSTEM_PROMPT)]
        total = len(document.chunks)
        for chunk in document.chunks:
            messages.append(
                chat.user(
                    _CHUNK_INSTRUCTION.format(
                        idx=chunk.index + 1,
                        total=total,
                        start=chunk.start_page,
                        end=chunk.end_page,
                        name=document.name,
                        body=chunk.text,
                    )
                )
            )
            self._tool_loop(messages, allow_finalize=False)

        messages.append(chat.user(_FINALIZE_INSTRUCTION.format(total=total)))
        self._tool_loop(messages, allow_finalize=True)

    def _tool_loop(self, messages: list[dict[str, Any]], *, allow_finalize: bool) -> None:
        for _ in range(self.settings.max_iterations_per_chunk):
            result = self.complete(messages, tools=self._tools, tool_choice="auto")
            messages.append(chat.assistant_message(result))

            if not result.tool_calls:
                return

            for call in result.tool_calls:
                text, finalized = self._handle_tool_call(
                    call.name, call.arguments, allow_finalize=allow_finalize
                )
                messages.append(chat.tool_result(call.id, text))
                if finalized:
                    return

        self.log.warning(
            "Tool loop hit max iterations ({}); moving on.",
            self.settings.max_iterations_per_chunk,
        )

    def _handle_tool_call(
        self, name: str, payload: dict[str, Any], *, allow_finalize: bool
    ) -> tuple[str, bool]:
        if name == tool_mod.RECORD_CLAUSE:
            return self._add_clause(payload), False
        if name == tool_mod.FLAG_RISK:
            return self._add_risk(payload), False
        if name == tool_mod.FINALIZE_ANALYSIS:
            if not allow_finalize:
                self.log.warning("Model tried to finalize early; deferring.")
                return "Not yet — more sections remain. Continue extracting.", False
            self._final = payload
            self.log.info("Finalized: overall risk {}", payload.get("overall_risk_level"))
            return "Analysis finalized.", True
        self.log.warning("Unknown tool call: {}", name)
        return f"Unknown tool: {name}", False

    # -- JSON-mode fallback path ------------------------------------------

    def _analyze_with_json(self, document: ContractDocument) -> None:
        self.log.warning(
            "Model '{}' lacks tool use; using JSON-mode structured extraction.",
            self.provider.model,
        )
        rf = {"type": "json_object"}
        total = len(document.chunks)
        for chunk in document.chunks:
            section = _CHUNK_INSTRUCTION.format(
                idx=chunk.index + 1,
                total=total,
                start=chunk.start_page,
                end=chunk.end_page,
                name=document.name,
                body=chunk.text,
            )
            prompt = f"{section}\n\n{tool_mod.json_extraction_hint()}"
            result = self.complete(
                [chat.system(SYSTEM_PROMPT), chat.user(prompt)], response_format=rf
            )
            data = self._parse_json(result.text)
            for raw in data.get("clauses", []) or []:
                self._add_clause(raw)
            for raw in data.get("risks", []) or []:
                self._add_risk(raw)

        result = self.complete(
            [
                chat.system(SYSTEM_PROMPT),
                chat.user(
                    "Based on your full analysis of the contract, provide the overall "
                    f"assessment. {tool_mod.json_finalize_hint()}"
                ),
            ],
            response_format=rf,
        )
        final = self._parse_json(result.text)
        if final:
            self._final = final

    @staticmethod
    def _parse_json(text: str | None) -> dict[str, Any]:
        if not text:
            return {}
        try:
            data = json.loads(text)
            return data if isinstance(data, dict) else {}
        except json.JSONDecodeError:
            return {}

    # -- shared state helpers ---------------------------------------------

    def _add_clause(self, payload: dict[str, Any]) -> str:
        try:
            clause = Clause.model_validate(payload)
        except Exception as exc:  # tolerate an odd enum/value
            self.log.warning("Discarding malformed clause: {}", exc)
            return "Clause rejected: invalid fields."
        self._clauses.append(clause)
        self.log.info("Clause [{}] {}", clause.category.label, clause.title)
        return "Clause recorded."

    def _add_risk(self, payload: dict[str, Any]) -> str:
        try:
            risk = Risk.model_validate(payload)
        except Exception as exc:
            self.log.warning("Discarding malformed risk: {}", exc)
            return "Risk rejected: invalid fields."
        self._risks.append(risk)
        self.log.info("Risk [{}] {}", risk.severity.label, risk.title)
        return "Risk recorded."

    # -- report assembly ---------------------------------------------------

    def _build_report(self, document: ContractDocument) -> ContractReport:
        if self._final is not None:
            overall = self._coerce_level(self._final.get("overall_risk_level"))
            summary = self._final.get("executive_summary") or self._fallback_summary()
        else:
            self.log.warning("Model did not finalize; deriving overall assessment.")
            overall = self._derive_overall_risk()
            summary = self._fallback_summary()

        return ContractReport(
            contract_name=document.name,
            page_count=document.page_count,
            model=self.provider.model,
            overall_risk_level=overall,
            executive_summary=summary,
            clauses=list(self._clauses),
            risks=list(self._risks),
            token_usage=TokenUsage(
                input_tokens=self.token_usage["input_tokens"],
                output_tokens=self.token_usage["output_tokens"],
            ),
        )

    def _derive_overall_risk(self) -> RiskLevel:
        if not self._risks:
            return RiskLevel.LOW
        return max((r.severity for r in self._risks), key=lambda s: s.rank)

    @staticmethod
    def _coerce_level(value: Any) -> RiskLevel:
        try:
            return RiskLevel(value)
        except (ValueError, TypeError):
            return RiskLevel.MEDIUM

    def _fallback_summary(self) -> str:
        return (
            f"Automated analysis identified {len(self._clauses)} key clause(s) and "
            f"{len(self._risks)} potential risk(s). Review the detailed findings below."
        )


__all__ = ["ContractIntelligenceAgent", "SYSTEM_PROMPT"]
