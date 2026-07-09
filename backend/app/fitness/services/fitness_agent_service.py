"""LangChain-based Fitness Agent tool-calling runner (v1).

This module focuses on:
- defining LangChain tools wrapping our calorie/diary services
- driving a minimal tool-calling loop (tool_call_start/tool_call_result)
- converting the tool/response process into Fitness SSE events (dicts)

The Fitness API layer will be responsible for persistence using
`app.fitness.services.chat_persistence`.
"""

from __future__ import annotations

import asyncio
import json
import time
import uuid
from typing import Any, AsyncIterator, Awaitable, Callable

from app.fitness.schemas import (
    FoodItemInput,
    FitnessGoalUpdate,
    Preference,
)
from app.fitness.services.calorie_resolver import ProgressCallback, resolve_food_calories
from app.fitness.services.fitness_intents import (
    detect_meal_type,
    extract_goal_kcal,
    is_low_signal_message,
    is_goal_update_request,
    is_meal_log_request,
    is_recommendation_request,
)
from app.fitness.services.meal_parser import extract_foods_heuristic, parse_meal_foods_from_message
from app.fitness.services.fitness_service import FitnessService
from app.fitness.services.hitl import (
    build_approval_preview,
    build_approval_prompt,
    is_write_tool,
)
from app.fitness.services.recommendation_service import recommend_meals_local


FITNESS_SYSTEM_PROMPT = (
    "你是 Qi 的 Fitness Agent。\n"
    "你的能力：根据用户输入的食物名称/分量进行热量估算与记账；查询今日目标/已摄入/剩余；"
    "按用户约束给出 2-3 个推荐候选，并在用户确认后写入日记。\n\n"
    "合规口径：你提供的是生活方式记录与热量估算，不是医疗建议或诊断。"
    "如果用户提出医疗诊断/处方/极端诱导节食，需简短拒答并引导关注专业健康咨询。\n\n"
    "工具使用规则（必须遵守）：\n"
    "- 涉及今日目标、已摄入、剩余、餐次记录时，优先调用 `get_today_summary`，禁止编造「没有记录」。\n"
    "- 用户明确要求修改每日热量目标时，必须调用 `set_daily_calorie_goal` 后再回复。\n"
    "- 用户要求推荐吃什么时，先 `get_today_summary` 获取剩余热量，再调用 `recommend_meals`。\n"
    "- 用户描述吃了什么、要记账时，先 `resolve_food_calories` 估算，再调用 `log_meal` 触发确认入账。\n"
    "- 写入类工具（log_meal / set_daily_calorie_goal / delete_diary_entry）会暂停并等待用户在界面确认；"
    "在用户确认前，禁止声称已写入、已更新目标或已删除记录。\n"
    "- `estimate` 来源必须被显式标记为估算（source=estimate）。\n"
    "- `resolve_food_calories` 对 local/USDA 接口返回的热量会做合理性校验，明显偏差时会自动修正。\n"
    "- 若本轮未成功调用写入工具，不得使用「已记录/已写入/已更新/已删除/已确认摄入」等完成态表述。\n"
    "- 系统消息中的「用户当前数据」仅供参考；任何写入/修改仍须调用对应工具。\n"
)


class FitnessAgentRuntimeError(RuntimeError):
    pass


def _json_dumps_safe(obj: Any) -> str:
    try:
        return json.dumps(obj, ensure_ascii=False, default=str)
    except TypeError:
        return str(obj)


async def _build_system_prompt(
    *,
    fitness_service: FitnessService,
    user_id: Any,
    user_timezone: str | None,
) -> str:
    summary = await fitness_service.get_today_summary(
        user_id=user_id,
        timezone_name=user_timezone,
    )
    summary_json = _json_dumps_safe(summary.model_dump())
    return (
        f"{FITNESS_SYSTEM_PROMPT}\n"
        "## 用户当前数据（实时快照）\n"
        f"```json\n{summary_json}\n```"
    )


