"""Resolve incomplete tool call names from the registry."""

from __future__ import annotations

from app.services.chat_tools.registry import ToolsRegistry


def resolve_tool_calls(tool_calls: list[dict], registry: ToolsRegistry) -> list[dict]:
    """Fill missing function.name using registered tools (common in streamed chunks)."""
    if not tool_calls:
        return tool_calls

    available = registry.tool_names
    sole_tool = available[0] if len(available) == 1 else None

    resolved: list[dict] = []
    for tc in tool_calls:
        item = dict(tc)
        func = dict(item.get("function") or {})
        name = (func.get("name") or "").strip()

        if not name or name == "unknown":
            if sole_tool:
                func["name"] = sole_tool
            elif "web_search" in available:
                func["name"] = "web_search"
            elif available:
                func["name"] = available[0]

        item["function"] = func
        resolved.append(item)

    return resolved
