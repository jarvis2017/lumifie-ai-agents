"""LangGraph state and graph wiring for the lead-research pipeline.

The graph is a linear three-stage pipeline — scrape → match → copywrite — but
modeled as an explicit LangGraph ``StateGraph`` so stages, state, and control flow
are first-class and easy to extend (e.g. conditional edges to skip outreach for
disqualified leads).
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph


class LeadState(TypedDict, total=False):
    """Shared state passed between sub-agents."""

    company_url: str
    icp: dict[str, Any]
    enrichment: dict[str, Any]
    icp_score: dict[str, Any]
    outreach: dict[str, Any]
    # Each node appends sources; operator.add merges the lists.
    sources: Annotated[list[str], operator.add]


def build_graph(agent: Any):
    """Wire the three sub-agent nodes into a compiled LangGraph pipeline."""
    graph = StateGraph(LeadState)
    graph.add_node("scrape", agent.scrape_node)
    graph.add_node("match", agent.match_node)
    graph.add_node("copywrite", agent.copy_node)
    graph.add_edge(START, "scrape")
    graph.add_edge("scrape", "match")
    graph.add_edge("match", "copywrite")
    graph.add_edge("copywrite", END)
    return graph.compile()


__all__ = ["LeadState", "build_graph"]