def _tool_call_id() -> str:
    return f"call_{uuid.uuid4().hex[:12]}"


def _tool_progress_event(
    *,
    call_id: str,
    tool_name: str,
    stage: str,
    detail: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "type": "tool_progress",
        "source": "agent",
        "call_id": call_id,
        "tool_name": tool_name,
        "stage": stage,
        **(detail or {}),
    }


async def _stream_tool_progress(
    queue: asyncio.Queue[dict[str, Any] | None],
    *,
    call_id: str,
    tool_name: str,
) -> AsyncIterator[dict[str, Any]]:
    while True:
        item = await queue.get()
        if item is None:
            break
        yield _tool_progress_event(
            call_id=call_id,
            tool_name=tool_name,
            stage=str(item.get("stage") or "working"),
            detail={k: v for k, v in item.items() if k != "stage"},
        )


async def _invoke_with_tool_progress(
    *,
    call_id: str,
    tool_name: str,
    invoke: Callable[[ProgressCallback | None], Awaitable[Any]],
) -> AsyncIterator[tuple[dict[str, Any], Any | None]]:
    queue: asyncio.Queue[dict[str, Any] | None] = asyncio.Queue()

    async def on_progress(stage: str, detail: dict[str, Any] | None = None) -> None:
        await queue.put({"stage": stage, **(detail or {})})

    async def runner() -> Any:
        try:
            return await invoke(on_progress)
        finally:
            await queue.put(None)

    task = asyncio.create_task(runner())

    async for event in _stream_tool_progress(queue, call_id=call_id, tool_name=tool_name):
        yield (event, None)

    result = await task
    yield ({}, result)


def _tool_supports_progress(tool_name: str) -> bool:
    return tool_name == "resolve_food_calories"


async def _yield_write_tool_approval(
    *,
    tool_name: str,
    tool_args: dict[str, Any],
    preview: dict[str, Any],
    call_id: str | None = None,
) -> AsyncIterator[dict[str, Any]]:
    cid = call_id or _tool_call_id()
    yield {
        "type": "tool_call_start",
        "source": "agent",
        "call_id": cid,
        "tool_name": tool_name,
        "tool_args": tool_args,
    }
    yield {
        "type": "approval_required",
        "source": "agent",
        "call_id": cid,
        "tool_name": tool_name,
        "tool_args": tool_args,
        "preview": preview,
    }
    yield {
        "type": "tool_call_result",
        "source": "agent",
        "call_id": cid,
        "result": None,
        "status": "pending_approval",
    }


async def _finish_with_approval_prompt(
    *,
    tool_name: str,
    preview: dict[str, Any],
) -> AsyncIterator[dict[str, Any]]:
    content = build_approval_prompt(tool_name, preview)
    yield {"type": "chunk", "source": "agent", "content": content}
    yield {"type": "final_response", "source": "agent", "content": content}
    yield {"type": "done", "source": "agent"}


def _resolved_list_to_log_items(resolved: list[dict[str, Any]]) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for entry in resolved:
        if not isinstance(entry, dict):
            continue
        items.append(
            {
                "name": entry.get("name"),
                "qty": entry.get("qty"),
                "unit": entry.get("unit"),
                "kcal": entry.get("kcal"),
                "source": entry.get("source"),
            }
        )
    return items


async def _emit_meal_log_approval(
    *,
    meal_type: str,
    items: list[dict[str, Any]],
    call_id: str | None = None,
) -> AsyncIterator[dict[str, Any]]:
    if not items:
        return
    tool_args = {"meal_type": meal_type, "items": items}
    preview = build_approval_preview("log_meal", tool_args)
    async for event in _yield_write_tool_approval(
        tool_name="log_meal",
        tool_args=tool_args,
        preview=preview,
        call_id=call_id,
    ):
        yield event
    async for event in _finish_with_approval_prompt(tool_name="log_meal", preview=preview):
        yield event


