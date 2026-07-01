"""
ReAct Agent 编排器
实现完整的 Observe → Think → Act → Verify 四步循环
"""
from typing import AsyncIterator, Dict, Any, List
import json
import time
import re
from datetime import datetime, timezone

from app.travel.services.tool_registry import ToolsRegistry
from app.travel.models import ExecutionStats


def utc_now_iso() -> str:
    """返回 UTC 时间的 ISO 8601 格式字符串"""
    return datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')


def extract_city_from_message(message: str) -> str:
    """从用户消息中提取城市名称"""
    # 常见城市列表
    cities = [
        "北京", "上海", "杭州", "深圳", "广州", "成都", "西安",
        "南京", "苏州", "重庆", "武汉", "长沙", "厦门", "青岛",
        "大连", "天津", "宁波", "无锡", "郑州", "济南"
    ]

    for city in cities:
        if city in message:
            return city

    # 默认返回杭州
    return "杭州"


REACT_SYSTEM_PROMPT = """你是一个智能旅行规划助手，使用 ReAct（Reasoning + Acting）框架进行决策。

你拥有以下工具：
- get_weather: 查询城市天气
- search_attractions: 搜索城市景点
- search_hotels: 搜索酒店
- search_transport: 查询交通方式
- search_food_recommendations: 搜索当地美食推荐（网页摘要，含小红书参考）
- calculate: 执行数学计算

默认规划要求：
- 每份完整行程必须包含每日用餐/美食安排（午餐、晚餐或特色小吃）
- 第 1 轮 Observe 已自动获取目的地天气与美食参考，请优先采用并写入最终方案

每一轮你需要：
1. 观察环境（已通过工具获取数据）
2. 分析数据并制定策略
3. 如果需要，执行操作（调用工具）
4. 验证操作结果

请用中文回复。思考要简洁但要有逻辑，体现 ReAct 的推理链条。"""


