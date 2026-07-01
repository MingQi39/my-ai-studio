"""
LLM Service
原生 LLM 调用（无工具），用于对比展示
"""
from typing import AsyncIterator, Dict, Any
from datetime import datetime, timezone
import time
from app.travel.services.openai_client import stream_chat
from app.travel.models import ExecutionStats


def utc_now_iso() -> str:
    """返回 UTC 时间的 ISO 8601 格式字符串"""
    return datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')


class LLMService:
    """原生 LLM 服务"""

    def __init__(self, openai_client, model_name: str):
        self.openai_client = openai_client
        self.model_name = model_name
        self.sequence = 0

    async def stream(
        self,
        user_message: str,
        system_prompt: str
    ) -> AsyncIterator[Dict[str, Any]]:
        """
        流式调用 LLM，不使用任何工具
        """
        start_time = time.time()
        stats = ExecutionStats(llm_calls=1)

        # 开始执行
        yield {
            "type": "start",
            "source": "llm",
            "timestamp": utc_now_iso()
        }

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message}
        ]

        # 流式生成
        try:
            async for chunk in stream_chat(self.openai_client, messages, self.model_name):
                self.sequence += 1
                yield {
                    "type": "chunk",
                    "source": "llm",
                    "content": chunk,
                    "sequence": self.sequence,
                    "timestamp": utc_now_iso()
                }
        except Exception as e:
            # LLM 调用失败
            self.sequence += 1
            yield {
                "type": "error",
                "source": "llm",
                "error_type": "llm_api_error",
                "message": f"LLM 调用失败: {str(e)}",
                "recoverable": True,
                "timestamp": utc_now_iso()
            }

        # 计算总耗时
        stats.duration_ms = int((time.time() - start_time) * 1000)

        # 执行完成
        yield {
            "type": "done",
            "source": "llm",
            "stats": stats.dict(),
            "timestamp": utc_now_iso()
        }

    async def stream_with_history(
        self,
        messages: list
    ) -> AsyncIterator[Dict[str, Any]]:
        """
        流式调用 LLM，支持对话历史

        Args:
            messages: 完整的消息历史（包含 system、user、assistant）
        """
        start_time = time.time()
        stats = ExecutionStats(llm_calls=1)

        # 开始执行
        yield {
            "type": "start",
            "timestamp": utc_now_iso()
        }

        # 流式生成
        try:
            async for chunk in stream_chat(self.openai_client, messages, self.model_name):
                self.sequence += 1
                yield {
                    "type": "chunk",
                    "content": chunk,
                    "sequence": self.sequence,
                    "timestamp": utc_now_iso()
                }
        except Exception as e:
            # LLM 调用失败
            self.sequence += 1
            yield {
                "type": "error",
                "error_type": "llm_api_error",
                "message": f"LLM 调用失败: {str(e)}",
                "recoverable": True,
                "timestamp": utc_now_iso()
            }

        # 计算总耗时
        stats.duration_ms = int((time.time() - start_time) * 1000)

        # 执行完成
        yield {
            "type": "done",
            "stats": stats.dict(),
            "timestamp": utc_now_iso()
        }