async def _try_direct_meal_log(
    *,
    message: str,
    openai_client: Any,
    model_name: str,
) -> AsyncIterator[dict[str, Any]]:
    if not is_meal_log_request(message):
        return

    meal_type = detect_meal_type(message, default="lunch")
    foods = await parse_meal_foods_from_message(
        message,
        openai_client=openai_client,
        model_name=model_name,
    )
    if not foods:
        foods = extract_foods_heuristic(message)
    if not foods:
        stripped = message.strip()
        if stripped:
            foods = [FoodItemInput(name=stripped[:80], qty=1.0, unit="份")]
    if not foods:
        return

    food_args = [f.model_dump() for f in foods]
    resolved_payload: list[dict[str, Any]] | None = None

    async def _execute_resolve(on_progress: ProgressCallback | None = None):
        result = await resolve_food_calories(
            foods,
            openai_client=openai_client,
            model_name=model_name,
            on_progress=on_progress,
        )
        return [r.model_dump(mode="json") for r in result]

    async for event, payload in _yield_tool_execution(
        tool_name="resolve_food_calories",
        tool_args={"foods": food_args},
        executor=_execute_resolve,
        supports_progress=True,
    ):
        if event["type"] == "tool_call_result" and event.get("status") == "success":
            resolved_payload = payload if isinstance(payload, list) else None
        yield event

    if not resolved_payload:
        return

    items = _resolved_list_to_log_items(resolved_payload)
    async for event in _emit_meal_log_approval(meal_type=meal_type, items=items):
        yield event


async def _yield_tool_execution(
    *,
    tool_name: str,
    tool_args: dict[str, Any],
    executor: Callable[..., Awaitable[Any]],
    supports_progress: bool = False,
) -> AsyncIterator[tuple[dict[str, Any], Any | None]]:
    call_id = _tool_call_id()
    yield (
        {
            "type": "tool_call_start",
            "source": "agent",
            "call_id": call_id,
            "tool_name": tool_name,
            "tool_args": tool_args,
        },
        None,
    )

    start = time.time()
    try:
        if supports_progress and _tool_supports_progress(tool_name):
            result: Any = None
            async for event, payload in _invoke_with_tool_progress(
                call_id=call_id,
                tool_name=tool_name,
                invoke=executor,
            ):
                if event:
                    yield (event, None)
                else:
                    result = payload
        else:
            result = await executor()

        duration_ms = int((time.time() - start) * 1000)
        if isinstance(result, list):
            result_payload = [
                item.model_dump(mode="json") if hasattr(item, "model_dump") else item
                for item in result
            ]
        elif hasattr(result, "model_dump"):
            result_payload = result.model_dump(mode="json")
        else:
            result_payload = result
        yield (
            {
                "type": "tool_call_result",
                "source": "agent",
                "call_id": call_id,
                "result": result_payload,
                "status": "success",
                "duration_ms": duration_ms,
            },
            result_payload,
        )
    except Exception as exc:
        duration_ms = int((time.time() - start) * 1000)
        yield (
            {
                "type": "tool_call_result",
                "source": "agent",
                "call_id": call_id,
                "result": None,
                "status": "error",
                "error": str(exc),
                "duration_ms": duration_ms,
            },
            None,
        )


async def _try_direct_goal_update(
    *,
    message: str,
    fitness_service: FitnessService,
    user_id: Any,
) -> AsyncIterator[dict[str, Any]]:
    if not is_goal_update_request(message):
        return

    goal_kcal = extract_goal_kcal(message)
    if goal_kcal is None:
        return

    previous = await fitness_service.get_goal(user_id)
    tool_args = {"daily_calorie_goal": goal_kcal}
    preview = build_approval_preview(
        "set_daily_calorie_goal",
        tool_args,
        previous_goal=previous.daily_calorie_goal,
    )

    async for event in _yield_write_tool_approval(
        tool_name="set_daily_calorie_goal",
        tool_args=tool_args,
        preview=preview,
    ):
        yield event

    async for event in _finish_with_approval_prompt(
        tool_name="set_daily_calorie_goal",
        preview=preview,
    ):
        yield event


