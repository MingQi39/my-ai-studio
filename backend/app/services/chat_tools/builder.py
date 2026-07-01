"""Build OpenAI tools / response_format from chat tool toggles."""

from __future__ import annotations

from typing import Any

from app.models.schemas import ChatToolsConfig
from app.services.chat_tools.handlers import (
    calculate_handler,
    execute_python_handler,
    get_current_time_handler,
    web_search_handler,
)
from app.services.chat_tools.registry import ToolsRegistry

TOOL_NAME_TO_TYPE = {
    "web_search": "search",
    "execute_python": "code",
    "calculate": "function",
    "get_current_time": "function",
}

STRUCTURED_RESPONSE_SCHEMA: dict[str, Any] = {
    "type": "json_schema",
    "json_schema": {
        "name": "structured_response",
        "strict": True,
        "schema": {
            "type": "object",
            "properties": {
                "answer": {
                    "type": "string",
                    "description": "Main response text for the user",
                },
                "highlights": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Optional bullet-point highlights",
                },
            },
            "required": ["answer"],
            "additionalProperties": False,
        },
    },
}

STRUCTURED_JSON_HINT = (
    'Respond in JSON with shape {"answer": "<main text>", "highlights": ["optional bullets"]}. '
    "The answer field is required."
)

# Providers that only support json_object (not json_schema) for response_format
_JSON_OBJECT_ONLY_PROVIDERS = frozenset({"deepseek"})


def adapt_response_format(
    response_format: dict[str, Any] | None,
    provider: str | None,
) -> dict[str, Any] | None:
    """Map response_format to what the provider supports."""
    if not response_format:
        return None
    if provider in _JSON_OBJECT_ONLY_PROVIDERS and response_format.get("type") == "json_schema":
        return {"type": "json_object"}
    return response_format


def create_chat_tools_registry(config: ChatToolsConfig | None) -> ToolsRegistry:
    """Register handlers for each enabled tool toggle."""
    registry = ToolsRegistry()
    if not config:
        return registry

    if config.search:
        registry.register(
            name="web_search",
            description=(
                "Search the web for up-to-date information. Use when the user asks about "
                "recent events, news, or facts you are unsure about. "
                "For time-sensitive queries (today, latest, scores), include the current "
                "date and year from system context in the search query."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": (
                            "Search query. For 'today' or recent events, include the current "
                            "year and date (see system message), e.g. '2026-06-30 World Cup scores'."
                        ),
                    }
                },
                "required": ["query"],
            },
            handler=web_search_handler,
        )

    if config.code:
        registry.register(
            name="execute_python",
            description="Execute Python code in a sandbox. Use for calculations, data processing, or demonstrations. Only stdlib math/datetime and print are available.",
            parameters={
                "type": "object",
                "properties": {
                    "code": {
                        "type": "string",
                        "description": "Python source code to execute",
                    }
                },
                "required": ["code"],
            },
            handler=execute_python_handler,
        )

    if config.function:
        registry.register(
            name="calculate",
            description="Evaluate a math expression (numbers, + - * / parentheses only).",
            parameters={
                "type": "object",
                "properties": {
                    "expression": {
                        "type": "string",
                        "description": "Math expression, e.g. (100+50)*2",
                    }
                },
                "required": ["expression"],
            },
            handler=calculate_handler,
        )
        registry.register(
            name="get_current_time",
            description="Get the current UTC date and time.",
            parameters={"type": "object", "properties": {}, "required": []},
            handler=get_current_time_handler,
        )

    return registry


def build_tools_and_format(
    config: ChatToolsConfig | None,
) -> tuple[list[dict], dict[str, Any] | None, ToolsRegistry]:
    """Return (openai_tools, response_format, registry)."""
    registry = create_chat_tools_registry(config)
    tools = registry.to_openai_tools()
    response_format = None
    if config and config.structured:
        response_format = STRUCTURED_RESPONSE_SCHEMA
    return tools, response_format, registry


def tool_type_for_name(name: str) -> str:
    return TOOL_NAME_TO_TYPE.get(name, "function")
