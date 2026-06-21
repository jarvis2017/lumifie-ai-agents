"""The contract-intelligence agent: a multi-step, tool-driven analysis loop.

This is deliberately *not* a single prompt. The agent:

1. Walks the contract chunk-by-chunk (page-aware), keeping one running
   conversation so context accumulates across pages.
2. On each chunk, runs a tool-execution loop where the model repeatedly calls
   ``record_clause`` / ``flag_risk`` until it has nothing more to extract.
3. After the last chunk, asks the model to ``finalize_analysis`` with an overall
   risk rating and executive summary.

The model decides what to extract and when it is done; the harness owns the loop,
tool execution, logging, and state — the standard manual agentic-loop pattern.
"""

from __future__ import annotations

from typing import Any

from loguru import logger

from contract_intelligence import tools as tool_mod
from contract_intelligence.config import Settings
from contract_intelligence.llm_client import MessageCreator
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

How to work:
- Use the record_clause tool once per distinct clause you find. Quote the \
contract verbatim in verbatim_excerpt — never paraphrase in that field.
- Use the flag_risk tool for anything unfavorable, ambiguous, missing, or \
one-sided. Every risk must include a concrete, actionable recommendation.
- Judge risk from the client's perspective: uncapped liability, broad IP \
assignment, auto-renewal, unilateral termination, and mandatory venue far from \
the client are common high-severity issues.
- The contract is delivered to you in sections. Analyze each section as it \
arrives. Do NOT call finalize_analysis until you are explicitly told that all \
sections have been provided.
- When you have finished extracting from a section, stop and wait for the next.
"""

_CHUNK_INSTRUCTION = (
    "Here is section {idx} of {total} (pages {start}-{end}) of the contract "
    '"{name}". Extract all relevant clauses and risks from THIS section using '
    "the record_clause and flag_risk tools. Do not call finalize_analysis yet."
    "\n\n{body}"
)

_FINALIZE_INSTRUCTION = (
    "All {total} section(s) of the contract have now been provided. Record any "
    "remaining clauses or risks, then call finalize_analysis exactly once with "
    "an overall risk rating and an executive summary for a decision-maker."
)


class ContractIntelligenceAgent:
    """Drives the multi-step contract analysis loop against an LLM client."""

    def __init__(self, client: MessageCreator, settings: Settings) -> None:
        self._client = client
        self._settings = settings
        self._tools = tool_mod.tool_definitions()

        # Accumulated analysis state.
        self._clauses: list[Clause] = []
        self._risks: list[Risk] = []
        self._usage = TokenUsage()
        self._final: dict[str, Any] | None = None

    # -- public API --------------------------------------------------------

    def analyze(self, document: ContractDocument) -> ContractReport:
        """Run the full analysis and return a :class:`ContractReport`."""
        logger.info(
            "Starting analysis of '{}' ({} page(s), {} chunk(s)) with {}",
            document.name,
            document.page_count,
            len(document.chunks),
            self._settings.model,
        )

        messages: list[dict[str, Any]] = []
        total = len(document.chunks)

        for chunk in document.chunks:
            user_text = _CHUNK_INSTRUCTION.format(
                idx=chunk.index + 1,
                total=total,
                start=chunk.start_page,
                end=chunk.end_page,
                name=document.name,
                body=chunk.text,
            )
            messages.append({"role": "user", "content": user_text})
            self._run_tool_loop(messages, allow_finalize=False)

        # Final pass: ask for the overall assessment.
        messages.append(
            {"role": "user", "content": _FINALIZE_INSTRUCTION.format(total=total)}
        )
        self._run_tool_loop(messages, allow_finalize=True)

        return self._build_report(document)

    # -- internals ---------------------------------------------------------

    def _run_tool_loop(
        self, messages: list[dict[str, Any]], *, allow_finalize: bool
    ) -> None:
        """Call the model and execute tool calls until it stops or finalizes."""
        for _ in range(self._settings.max_iterations_per_chunk):
            response = self._client.create(
                model=self._settings.model,
                max_tokens=self._settings.max_tokens,
                system=SYSTEM_PROMPT,
                tools=self._tools,
                thinking={"type": "adaptive"},
                output_config={"effort": self._settings.effort},
                messages=messages,
            )
            self._usage.add(getattr(response, "usage", None))

            # Preserve the assistant turn verbatim (thinking + tool_use blocks)
            # so the conversation stays valid on the next request.
            messages.append({"role": "assistant", "content": response.content})

            tool_uses = [b for b in response.content if getattr(b, "type", None) == "tool_use"]

            if not tool_uses:
                # No tool calls this turn — the model is done with this section.
                if response.stop_reason not in (None, "end_turn"):
                    logger.debug("Stopped with reason: {}", response.stop_reason)
                return

            tool_results: list[dict[str, Any]] = []
            for block in tool_uses:
                result_text, finalized = self._handle_tool_call(
                    block.name, block.input, allow_finalize=allow_finalize
                )
                tool_results.append(
                    {
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": result_text,
                    }
                )
                if finalized:
                    # Acknowledge the call, then stop — analysis is complete.
                    messages.append({"role": "user", "content": tool_results})
                    return

            messages.append({"role": "user", "content": tool_results})

        logger.warning(
            "Tool loop hit max iterations ({}); moving on.",
            self._settings.max_iterations_per_chunk,
        )

    def _handle_tool_call(
        self, name: str, payload: dict[str, Any], *, allow_finalize: bool
    ) -> tuple[str, bool]:
        """Apply one tool call to agent state. Returns (result_text, finalized)."""
        if name == tool_mod.RECORD_CLAUSE:
            try:
                clause = Clause.model_validate(payload)
            except Exception as exc:  # be tolerant of an odd enum/value
                logger.warning("Discarding malformed clause: {}", exc)
                return "Clause rejected: invalid fields.", False
            self._clauses.append(clause)
            logger.info("Clause [{}] {}", clause.category.label, clause.title)
            return "Clause recorded.", False

        if name == tool_mod.FLAG_RISK:
            try:
                risk = Risk.model_validate(payload)
            except Exception as exc:
                logger.warning("Discarding malformed risk: {}", exc)
                return "Risk rejected: invalid fields.", False
            self._risks.append(risk)
            logger.info("Risk [{}] {}", risk.severity.label, risk.title)
            return "Risk recorded.", False

        if name == tool_mod.FINALIZE_ANALYSIS:
            if not allow_finalize:
                logger.warning("Model tried to finalize early; deferring.")
                return (
                    "Not yet — more sections remain. Continue extracting and "
                    "wait until told all sections are provided.",
                    False,
                )
            self._final = payload
            logger.info("Analysis finalized: overall risk {}", payload.get("overall_risk_level"))
            return "Analysis finalized.", True

        logger.warning("Unknown tool call: {}", name)
        return f"Unknown tool: {name}", False

    def _build_report(self, document: ContractDocument) -> ContractReport:
        if self._final is not None:
            overall = self._coerce_risk_level(self._final.get("overall_risk_level"))
            summary = self._final.get("executive_summary") or self._fallback_summary()
        else:
            # Defensive fallback if the model never finalized.
            logger.warning("Model did not finalize; deriving overall assessment.")
            overall = self._derive_overall_risk()
            summary = self._fallback_summary()

        return ContractReport(
            contract_name=document.name,
            page_count=document.page_count,
            model=self._settings.model,
            overall_risk_level=overall,
            executive_summary=summary,
            clauses=list(self._clauses),
            risks=list(self._risks),
            token_usage=self._usage,
        )

    def _derive_overall_risk(self) -> RiskLevel:
        if not self._risks:
            return RiskLevel.LOW
        return max((r.severity for r in self._risks), key=lambda s: s.rank)

    @staticmethod
    def _coerce_risk_level(value: Any) -> RiskLevel:
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