async def _try_direct_recommendation(
    *,
    message: str,
    fitness_service: FitnessService,
    user_id: Any,
    user_timezone: str | None,
) -> AsyncIterator[dict[str, Any]]:
    if not is_recommendation_request(message):
        return

    summary_payload: dict[str, Any] | None = None

    async def _execute_summary():
        return await fitness_service.get_today_summary(
            user_id=user_id,
            timezone_name=user_timezone,
        )

    async for event, payload in _yield_tool_execution(
        tool_name="get_today_summary",
        tool_args={},
        executor=_execute_summary,
    ):
        if event["type"] == "tool_call_result" and event.get("status") == "success":
            summary_payload = payload
        yield event

    if not summary_payload:
        return

    meal_type = detect_meal_type(message)
    remaining_kcal = float(summary_payload.get("remaining_kcal") or 0)
    budget_kcal = max(remaining_kcal, 0) or float(summary_payload.get("daily_calorie_goal") or 1800)
    recommend_args = {
        "meal_type": meal_type,
        "target_kcal": budget_kcal,
        "budget_kcal": budget_kcal,
        "preferences": None,
    }

    recommendations: list[dict[str, Any]] = []

    async def _execute_recommend():
        return recommend_meals_local(
            meal_type=meal_type,
            target_kcal=budget_kcal,
            budget_kcal=budget_kcal,
            preferences=None,
        )

    async for event, payload in _yield_tool_execution(
        tool_name="recommend_meals",
        tool_args=recommend_args,
        executor=_execute_recommend,
    ):
        if event["type"] == "tool_call_result" and event.get("status") == "success":
            event["result"] = {"recommendations": payload or []}
            recommendations = [item for item in (payload or [])]
        yield event

    if not recommendations:
        return

    yield {
        "type": "recommendations",
        "source": "agent",
        "recommendations": recommendations,
    }

    meal_label = {
        "breakfast": "早餐",
        "lunch": "午餐",
        "dinner": "晚餐",
        "snack": "加餐",
    }.get(meal_type, "餐食")

    lines = [
        f"根据您今日剩余 **{int(budget_kcal)} kcal**，为您准备了 {len(recommendations)} 套{meal_label}推荐：",
    ]
    for idx, rec in enumerate(recommendations, start=1):
        total = rec.get("total_kcal")
        title = rec.get("title") or f"方案 {idx}"
        lines.append(f"{idx}. **{title}**（约 {int(total or 0)} kcal）")
        for item in rec.get("items") or []:
            lines.append(f"   - {item.get('name')}（约 {int(item.get('kcal') or 0)} kcal）")
    lines.append("如需入账，请告诉我选择第几套。")
    content = "\n".join(lines)

    yield {"type": "chunk", "source": "agent", "content": content}
    yield {"type": "final_response", "source": "agent", "content": content}
    yield {"type": "done", "source": "agent"}


def _contains_write_claim(text: Any) -> bool:
    if isinstance(text, list):
        msg = " ".join(str(item) for item in text).strip()
    else:
        msg = str(text or "").strip()
    if not msg:
        return False
    claim_phrases = (
        "已记录",
        "已写入",
        "已更新",
        "已删除",
        "已确认摄入",
        "已记入",
    )
    return any(phrase in msg for phrase in claim_phrases)


def _build_safe_non_write_reply() -> str:
    return (
        "我还没有执行写入操作。若要记入日记，请直接回复“确认”。\n"
        "如果不记录，请回复“取消”或继续告诉我你想调整的食物/份量。"
    )


