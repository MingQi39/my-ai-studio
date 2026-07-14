"""DeepAgents spider orchestrator SSE stream."""

from __future__ import annotations

import uuid
from typing import Any, AsyncIterator

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, ToolMessage

from app.spider.services.agent_builder import build_spider_agent
from app.spider.services.sandbox import initialize_session_sandbox, list_workspace_files
from app.spider.services.todo_events import build_todos_updated_event
from app.spider.services.tools import set_sandbox_workspace

SUBAGENT_LABELS = {
    "web_analyzer": "网站结构分析",
    "code_generator": "爬虫代码生成",
    "debug_agent": "沙箱执行调试",
    "data_processor": "数据清洗质检",
}


class SpiderAgentRuntimeError(RuntimeError):
    pass


def _tool_call_id() -> str:
    return f"call_{uuid.uuid4().hex[:12]}"


def _format_tool_name(tool_name: str, tool_args: dict[str, Any]) -> str:
    if tool_name == "task":
        assignee = tool_args.get("assignee") or tool_args.get("subagent_type") or "unknown"
        return f"子智能体 · {SUBAGENT_LABELS.get(assignee, assignee)}"
    return tool_name


def _build_task_prompt(message: str, *, target_url: str | None, conversation_history: list[dict[str, str]]) -> str:
    parts: list[str] = []
    if conversation_history:
        parts.append("## 历史对话摘要\n")
        for item in conversation_history[-6:]:
            role = item.get("role", "user")
            content = (item.get("content") or "").strip()
            if content:
                parts.append(f"- {role}: {content[:300]}")
        parts.append("")

    if target_url:
        parts.append(f"目标 URL: {target_url}\n")

    parts.append(message.strip())
    return "\n".join(parts).strip()


async def spider_agent_stream(
    *,
    message: str,
    conversation_history: list[dict[str, str]],
    user_id: str,
    session_id: str,
    llm_api_key: str,
    llm_base_url: str,
    model_name: str,
    target_url: str | None = None,
) -> AsyncIterator[dict[str, Any]]:
    yield {"type": "start", "source": "agent"}

    try:
        from deepagents import create_deep_agent  # noqa: F401
    except ImportError as exc:
        raise SpiderAgentRuntimeError(
            "DeepAgents 依赖未安装。请在后端 requirements 中加入 deepagents 后重装依赖。"
        ) from exc

    try:
        workspace = initialize_session_sandbox(user_id, session_id)
    except Exception as exc:
        yield {
            "type": "error",
            "source": "agent",
            "message": f"Docker 沙箱初始化失败: {exc}",
            "recoverable": False,
        }
        yield {"type": "done", "source": "agent"}
        return

    set_sandbox_workspace(workspace)

    agent = build_spider_agent(
        llm_api_key=llm_api_key,
        llm_base_url=llm_base_url,
        model_name=model_name,
        workspace=workspace,
    )

    task_prompt = _build_task_prompt(
        message,
        target_url=target_url,
        conversation_history=conversation_history,
    )

    content_buffer = ""
    emitted_tool_calls: set[str] = set()
    emitted_tool_results: set[str] = set()

    try:
        async for event in agent.astream(
            {"messages": [HumanMessage(content=task_prompt)]},
            config={"configurable": {"thread_id": session_id}},
        ):
            for _node_name, node_data in event.items():
                if not node_data or "messages" not in node_data:
                    continue

                messages = node_data["messages"]
                if not isinstance(messages, list):
                    messages = [messages]

                for msg in messages:
                    if not isinstance(msg, BaseMessage):
                        continue

                    if isinstance(msg, AIMessage) and getattr(msg, "tool_calls", None):
                        for tool_call in msg.tool_calls:
                            call_id = str(tool_call.get("id") or _tool_call_id())
                            if call_id in emitted_tool_calls:
                                continue
                            emitted_tool_calls.add(call_id)

                            tool_name = str(tool_call.get("name") or "unknown")
                            tool_args = dict(tool_call.get("args") or {})
                            display_name = _format_tool_name(tool_name, tool_args)

                            yield {
                                "type": "tool_call_start",
                                "source": "agent",
                                "call_id": call_id,
                                "tool_name": display_name,
                                "tool_args": tool_args,
                                "raw_tool_name": tool_name,
                            }

                            if tool_name == "write_todos":
                                todos_event = build_todos_updated_event(tool_args.get("todos"))
                                if todos_event is not None:
                                    yield todos_event

                            if tool_name == "task":
                                assignee = tool_args.get("assignee") or tool_args.get("subagent_type")
                                yield {
                                    "type": "subagent_start",
                                    "source": "agent",
                                    "call_id": call_id,
                                    "subagent": assignee,
                                    "description": tool_args.get("content") or tool_args.get("description"),
                                }

                    elif isinstance(msg, ToolMessage):
                        call_id = str(msg.tool_call_id or _tool_call_id())
                        if call_id in emitted_tool_results:
                            continue
                        emitted_tool_results.add(call_id)

                        result_text = msg.content if isinstance(msg.content, str) else str(msg.content)
                        yield {
                            "type": "tool_call_result",
                            "source": "agent",
                            "call_id": call_id,
                            "tool_name": msg.name or "tool",
                            "result": result_text[:2000],
                            "status": "success",
                        }

                        if msg.name == "task":
                            yield {
                                "type": "subagent_complete",
                                "source": "agent",
                                "call_id": call_id,
                                "result_preview": result_text[:1000],
                            }

                    elif isinstance(msg, AIMessage) and msg.content and not getattr(msg, "tool_calls", None):
                        chunk = msg.content if isinstance(msg.content, str) else str(msg.content)
                        if chunk.strip():
                            content_buffer = chunk
                            yield {"type": "chunk", "source": "agent", "content": chunk}

    except Exception as exc:
        yield {
            "type": "error",
            "source": "agent",
            "message": str(exc),
            "recoverable": False,
        }
        yield {"type": "done", "source": "agent"}
        return

    final_content = content_buffer.strip() or "爬虫任务已处理完成，请查看沙箱工作区文件。"
    yield {"type": "final_response", "source": "agent", "content": final_content}
    yield {
        "type": "workspace_updated",
        "source": "agent",
        "workspace_path": workspace.display_path,
        "volume_name": workspace.volume_name,
        "files": list_workspace_files(workspace),
    }
    yield {"type": "done", "source": "agent"}
