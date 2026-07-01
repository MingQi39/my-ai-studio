"""
流式响应工具

提供 SSE 格式化和流式内容缓冲。
"""

import json
from typing import Any

from .adapters.types import ChatCompletionChunk
from .exceptions import LLMException


class SSEFormatter:
    """SSE (Server-Sent Events) 格式化器"""

    @staticmethod
    def format_chunk(chunk: ChatCompletionChunk) -> str:
        """格式化响应块为 SSE 格式

        Args:
            chunk: 响应块

        Returns:
            SSE 格式字符串
        """
        data = {
            "type": chunk["type"],
        }

        if chunk["type"] == "content" and chunk.get("content"):
            data["content"] = chunk["content"]
        elif chunk["type"] == "thinking" and chunk.get("thinking"):
            thinking = chunk["thinking"]
            # Handle case where thinking might be a list, dict, or other object
            if isinstance(thinking, str):
                data["thinking"] = thinking
            elif isinstance(thinking, list):
                # Flatten list to string
                parts = []
                for item in thinking:
                    if isinstance(item, dict):
                        parts.append(item.get('text', '') or item.get('content', '') or str(item))
                    else:
                        parts.append(str(item))
                data["thinking"] = "".join(parts)
            elif isinstance(thinking, dict):
                # Extract text from dict
                data["thinking"] = thinking.get('text', '') or thinking.get('content', '') or str(thinking)
            else:
                data["thinking"] = str(thinking)
        elif chunk["type"] == "tool_call" and chunk.get("tool_call"):
            data["tool_call"] = chunk["tool_call"]
        elif chunk["type"] == "usage" and chunk.get("usage"):
            data["usage"] = chunk["usage"]
        elif chunk["type"] == "error" and chunk.get("error"):
            data["error"] = chunk["error"]

        return f"data: {json.dumps(data, ensure_ascii=False)}\n\n"

    @staticmethod
    def format_error(error: LLMException) -> str:
        """格式化错误为 SSE 格式

        Args:
            error: LLM 异常

        Returns:
            SSE 格式字符串
        """
        data = {
            "type": "error",
            "error": {
                "code": error.error_code,
                "message": error.message,
                "details": error.details,
            }
        }
        return f"data: {json.dumps(data, ensure_ascii=False)}\n\n"

    @staticmethod
    def format_done(usage: dict | None = None) -> str:
        """格式化完成信号为 SSE 格式

        Args:
            usage: Token 使用统计

        Returns:
            SSE 格式字符串
        """
        data: dict[str, Any] = {"type": "done"}
        if usage:
            data["usage"] = usage
        return f"data: {json.dumps(data, ensure_ascii=False)}\n\ndata: [DONE]\n\n"


class StreamBuffer:
    """流式内容缓冲器

    用于聚合流式响应的内容。
    """

    def __init__(self):
        self._content_parts: list[str] = []
        self._thinking_parts: list[str] = []
        self._tool_calls: list[dict] = []
        self._usage: dict | None = None
        self._error: str | None = None

    def append(self, chunk: ChatCompletionChunk) -> None:
        """添加内容块

        Args:
            chunk: 响应块
        """
        chunk_type = chunk["type"]

        if chunk_type == "content" and chunk.get("content"):
            self._content_parts.append(chunk["content"])
        elif chunk_type == "thinking" and chunk.get("thinking"):
            thinking = chunk["thinking"]
            # Handle case where thinking might be a list, dict, or other object
            if isinstance(thinking, str):
                self._thinking_parts.append(thinking)
            elif isinstance(thinking, list):
                # Flatten list to string - each item might be a dict with 'text' key or just a string
                for item in thinking:
                    if isinstance(item, dict):
                        self._thinking_parts.append(item.get('text', '') or item.get('content', '') or str(item))
                    else:
                        self._thinking_parts.append(str(item))
            elif isinstance(thinking, dict):
                # Extract text from dict
                self._thinking_parts.append(thinking.get('text', '') or thinking.get('content', '') or str(thinking))
            else:
                self._thinking_parts.append(str(thinking))
        elif chunk_type == "tool_call" and chunk.get("tool_call"):
            self._merge_tool_call(chunk["tool_call"])
        elif chunk_type == "usage" and chunk.get("usage"):
            self._usage = chunk["usage"]
        elif chunk_type == "error" and chunk.get("error"):
            self._error = chunk["error"]

    def _merge_tool_call(self, tool_call: dict) -> None:
        """合并工具调用（流式分片按 index 聚合，避免 null id 误合并）"""
        tool_call = dict(tool_call)
        index = tool_call.get("index", len(self._tool_calls))

        existing = None
        for tc in self._tool_calls:
            if tc.get("index") == index:
                existing = tc
                break

        incoming_func = tool_call.get("function") or {}
        if not isinstance(incoming_func, dict):
            incoming_func = dict(incoming_func) if hasattr(incoming_func, "items") else {}

        if existing is None:
            new_tc: dict = {
                "index": index,
                "id": tool_call.get("id"),
                "type": tool_call.get("type") or "function",
                "function": {},
            }
            if incoming_func.get("name"):
                new_tc["function"]["name"] = incoming_func["name"]
            if incoming_func.get("arguments"):
                new_tc["function"]["arguments"] = incoming_func["arguments"]
            self._tool_calls.append(new_tc)
            return

        if tool_call.get("id") and not existing.get("id"):
            existing["id"] = tool_call["id"]

        if "function" not in existing:
            existing["function"] = {}
        if incoming_func.get("name"):
            existing["function"]["name"] = incoming_func["name"]
        if incoming_func.get("arguments"):
            existing["function"]["arguments"] = (
                existing["function"].get("arguments", "") + incoming_func["arguments"]
            )

    def get_content(self) -> str:
        """获取聚合的文本内容

        Returns:
            聚合后的文本
        """
        return "".join(self._content_parts)

    def get_thinking(self) -> str:
        """获取聚合的思考内容

        Returns:
            聚合后的思考内容
        """
        return "".join(self._thinking_parts)

    def get_tool_calls(self) -> list[dict]:
        """获取工具调用列表

        Returns:
            工具调用列表
        """
        return self._tool_calls

    def get_usage(self) -> dict | None:
        """获取 Token 使用统计

        Returns:
            使用统计或 None
        """
        return self._usage

    def get_error(self) -> str | None:
        """获取错误信息

        Returns:
            错误信息或 None
        """
        return self._error

    def has_content(self) -> bool:
        """是否有文本内容"""
        return len(self._content_parts) > 0

    def has_thinking(self) -> bool:
        """是否有思考内容"""
        return len(self._thinking_parts) > 0

    def has_tool_calls(self) -> bool:
        """是否有工具调用"""
        return len(self._tool_calls) > 0

    def clear(self) -> None:
        """清空缓冲区"""
        self._content_parts.clear()
        self._thinking_parts.clear()
        self._tool_calls.clear()
        self._usage = None
        self._error = None

    def to_dict(self) -> dict:
        """转换为字典

        Returns:
            包含所有聚合内容的字典
        """
        return {
            "content": self.get_content(),
            "thinking": self.get_thinking(),
            "tool_calls": self.get_tool_calls(),
            "usage": self.get_usage(),
            "error": self.get_error(),
        }
