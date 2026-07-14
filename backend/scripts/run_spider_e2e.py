#!/usr/bin/env python3
"""End-to-end smoke test for the Spider Agent pipeline."""

from __future__ import annotations

import asyncio
import json
import sys
import uuid

BACKEND_ROOT = __import__("pathlib").Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

TARGET_URL = "https://quotes.toscrape.com/"
USER_MESSAGE = (
    "分析目标网站首页结构，生成简单爬虫代码，在沙箱执行后爬取首页前 5 条名言的 text 和 author，"
    "并清洗保存为 JSON。只需首页列表，不要翻页。"
)


async def step_tools(user_id: str, session_id: str) -> dict:
    from app.spider.services.sandbox import initialize_session_sandbox
    from app.spider.services.tools import analyze_html_structure, fetch_url, set_sandbox_workspace

    workspace = initialize_session_sandbox(user_id, session_id)
    set_sandbox_workspace(workspace)

    print("\n[1/4] fetch_url ...")
    fetch_result = await fetch_url.ainvoke({"url": TARGET_URL})
    print(
        json.dumps(
            {k: fetch_result.get(k) for k in ("success", "status_code", "url", "html_file", "sandbox_path", "error")},
            ensure_ascii=False,
        )
    )
    if not fetch_result.get("success"):
        raise RuntimeError(f"fetch_url failed: {fetch_result}")

    print("[1/4] analyze_html_structure ...")
    analysis = await analyze_html_structure.ainvoke(
        {"html_file": fetch_result["html_file"], "url": TARGET_URL}
    )
    preview = analysis[:300] if isinstance(analysis, str) else json.dumps(analysis, ensure_ascii=False)[:300]
    print(f"analysis preview: {preview}...")
    return fetch_result


async def step_docker(user_id: str, session_id: str) -> None:
    from app.spider.services.sandbox import initialize_session_sandbox

    print("\n[2/4] initialize session sandbox ...")
    workspace = initialize_session_sandbox(user_id, session_id)
    result = workspace.backend.execute("python --version")
    print(
        f"container={workspace.backend.id[:12]} "
        f"volume={workspace.volume_name} "
        f"exit={result.exit_code} output={result.output.strip()}"
    )


async def step_agent(user_id: str, model_config_id: str, session_id: str):
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

    from app.config import settings
    from app.services.model_service import ModelService
    from app.spider.services.sandbox import initialize_session_sandbox, list_workspace_files
    from app.spider.services.spider_pipeline_service import spider_pipeline_stream as spider_agent_stream
    from app.travel.llm_context import resolve_travel_llm

    workspace = initialize_session_sandbox(user_id, session_id)

    engine = create_async_engine(settings.DATABASE_URL)
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with session_factory() as db:
        model_service = ModelService(db)
        ctx = await resolve_travel_llm(model_service, uuid.UUID(user_id), uuid.UUID(model_config_id))

    print("\n[3/4] spider_agent_stream ...")
    print(f"model={ctx.model_id} sandbox={workspace.display_path} volume={workspace.volume_name}")

    event_counts: dict[str, int] = {}
    errors: list[str] = []
    final_response = ""

    async for event in spider_agent_stream(
        message=USER_MESSAGE,
        conversation_history=[],
        user_id=user_id,
        session_id=session_id,
        llm_api_key=ctx.api_key,
        llm_base_url=ctx.base_url,
        model_name=ctx.model_id,
        target_url=TARGET_URL,
    ):
        etype = str(event.get("type"))
        event_counts[etype] = event_counts.get(etype, 0) + 1
        if etype == "tool_call_start":
            print(f"  -> tool_start: {event.get('tool_name')}")
        elif etype == "subagent_start":
            print(f"  -> subagent: {event.get('subagent')}")
        elif etype == "error":
            msg = str(event.get("message") or event)
            errors.append(msg)
            print(f"  !! error: {msg}")
        elif etype == "final_response":
            final_response = str(event.get("content") or "")
            print(f"  -> final: {final_response[:200]}...")
        elif etype == "done":
            print("  -> done")

    await engine.dispose()

    print("\n[4/4] sandbox files:")
    files = list_workspace_files(workspace)
    for file in files:
        print(f"  - {file['name']} ({file['size']} bytes)")

    print("\nEvent summary:", json.dumps(event_counts, ensure_ascii=False))
    if errors:
        raise RuntimeError("agent reported errors: " + "; ".join(errors))

    expected_any = {"source_page.html", "spider.py"}
    produced = {f["name"] for f in files}
    if not produced:
        raise RuntimeError("sandbox is empty after agent run")

    if not produced.intersection(expected_any):
        print(f"warning: expected some of {expected_any}, got {produced}")

    return workspace


async def main() -> None:
    import sqlite3

    db_path = BACKEND_ROOT / "myai_studio.db"
    conn = sqlite3.connect(db_path)
    user_id, email = conn.execute("SELECT id, email FROM users LIMIT 1").fetchone()
    model_config_id = conn.execute(
        """
        SELECT id FROM model_configs
        WHERE user_id = ?
          AND adapter_type = 'official'
        ORDER BY created_at DESC
        LIMIT 1
        """,
        (user_id,),
    ).fetchone()
    if model_config_id is None:
        row = conn.execute(
            "SELECT id FROM model_configs WHERE user_id = ? ORDER BY created_at DESC LIMIT 1",
            (user_id,),
        ).fetchone()
        if row is None:
            raise RuntimeError("No model config found for user")
        model_config_id = row
    model_config_id = model_config_id[0]
    conn.close()

    session_id = f"e2e-{uuid.uuid4().hex[:8]}"

    print("Spider E2E")
    print(f"user={email} model_config={model_config_id}")
    print(f"target={TARGET_URL} session={session_id}")

    await step_tools(user_id, session_id)
    await step_docker(user_id, session_id)
    result_workspace = await step_agent(user_id, model_config_id, session_id)

    print("\n✅ E2E completed")
    print(f"sandbox: {result_workspace.display_path}")
    print(f"volume: {result_workspace.volume_name}")


if __name__ == "__main__":
    asyncio.run(main())
