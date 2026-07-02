"""
流状态管理器

追踪当前正在进行的 SSE 流式会话，支持刷新后重连。
维护 session_id -> 流状态 的映射，以及对应的消息 ID 和内容缓冲区。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional


@dataclass
class StreamState:
    """流式会话的状态"""
    session_id: str
    message_id: str
    content: str = ""
    thinking: str = ""
    tool_results: list = field(default_factory=list)
    is_active: bool = True
    started_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class StreamStateManager:
    """
    单例流状态管理器

    使用内存字典存储活跃流的运行时状态。
    注意：服务重启后状态会丢失，但用户可以通过历史消息恢复。
    """

    _instance: Optional[StreamStateManager] = None

    def __new__(cls) -> StreamStateManager:
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._streams: dict[str, StreamState] = {}
        return cls._instance

    def register(
        self,
        session_id: str,
        message_id: str,
    ) -> StreamState:
        """注册一个新流"""
        state = StreamState(session_id=session_id, message_id=message_id)
        self._streams[session_id] = state
        return state

    def complete(self, session_id: str) -> None:
        """标记流已完成并注销（保留对象引用供 resume 轮询退出）"""
        state = self._streams.pop(session_id, None)
        if state:
            state.is_active = False

    def unregister(self, session_id: str) -> None:
        """注销一个流"""
        self.complete(session_id)

    def get(self, session_id: str) -> Optional[StreamState]:
        """获取流状态"""
        return self._streams.get(session_id)

    def is_active(self, session_id: str) -> bool:
        """检查 session 是否有活跃的流"""
        state = self._streams.get(session_id)
        return state is not None and state.is_active

    def update_content(self, session_id: str, content: str) -> None:
        """更新内容"""
        state = self._streams.get(session_id)
        if state:
            state.content = content

    def update_thinking(self, session_id: str, thinking: str) -> None:
        """更新思考内容"""
        state = self._streams.get(session_id)
        if state:
            state.thinking = thinking

    def upsert_tool_result(self, session_id: str, tool_result: dict) -> None:
        """追加或更新工具执行状态（按 call_id 匹配）"""
        state = self._streams.get(session_id)
        if not state:
            return

        call_id = tool_result.get("call_id")
        if call_id:
            for index, existing in enumerate(state.tool_results):
                if existing.get("call_id") == call_id:
                    state.tool_results[index] = tool_result
                    return

        state.tool_results.append(tool_result)


# 全局单例
stream_state_manager = StreamStateManager()
