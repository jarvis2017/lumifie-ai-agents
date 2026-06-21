"""Helpers for building OpenAI-style chat messages and tool definitions.

litellm speaks the OpenAI chat format across every provider, so all agents build
messages and tools with these helpers regardless of the underlying model.
"""

from __future__ import annotations

import json
from typing import Any

from lumifie_core.provider import CompletionResult


def parse_json(text: str | None) -> dict[str, Any]:
    """Best-effort parse of a JSON object from model text; {} on failure."""
    if not text:
        return {}
    try:
        data = json.loads(text)
    except (json.JSONDecodeError, TypeError):
        return {}
    return data if isinstance(data, dict) else {}


def system(content: str) -> dict[str, Any]:
    return {"role": "system", "content": content}


def user(content: str) -> dict[str, Any]:
    return {"role": "user", "content": content}


def function_tool(name: str, description: str, parameters: dict[str, Any]) -> dict[str, Any]:
    """Build an OpenAI-style function tool definition."""
    return {
        "type": "function",
        "function": {
            "name": name,
            "description": description,
            "parameters": parameters,
        },
    }


def assistant_message(result: CompletionResult) -> dict[str, Any]:
    """Reconstruct the assistant turn (text + tool calls) to append to history."""
    msg: dict[str, Any] = {"role": "assistant", "content": result.text or ""}
    if result.tool_calls:
        msg["tool_calls"] = [
            {
                "id": tc.id,
                "type": "function",
                "function": {"name": tc.name, "arguments": json.dumps(tc.arguments)},
            }
            for tc in result.tool_calls
        ]
    return msg


def tool_result(tool_call_id: str, content: str) -> dict[str, Any]:
    return {"role": "tool", "tool_call_id": tool_call_id, "content": content}


__all__ = [
    "system",
    "user",
    "function_tool",
    "assistant_message",
    "tool_result",
    "parse_json",
]
