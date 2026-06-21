"""The LangGraph supervisor: routes between sub-agents based on pipeline state.

START → supervisor → {prospector, outreach, reply_handler, crm_sync, reporter} → …
each sub-agent returns to the supervisor, which advances to the next stage until the
report is produced, then END. Compiled with a checkpointer so the full pipeline
conversation/state is preserved per ``thread_id`` (LangGraph checkpointing).
"""

from __future__ import annotations

from typing import Any

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph

from sales_ops.state import CRM, OUTREACH, PROSPECT, REPLY, REPORT, SalesState


def route(state: SalesState) -> str:
    """Supervisor routing: pick the next stage from what's already done."""
    if not state.get("prospected"):
        return PROSPECT
    if not state.get("outreached"):
        return OUTREACH
    if not state.get("replies_checked"):
        return REPLY
    if not state.get("crm_synced"):
        return CRM
    if not state.get("reported"):
        return REPORT
    return END


def build_graph(orch: Any):
    """Wire the supervisor + five sub-agent nodes into a compiled, checkpointed graph."""

    def supervisor_node(state: SalesState) -> dict[str, Any]:
        return {"trace": [f"supervisor → {route(state)}"]}

    graph = StateGraph(SalesState)
    graph.add_node("supervisor", supervisor_node)
    graph.add_node(PROSPECT, orch.prospect_node)
    graph.add_node(OUTREACH, orch.outreach_node)
    graph.add_node(REPLY, orch.reply_node)
    graph.add_node(CRM, orch.crm_node)
    graph.add_node(REPORT, orch.report_node)

    graph.add_edge(START, "supervisor")
    graph.add_conditional_edges(
        "supervisor",
        route,
        {PROSPECT: PROSPECT, OUTREACH: OUTREACH, REPLY: REPLY, CRM: CRM, REPORT: REPORT, END: END},
    )
    for node in (PROSPECT, OUTREACH, REPLY, CRM, REPORT):
        graph.add_edge(node, "supervisor")

    return graph.compile(checkpointer=MemorySaver())


__all__ = ["build_graph", "route"]
