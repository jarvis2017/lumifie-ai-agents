"""rag-knowledge-chatbot — answer questions over your documents with citations.

A business uploads documents (PDF, Word, Markdown, text, or URLs); this agent
ingests and chunks them into a persistent Chroma vector store, retrieves the most
relevant passages for a question, and asks the LLM to answer using only that
context — citing exact sources inline as ``[1]``, ``[2]``. Built on
``lumifie_core`` for provider access, logging, and the base agent.
"""

from __future__ import annotations

__version__ = "0.1.0"

__all__ = ["__version__"]
