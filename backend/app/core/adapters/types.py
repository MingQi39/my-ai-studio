"""
适配器类型定义

定义聊天消息、响应块等类型。
"""

from typing import TypedDict, Literal, Any


class ContentBlock(TypedDict, total=False):
    """内容块（支持多模态）"""
    type: Literal["text", "image_url", "image_base64", "audio"]
    text: str | None
    image_url: str | None
    image_base64: str | None
    mime_type: str | None  # 用于 base64 内容


class ChatMessage(TypedDict, total=False):
    """聊天消息"""
    role: Literal["system", "user", "assistant", "tool"]
    content: str | list[ContentBlock]
    tool_call_id: str | None  # 用于 tool 角色
    tool_calls: list[dict] | None  # 用于 assistant 角色
    name: str | None  # 可选的名称


class ToolCall(TypedDict):
    """工具调用"""
    id: str
    type: Literal["function"]
    function: dict  # {"name": str, "arguments": str}


class ChatCompletionChunk(TypedDict):
    """流式响应块"""
    type: Literal["content", "thinking", "tool_call", "usage", "done", "error"]
    content: str | None
    thinking: str | None
    tool_call: dict | None
    usage: dict | None
    error: str | None


class ModelInfo(TypedDict, total=False):
    """模型信息"""
    id: str
    name: str
    context_length: int
    supports_vision: bool
    supports_tools: bool
    supports_reasoning: bool
    supports_audio: bool


class ChatCompletionResponse(TypedDict, total=False):
    """非流式响应"""
    content: str | None
    reasoning_content: str | None
    tool_calls: list[ToolCall] | None
    usage: dict | None
    model: str | None
    finish_reason: str | None


class UsageInfo(TypedDict, total=False):
    """Token 使用统计"""
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    reasoning_tokens: int | None  # 思考模式特有