async def fitness_agent_stream(
    *,
    message: str,
    conversation_history: list[dict[str, str]],
    max_rounds: int,
    user_timezone: str | None,
    user_id: Any,
    openai_client: Any,
    llm_api_key: str,
    llm_base_url: str,
    model_name: str,
    fitness_service: FitnessService,
) -> AsyncIterator[dict[str, Any]]:
    """
    Yields SSE-compatible event dicts.

    Event types (subset):
    - start
    - tool_call_start / tool_call_result
    - chunk
    - final_response
    - error
    - done
    """

    yield {"type": "start", "source": "agent"}

    if is_goal_update_request(message):
        async for event in _try_direct_goal_update(
            message=message,
            fitness_service=fitness_service,
            user_id=user_id,
        ):
            yield event
        return

    if is_meal_log_request(message):
        meal_log_handled = False
        async for event in _try_direct_meal_log(
            message=message,
            openai_client=openai_client,
            model_name=model_name,
        ):
            meal_log_handled = True
            yield event
        if meal_log_handled:
            return

    if is_recommendation_request(message):
        async for event in _try_direct_recommendation(
            message=message,
            fitness_service=fitness_service,
            user_id=user_id,
            user_timezone=user_timezone,
        ):
            yield event
        return

    if is_low_signal_message(message):
        content = "收到。若要继续记账，请说清楚食物和份量（例如：晚餐吃了牛排 100克）。"
        yield {"type": "chunk", "source": "agent", "content": content}
        yield {"type": "final_response", "source": "agent", "content": content}
        yield {"type": "done", "source": "agent"}
        return

    try:
        from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
        from langchain_core.tools import StructuredTool
        from langchain_openai import ChatOpenAI
    except ImportError as exc:
        raise FitnessAgentRuntimeError(
            "LangChain 依赖未安装。请在后端 requirements 中加入 langchain / langchain-openai 后重装依赖。"
        ) from exc

    # Tools ------------------------------------------------------------
    async def tool_resolve_food_calories(foods: list[FoodItemInput]) -> list[dict[str, Any]]:
        resolved = await resolve_food_calories(
            foods,
            openai_client=openai_client,
            model_name=model_name,
        )
        return [r.model_dump(mode="json") for r in resolved]

    async def tool_get_today_summary() -> dict[str, Any]:
        summary = await fitness_service.get_today_summary(
            user_id=user_id,
            timezone_name=user_timezone,
        )
        return summary.model_dump(mode="json")

    async def tool_set_daily_calorie_goal(update: FitnessGoalUpdate) -> dict[str, Any]:
        updated = await fitness_service.set_goal(
            user_id=user_id,
            daily_calorie_goal=update.daily_calorie_goal,
        )
        return updated.model_dump(mode="json")

    async def tool_log_meal(
        meal_type: str,
        items: list[dict[str, Any]],
        note: str | None = None,
    ) -> dict[str, Any]:
        entry = await fitness_service.log_meal(
            user_id=user_id,
            meal_type=meal_type,
            items=items,
            note=note,
            timezone_name=user_timezone,
        )
        return entry.model_dump(mode="json")

    async def tool_delete_diary_entry(entry_id: str) -> dict[str, Any]:
        ok = await fitness_service.delete_entry(user_id=user_id, entry_id=entry_id)
        return {"ok": ok}

    async def tool_recommend_meals(
        meal_type: str,
        target_kcal: float,
        budget_kcal: float | None = None,
        preferences: list[Preference] | None = None,
    ) -> dict[str, Any]:
        recs = recommend_meals_local(
            meal_type=meal_type,
            target_kcal=target_kcal,
            budget_kcal=budget_kcal,
            preferences=preferences,
        )
        return {"recommendations": [r.model_dump(mode="json") for r in recs]}

    # Create StructuredTools ------------------------------------------
    resolve_tool = StructuredTool.from_function(
        name="resolve_food_calories",
        description="解析食物并返回热量与 source(local/usda/web/estimate)。不落库。",
        func=tool_resolve_food_calories,
    )
    get_summary_tool = StructuredTool.from_function(
        name="get_today_summary",
        description="读取今日目标、已摄入、剩余以及今日餐次列表。",
        func=tool_get_today_summary,
    )
    set_goal_tool = StructuredTool.from_function(
        name="set_daily_calorie_goal",
        description="设置/更新每日热量目标（kcal）。",
        func=tool_set_daily_calorie_goal,
    )
    log_meal_tool = StructuredTool.from_function(
        name="log_meal",
        description="写入日记：把用户确认后的餐次记录到今日 diary（默认不自动触发）。",
        func=tool_log_meal,
    )
    delete_entry_tool = StructuredTool.from_function(
        name="delete_diary_entry",
        description="删除或撤销某条日记记录（由 entry_id 指定）。",
        func=tool_delete_diary_entry,
    )
    recommend_tool = StructuredTool.from_function(
        name="recommend_meals",
        description="根据剩余/预算与简单偏好生成 2-3 套推荐候选。默认不落库。",
        func=tool_recommend_meals,
    )

    tools = [
        resolve_tool,
        get_summary_tool,
        set_goal_tool,
        log_meal_tool,
        delete_entry_tool,
        recommend_tool,
    ]

    # LLM --------------------------------------------------------------
    # We assume `openai_client` is already OpenAI-compatible; langchain-openai
    # config must be provided separately. We use openai_client's base_url and api_key
    # if available, otherwise rely on env/implicit config.
    llm = ChatOpenAI(
        api_key=llm_api_key,
        base_url=llm_base_url,
        model=model_name,
        temperature=0.2,
    )
    llm_with_tools = llm.bind_tools(tools)

    # Conversation -----------------------------------------------------
    system_prompt = await _build_system_prompt(
        fitness_service=fitness_service,
        user_id=user_id,
        user_timezone=user_timezone,
    )
    lc_messages: list[Any] = [SystemMessage(content=system_prompt)]
    for h in conversation_history:
        role = h.get("role")
        content = h.get("content") or ""
        if role == "user":
            lc_messages.append(HumanMessage(content=content))
        elif role == "assistant":
            lc_messages.append(AIMessage(content=content))

    lc_messages.append(HumanMessage(content=message))

    tool_trace: list[dict[str, Any]] = []
    for _round in range(max_rounds):
        ai_msg: AIMessage = await llm_with_tools.ainvoke(lc_messages)
        # If no tool calls => final response.
        if not getattr(ai_msg, "tool_calls", None):
            if is_meal_log_request(message):
                meal_log_handled = False
                async for event in _try_direct_meal_log(
                    message=message,
                    openai_client=openai_client,
                    model_name=model_name,
                ):
                    meal_log_handled = True
                    yield event
                if meal_log_handled:
                    return

            content = ai_msg.content or ""
            write_success = any(
                t.get("tool_name") in {"log_meal", "set_daily_calorie_goal", "delete_diary_entry"}
                and t.get("status") == "success"
                for t in tool_trace
            )
            if _contains_write_claim(content) and not write_success:
                content = _build_safe_non_write_reply()
            if content:
                # chunk once with full content
                yield {"type": "chunk", "source": "agent", "content": content}
            yield {"type": "final_response", "source": "agent", "content": content}
            yield {"type": "done", "source": "agent"}
            return

        # Tool calls ---------------------------------------------------
        tool_calls = list(ai_msg.tool_calls)  # type: ignore[attr-defined]
        # append the assistant message so tool call ids are consistent
        lc_messages.append(ai_msg)

        for tc in tool_calls:
            tool_name = getattr(tc, "name", None) or tc.get("name")  # type: ignore[union-attr]
            call_id = getattr(tc, "id", None) or tc.get("id")  # type: ignore[union-attr]
            args = getattr(tc, "args", None) or tc.get("args") or {}  # type: ignore[union-attr]
            tool_name_str = str(tool_name)

            if is_write_tool(tool_name_str):
                previous_goal = None
                if tool_name_str == "set_daily_calorie_goal":
                    previous_goal = (await fitness_service.get_goal(user_id)).daily_calorie_goal
                preview = build_approval_preview(
                    tool_name_str,
                    dict(args),
                    previous_goal=previous_goal,
                )
                async for event in _yield_write_tool_approval(
                    tool_name=tool_name_str,
                    tool_args=dict(args),
                    preview=preview,
                    call_id=str(call_id),
                ):
                    yield event
                async for event in _finish_with_approval_prompt(
                    tool_name=tool_name_str,
                    preview=preview,
                ):
                    yield event
                return

            yield {
                "type": "tool_call_start",
                "source": "agent",
                "call_id": str(call_id),
                "tool_name": tool_name_str,
                "tool_args": args,
            }
            start = time.time()
            tool_result: Any = None
            try:
                tool_obj = {t.name: t for t in tools}.get(tool_name_str)
                if not tool_obj:
                    raise FitnessAgentRuntimeError(f"未知工具：{tool_name}")

                if _tool_supports_progress(tool_name_str):
                    raw_foods = args.get("foods") if isinstance(args, dict) else None
                    food_inputs = [
                        item if isinstance(item, FoodItemInput) else FoodItemInput(**item)
                        for item in (raw_foods or [])
                    ]

                    async def _invoke_resolve(on_progress: ProgressCallback | None = None) -> list[dict[str, Any]]:
                        resolved = await resolve_food_calories(
                            food_inputs,
                            openai_client=openai_client,
                            model_name=model_name,
                            on_progress=on_progress,
                        )
                        return [r.model_dump(mode="json") for r in resolved]

                    async for progress_event, payload in _invoke_with_tool_progress(
                        call_id=str(call_id),
                        tool_name=tool_name_str,
                        invoke=_invoke_resolve,
                    ):
                        if progress_event:
                            yield progress_event
                        else:
                            tool_result = payload
                elif hasattr(tool_obj, "ainvoke"):
                    tool_result = await tool_obj.ainvoke(args)
                else:
                    tool_result = tool_obj.invoke(args)  # type: ignore[operator]

                duration_ms = int((time.time() - start) * 1000)
                yield {
                    "type": "tool_call_result",
                    "source": "agent",
                    "call_id": str(call_id),
                    "result": tool_result,
                    "status": "success",
                    "duration_ms": duration_ms,
                }
                # Derived higher-level events for front-end convenience
                if tool_name_str == "recommend_meals":
                    yield {
                        "type": "recommendations",
                        "source": "agent",
                        "recommendations": (tool_result or {}).get("recommendations", []),
                    }
                if tool_name_str == "resolve_food_calories" and is_meal_log_request(message):
                    resolved_list = tool_result if isinstance(tool_result, list) else []
                    items = _resolved_list_to_log_items(resolved_list)
                    if items:
                        meal_type = detect_meal_type(message, default="lunch")
                        async for event in _emit_meal_log_approval(
                            meal_type=meal_type,
                            items=items,
                            call_id=f"{call_id}-log",
                        ):
                            yield event
                        return
                tool_trace.append(
                    {
                        "tool_name": tool_name_str,
                        "tool_args": args,
                        "status": "success",
                        "duration_ms": duration_ms,
                        "result": tool_result,
                    }
                )
            except Exception as exc:
                duration_ms = int((time.time() - start) * 1000)
                yield {
                    "type": "tool_call_result",
                    "source": "agent",
                    "call_id": str(call_id),
                    "result": None,
                    "status": "error",
                    "error": str(exc),
                    "duration_ms": duration_ms,
                }
                tool_trace.append(
                    {
                        "tool_name": tool_name_str,
                        "tool_args": args,
                        "status": "error",
                        "duration_ms": duration_ms,
                        "error": str(exc),
                    }
                )
                # keep going; model will handle tool error and retry

            # ToolMessage content should be a string
            lc_messages.append(
                ToolMessage(
                    content=_json_dumps_safe(tool_result),
                    tool_call_id=str(call_id),
                )
            )

    # If we exit the loop without final response
    yield {
        "type": "error",
        "source": "agent",
        "error_type": "max_rounds_exceeded",
        "message": "Agent 超出最大轮数，未生成最终回复。",
        "recoverable": False,
    }
    yield {"type": "done", "source": "agent"}