class ReActAgent:
    """ReAct Agent 编排器"""

    def __init__(
        self,
        tools_registry: ToolsRegistry,
        openai_client,
        model_name: str = "gpt-4o-mini"
    ):
        self.tools_registry = tools_registry
        self.openai_client = openai_client
        self.model_name = model_name
        self.sequence = 0
        self.stats = ExecutionStats()

    async def run(
        self,
        user_message: str,
        max_rounds: int = 3,
        conversation_history: List[Dict[str, str]] | None = None,
    ) -> AsyncIterator[Dict[str, Any]]:
        """
        运行 ReAct 循环

        Args:
            user_message: 用户输入
            max_rounds: 最大推理轮次
            conversation_history: 先前对话（不含当前 user 消息）

        Yields:
            SSE 事件字典
        """
        start_time = time.time()
        messages: List[Dict] = [
            {"role": "system", "content": REACT_SYSTEM_PROMPT},
        ]
        if conversation_history:
            for item in conversation_history:
                role = item.get("role")
                content = item.get("content")
                if role in ("user", "assistant") and content:
                    messages.append({"role": role, "content": content})
        messages.append({"role": "user", "content": user_message})

        # 开始执行
        yield self._event("start")

        for round_num in range(1, max_rounds + 1):
            # 轮次开始
            yield self._event("round_start", round=round_num)

            # Step 1: Observe - 自动获取环境数据
            async for event in self._observe_step(round_num, messages, user_message):
                yield event

            # Step 2: Think - LLM 分析 + 决定是否调用工具
            tool_calls = []
            think_completed = False
            async for event in self._think_step(round_num, messages):
                yield event
                if event.get("type") == "step" and event.get("step_type") == "Think":
                    think_completed = True
                elif event.get("type") == "error":
                    # Think 步骤失败，跳过后续步骤
                    break

            # 从 messages 中提取 tool_calls（只有在 Think 成功完成时）
            if think_completed and messages and messages[-1].get("role") == "assistant":
                tool_calls = messages[-1].get("tool_calls", [])

            # Step 3: Act - 执行工具调用
            if tool_calls:
                async for event in self._act_step(round_num, tool_calls, messages):
                    yield event
            else:
                # 无工具调用，说明 Agent 认为任务已完成，智能停止
                self.sequence += 1
                yield self._event(
                    "step",
                    step_type="Act",
                    round=round_num,
                    content=f"本轮分析后认为已掌握足够信息，无需继续调用工具。准备生成最终回复。"
                )

                # 智能停止：提前结束循环
                yield self._event("round_end", round=round_num)
                break

            # Step 4: Verify - 验证结果（只有在 Think 成功时才执行）
            if think_completed:
                async for event in self._verify_step(round_num, messages):
                    yield event

            # 轮次结束
            yield self._event("round_end", round=round_num)

        # 生成最终用户回复
        async for event in self._final_response_step(messages, user_message):
            yield event

        # 计算总耗时
        self.stats.duration_ms = int((time.time() - start_time) * 1000)

        # 执行完成
        yield self._event("done", stats=self.stats.dict())

    async def _observe_step(
        self,
        round_num: int,
        messages: List[Dict],
        user_message: str
    ) -> AsyncIterator[Dict[str, Any]]:
        """Observe 步骤：自动获取环境数据（天气；首轮另含美食推荐）"""
        city = extract_city_from_message(user_message)
        observe_parts: list[str] = []

        weather_result = await self.tools_registry.execute(
            "get_weather",
            {"city": city},
        )
        observe_parts.append(f"[天气] {city}\n{weather_result}")

        if round_num == 1:
            food_args = {"city": city}
            call_id = f"observe-food-{round_num}"
            self.sequence += 1
            yield self._event(
                "tool_call_start",
                tool_name="search_food_recommendations",
                tool_args=food_args,
                call_id=call_id,
            )

            tool_start = time.time()
            try:
                food_result = await self.tools_registry.execute(
                    "search_food_recommendations",
                    food_args,
                )
                status = "success"
                error_msg = None
                self.stats.tool_calls += 1
            except Exception as e:
                food_result = json.dumps({"error": str(e)}, ensure_ascii=False)
                status = "error"
                error_msg = str(e)

            self.sequence += 1
            yield self._event(
                "tool_call_result",
                tool_name="search_food_recommendations",
                result=food_result,
                status=status,
                duration_ms=int((time.time() - tool_start) * 1000),
                call_id=call_id,
                error=error_msg,
            )
            observe_parts.append(f"[美食推荐] {city}\n{food_result}")

        observe_content = "[环境观察]\n" + "\n\n".join(observe_parts)
        self.sequence += 1
        yield self._event(
            "step",
            step_type="Observe",
            round=round_num,
            content=observe_content,
        )

        messages.append({
            "role": "user",
            "content": (
                f"[第{round_num}轮] 当前环境数据：\n"
                f"{observe_content}\n\n"
                "请基于以上数据规划完整行程，必须包含每日用餐/美食安排。"
                "分析当前情况并决定是否还需要调用其他工具。"
            ),
        })

    async def _think_step(
        self,
        round_num: int,
        messages: List[Dict]
    ) -> AsyncIterator[Dict[str, Any]]:
        """Think 步骤：LLM 分析 + Function Calling"""
        self.stats.llm_calls += 1

        try:
            response = await self.openai_client.chat.completions.create(
                model=self.model_name,
                messages=messages,
                tools=self.tools_registry.to_openai_tools(),
                tool_choice="auto"
            )
        except Exception as e:
            # LLM 调用失败
            self.sequence += 1
            yield self._event(
                "error",
                error_type="llm_api_error",
                message=f"LLM 调用失败: {str(e)}",
                recoverable=True
            )
            return

        msg = response.choices[0].message
        think_content = msg.content or "（Agent 选择直接调用工具，无文字分析）"

        self.sequence += 1
        yield self._event(
            "step",
            step_type="Think",
            round=round_num,
            content=think_content
        )

        # 将 Think 回复加入对话历史
        assistant_msg: Dict = {
            "role": "assistant",
            "content": think_content
        }
        if msg.tool_calls:
            assistant_msg["tool_calls"] = [
                {
                    "id": tc.id,
                    "type": "function",
                    "function": {
                        "name": tc.function.name,
                        "arguments": tc.function.arguments
                    }
                }
                for tc in msg.tool_calls
            ]
        messages.append(assistant_msg)

    async def _act_step(
        self,
        round_num: int,
        tool_calls: List[Dict],
        messages: List[Dict]
    ) -> AsyncIterator[Dict[str, Any]]:
        """Act 步骤：执行工具调用"""
        act_parts = []

        for tc in tool_calls:
            call_id = tc["id"]
            fn_name = tc["function"]["name"]

            try:
                fn_args = json.loads(tc["function"]["arguments"]) if tc["function"]["arguments"] else {}
            except json.JSONDecodeError:
                fn_args = {}

            # 发送工具调用开始事件
            self.sequence += 1
            yield self._event(
                "tool_call_start",
                tool_name=fn_name,
                tool_args=fn_args,
                call_id=call_id
            )

            # 执行工具
            tool_start = time.time()
            try:
                result = await self.tools_registry.execute(fn_name, fn_args)
                status = "success"
                error_msg = None
                self.stats.tool_calls += 1
            except Exception as e:
                result = json.dumps({"error": str(e)}, ensure_ascii=False)
                status = "error"
                error_msg = str(e)

            tool_duration = int((time.time() - tool_start) * 1000)

            # 发送工具调用结果事件
            self.sequence += 1
            yield self._event(
                "tool_call_result",
                tool_name=fn_name,
                result=result,
                status=status,
                duration_ms=tool_duration,
                call_id=call_id,
                error=error_msg
            )

            # 将工具结果加入对话历史
            messages.append({
                "role": "tool",
                "tool_call_id": call_id,
                "content": result
            })

            # 记录到 act_parts 用于汇总
            act_parts.append(f"调用 {fn_name}({json.dumps(fn_args, ensure_ascii=False)}) → {result[:100]}")

        # 发送 Act 步骤汇总
        self.sequence += 1
        yield self._event(
            "step",
            step_type="Act",
            round=round_num,
            content=f"执行了 {len(tool_calls)} 个工具调用：\n" + "\n".join(act_parts)
        )

    async def _verify_step(
        self,
        round_num: int,
        messages: List[Dict]
    ) -> AsyncIterator[Dict[str, Any]]:
        """Verify 步骤：验证工具调用结果"""
        self.stats.llm_calls += 1

        # 添加验证提示
        messages.append({
            "role": "user",
            "content": "请验证上述工具调用的结果是否符合预期，并总结本轮的收获。"
        })

        try:
            response = await self.openai_client.chat.completions.create(
                model=self.model_name,
                messages=messages
            )
        except Exception as e:
            self.sequence += 1
            yield self._event(
                "error",
                error_type="llm_api_error",
                message=f"Verify 阶段 LLM 调用失败: {str(e)}",
                recoverable=True
            )
            return

        verify_content = response.choices[0].message.content or "（验证完成）"

        self.sequence += 1
        yield self._event(
            "step",
            step_type="Verify",
            round=round_num,
            content=verify_content
        )

        # 将验证结果加入对话历史
        messages.append({
            "role": "assistant",
            "content": verify_content
        })

    async def _final_response_step(
        self,
        messages: List[Dict],
        user_message: str
    ) -> AsyncIterator[Dict[str, Any]]:
        """生成最终用户回复"""
        self.stats.llm_calls += 1

        # 添加最终回复提示
        messages.append({
            "role": "user",
            "content": (
                f"基于以上所有分析和数据，请用简洁友好的语言回答用户的问题：{user_message}\n\n"
                "要求：\n"
                "1. 直接给出完整旅行建议（是否适合出行、每日景点/酒店/交通、注意事项）\n"
                "2. 必须包含每日用餐或美食推荐（午餐、晚餐或特色小吃），优先引用已获取的美食参考\n"
                "3. 用清晰段落总结，不要重复前面的分析过程\n"
                "4. 语气要友好自然，像朋友聊天一样"
            )
        })

        try:
            response = await self.openai_client.chat.completions.create(
                model=self.model_name,
                messages=messages
            )
        except Exception as e:
            self.sequence += 1
            yield self._event(
                "error",
                error_type="llm_api_error",
                message=f"最终回复生成失败: {str(e)}",
                recoverable=True
            )
            return

        final_content = response.choices[0].message.content or "已完成分析"

        self.sequence += 1
        yield self._event(
            "final_response",
            content=final_content
        )

        # 将最终回复加入对话历史
        messages.append({
            "role": "assistant",
            "content": final_content
        })

    def _event(self, event_type: str, **kwargs) -> Dict[str, Any]:
        """构造 SSE 事件"""
        event = {
            "type": event_type,
            "source": "agent",
            "timestamp": utc_now_iso(),
            "sequence": self.sequence
        }
        event.update(kwargs)
        return event
