"""
Pydantic 模型定义
定义 SSE 事件、请求/响应模型
"""
from typing import Literal, Optional, Dict, Any
from pydantic import BaseModel
from enum import Enum


class EventType(str, Enum):
    """SSE 事件类型枚举"""
    START = "start"
    DONE = "done"
    CHUNK = "chunk"
    ROUND_START = "round_start"
    ROUND_END = "round_end"
    STEP = "step"
    TOOL_CALL_START = "tool_call_start"
    TOOL_CALL_RESULT = "tool_call_result"
    STATS_UPDATE = "stats_update"
    ERROR = "error"


class StepType(str, Enum):
    """ReAct 步骤类型"""
    OBSERVE = "Observe"
    THINK = "Think"
    ACT = "Act"
    VERIFY = "Verify"


class ExecutionStats(BaseModel):
    """执行统计信息"""
    llm_calls: int = 0
    tool_calls: int = 0
    duration_ms: int = 0
    tokens_used: Optional[int] = None


class SSEEvent(BaseModel):
    """SSE 事件基础模型"""
    type: EventType
    source: Literal["llm", "agent"]
    timestamp: str
    sequence: Optional[int] = None

    # LLM chunk
    content: Optional[str] = None

    # ReAct round
    round: Optional[int] = None

    # ReAct step
    step_type: Optional[StepType] = None

    # Tool call
    tool: Optional[str] = None
    args: Optional[Dict[str, Any]] = None
    result: Optional[str] = None
    ok: Optional[bool] = None
    call_id: Optional[str] = None
    duration_ms: Optional[int] = None

    # Stats
    stats: Optional[ExecutionStats] = None

    # Error
    error_type: Optional[str] = None
    message: Optional[str] = None
    recoverable: Optional[bool] = None
    context: Optional[Dict[str, Any]] = None


# API 请求模型
class CompareRequest(BaseModel):
    """对比 API 请求"""
    message: str
    max_rounds: int = 3


class AgentRequest(BaseModel):
    """Agent API 请求"""
    message: str
    max_rounds: int = 3
    model: Optional[str] = None


class ToolTestRequest(BaseModel):
    """工具测试请求"""
    args: Dict[str, Any]


class SettingsUpdate(BaseModel):
    """配置更新请求"""
    llm_api_key: Optional[str] = None
    llm_base_url: Optional[str] = None
    llm_model: Optional[str] = None
    system_prompt: Optional[str] = None
    max_rounds: Optional[int] = None
