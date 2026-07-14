"""Deterministic Spider pipeline with SSE events.

DeepAgents `task` subagent delegation can hang in some environments, so the API
uses this reliable staged pipeline that reuses the same tools and Docker sandbox.
"""

from __future__ import annotations

import json
import re
import textwrap
import uuid
from typing import Any, AsyncIterator

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI

from app.spider.services.sandbox import (
    create_execute_in_sandbox_tool,
    initialize_session_sandbox,
    list_workspace_files,
)
from app.spider.services.sandbox_workspace import SandboxWorkspace
from app.spider.services.tools import (
    analyze_html_structure,
    clean_data,
    detect_anti_scraping,
    fetch_url,
    save_spider_code,
    set_sandbox_workspace,
    validate_code_syntax,
    validate_data,
)

STAGE_LABELS = {
    "web_analyzer": "网站结构分析",
    "code_generator": "爬虫代码生成",
    "debug_agent": "沙箱执行调试",
    "data_processor": "数据清洗质检",
}


def _call_id() -> str:
    return f"call_{uuid.uuid4().hex[:12]}"


def _preview(value: Any, limit: int = 1200) -> str:
    if isinstance(value, str):
        text = value
    else:
        text = json.dumps(value, ensure_ascii=False, default=str)
    return text if len(text) <= limit else text[:limit] + "... [truncated]"


def _error_event(
    *,
    code: str,
    title: str,
    detail: str,
    hints: list[str] | None = None,
    stage: str | None = None,
    recoverable: bool = False,
) -> dict[str, Any]:
    """Structured error for SSE + persistence; `message` stays human-readable for fallbacks."""
    hint_list = [h for h in (hints or []) if h]
    lines = [title]
    if detail:
        lines.extend(["", detail])
    if hint_list:
        lines.append("")
        lines.append("你可以尝试：")
        lines.extend(f"- {hint}" for hint in hint_list)
    return {
        "type": "error",
        "source": "agent",
        "code": code,
        "title": title,
        "detail": detail,
        "hints": hint_list,
        "stage": stage,
        "message": "\n".join(lines),
        "recoverable": recoverable,
    }


async def _emit_stage_start(
    stage: str,
    description: str,
) -> list[dict[str, Any]]:
    call_id = _call_id()
    return [
        {
            "type": "tool_call_start",
            "source": "agent",
            "call_id": call_id,
            "tool_name": f"子智能体 · {STAGE_LABELS[stage]}",
            "tool_args": {"subagent_type": stage, "description": description},
            "raw_tool_name": "task",
        },
        {
            "type": "subagent_start",
            "source": "agent",
            "call_id": call_id,
            "subagent": stage,
            "description": description,
        },
    ]


async def _emit_stage_complete(call_id: str, result_preview: str) -> list[dict[str, Any]]:
    return [
        {
            "type": "tool_call_result",
            "source": "agent",
            "call_id": call_id,
            "tool_name": "task",
            "result": result_preview,
            "status": "success",
        },
        {
            "type": "subagent_complete",
            "source": "agent",
            "call_id": call_id,
            "result_preview": result_preview,
        },
    ]


def _workspace_updated_event(workspace: SandboxWorkspace) -> dict[str, Any]:
    return {
        "type": "workspace_updated",
        "source": "agent",
        "workspace_path": workspace.display_path,
        "volume_name": workspace.volume_name,
        "files": list_workspace_files(workspace),
    }


def _resolve_target_url(message: str, target_url: str | None) -> str:
    if target_url and target_url.strip():
        return target_url.strip()
    for token in message.split():
        if token.startswith("http://") or token.startswith("https://"):
            return token.strip(".,;)")
    raise ValueError("请填写目标网址，或在消息中包含 http(s):// 链接")


def _strip_code_fences(code: str) -> str:
    text = code.strip()
    if not text.startswith("```"):
        return text
    return textwrap.dedent(
        "\n".join(line for line in text.splitlines() if not line.strip().startswith("```"))
    ).strip()


def _fix_common_requests_mistakes(code: str) -> str:
    """Fix frequent LLM mistakes that pass syntax check but fail at runtime."""
    # session.headers.add('Key', 'value') -> session.headers['Key'] = 'value'
    code = re.sub(
        r"(\b[\w.]+\.headers)\.add\(\s*(['\"])([^'\"]+)\2\s*,\s*([^)]+?)\s*\)",
        r"\1[\2\3\2] = \4",
        code,
    )
    return code


def _sanitize_python_code(code: str) -> str:
    """Normalize full-width punctuation that breaks Python syntax (common with local LLMs)."""
    replacements = {
        "\uff1a": ":",  # ：
        "\uff08": "(",  # （
        "\uff09": ")",  # ）
        "\uff1b": ";",  # ；
        "\u201c": '"',  # "
        "\u201d": '"',  # "
        "\u2018": "'",  # '
        "\u2019": "'",  # '
    }
    for old, new in replacements.items():
        code = code.replace(old, new)
    return _fix_common_requests_mistakes(code)


def _fallback_spider_code(target_url: str, *, limit: int = 10) -> str:
    """Deterministic spider template used when LLM output is not valid Python."""
    return textwrap.dedent(
        f'''
        #!/usr/bin/env python3
        # -*- coding: utf-8 -*-
        import json
        import logging
        import random
        import time
        from typing import Any

        import requests
        from bs4 import BeautifulSoup

        logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
        logger = logging.getLogger("spider")

        TARGET_URL = {target_url!r}
        LIMIT = {limit}


        def random_delay() -> None:
            time.sleep(random.uniform(1, 2))


        def fetch_page(session: requests.Session, url: str) -> str | None:
            try:
                random_delay()
                response = session.get(url, timeout=30)
                response.raise_for_status()
                response.encoding = response.apparent_encoding or "utf-8"
                return response.text
            except Exception as exc:
                logger.error("fetch failed: %s", exc)
                return None


        def parse_items(soup: BeautifulSoup) -> list[dict[str, Any]]:
            items: list[dict[str, Any]] = []
            selectors = [
                ("div.quote", "span.text", "small.author", "a.tag"),
                ("div.item", "a", None, None),
                ("li", "a", None, None),
                ("article", "h2", None, None),
            ]
            for container_sel, title_sel, author_sel, tag_sel in selectors:
                containers = soup.select(container_sel)
                if not containers:
                    continue
                for node in containers[:LIMIT]:
                    try:
                        title_el = node.select_one(title_sel) if title_sel else node
                        title = title_el.get_text(strip=True) if title_el else ""
                        href = title_el.get("href", "") if title_el and title_el.name == "a" else ""
                        if not href:
                            link = node.select_one("a[href]")
                            href = link.get("href", "") if link else ""
                        author = ""
                        if author_sel:
                            author_el = node.select_one(author_sel)
                            author = author_el.get_text(strip=True) if author_el else ""
                        tags: list[str] = []
                        if tag_sel:
                            tags = [t.get_text(strip=True) for t in node.select(tag_sel)]
                        if title or href:
                            items.append({{
                                "title": title,
                                "url": href,
                                "author": author,
                                "tags": tags,
                            }})
                    except Exception:
                        continue
                if items:
                    break
            return items[:LIMIT]


        def main() -> int:
            session = requests.Session()
            session.headers.update({{
                "User-Agent": (
                    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
                ),
                "Accept-Encoding": "gzip, deflate",
            }})
            html = fetch_page(session, TARGET_URL)
            if not html:
                return 1
            soup = BeautifulSoup(html, "lxml")
            data = parse_items(soup)
            with open("scraped_data.json", "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            logger.info("saved %s records", len(data))
            return 0 if data else 1


        if __name__ == "__main__":
            raise SystemExit(main())
        '''
    ).strip()


async def _validate_python_code(code: str) -> dict[str, Any]:
    return await validate_code_syntax.ainvoke({"code": code})


async def _generate_spider_code(
    *,
    llm_api_key: str,
    llm_base_url: str,
    model_name: str,
    target_url: str,
    analysis: str,
    anti_scraping: dict[str, Any],
    limit: int = 5,
) -> str:
    llm = ChatOpenAI(
        api_key=llm_api_key,
        base_url=llm_base_url,
        model=model_name,
        temperature=0,
    )
    system = SystemMessage(
        content=(
            "你是 Python 爬虫工程师。根据网站分析结果生成可运行的 requests+BeautifulSoup 爬虫脚本。\n"
            "要求：\n"
            "- 只输出纯 Python 源码，禁止 Markdown 代码块\n"
            "- 代码中只能使用 ASCII 标点符号（冒号/逗号/括号必须用英文半角 : , ( )）\n"
            "- 中文内容只能出现在字符串字面量或注释中\n"
            "- 必须使用同步代码：只用 requests + BeautifulSoup，禁止 asyncio / aiohttp / await / async def\n"
            "- 入口必须是同步 def main() -> int，并用 if __name__ == '__main__': raise SystemExit(main())\n"
            "- TARGET_URL 必须等于给定目标 URL，禁止改写、加空格或猜测路径\n"
            "- 使用 requests.Session、logging、random.uniform 延迟\n"
            "- session.headers 是字典，只能用 headers['Key']=value 或 headers.update({...})，禁止 headers.add()\n"
            "- Accept-Encoding 只能是 gzip, deflate\n"
            "- 解析失败不能中断整体流程，用 try/except 跳过坏节点\n"
            "- 无论解析到多少条，都要把 list 写入 scraped_data.json（ensure_ascii=False）；0 条也要写 []\n"
            "- 有有效记录返回 0，0 条记录返回 1\n"
            "- 只爬取首页前几条数据即可\n"
            f"- 最多爬取 {limit} 条记录\n"
        )
    )
    human = HumanMessage(
        content=(
            f"目标 URL: {target_url}\n\n"
            f"结构分析:\n{analysis}\n\n"
            f"反爬检测:\n{json.dumps(anti_scraping, ensure_ascii=False)}\n\n"
            "请生成 spider.py 完整代码。"
        )
    )
    response = await llm.ainvoke([system, human])
    code = response.content if isinstance(response.content, str) else str(response.content)
    return _sanitize_python_code(_strip_code_fences(code))


async def _generate_spider_code_with_retry(
    *,
    llm_api_key: str,
    llm_base_url: str,
    model_name: str,
    target_url: str,
    analysis: str,
    anti_scraping: dict[str, Any],
    limit: int = 5,
) -> tuple[str, str]:
    """Returns (code, source) where source is llm|llm_fixed|template."""
    code = await _generate_spider_code(
        llm_api_key=llm_api_key,
        llm_base_url=llm_base_url,
        model_name=model_name,
        target_url=target_url,
        analysis=analysis,
        anti_scraping=anti_scraping,
        limit=limit,
    )
    syntax = await _validate_python_code(code)
    if syntax.get("valid"):
        return code, "llm"

    llm = ChatOpenAI(
        api_key=llm_api_key,
        base_url=llm_base_url,
        model=model_name,
        temperature=0,
    )
    fix = await llm.ainvoke(
        [
            SystemMessage(
                content=(
                    "修复以下 Python 爬虫代码的语法错误。"
                    "只输出完整可运行代码，不要解释，不要使用全角标点。"
                )
            ),
            HumanMessage(content=code),
        ]
    )
    fixed = _sanitize_python_code(
        _strip_code_fences(fix.content if isinstance(fix.content, str) else str(fix.content))
    )
    syntax = await _validate_python_code(fixed)
    if syntax.get("valid"):
        return fixed, "llm_fixed"

    template = _fallback_spider_code(target_url, limit=limit)
    return template, "template"


async def _fix_runtime_spider_code(
    *,
    llm_api_key: str,
    llm_base_url: str,
    model_name: str,
    code: str,
    error_message: str,
) -> str:
    llm = ChatOpenAI(
        api_key=llm_api_key,
        base_url=llm_base_url,
        model=model_name,
        temperature=0,
    )
    fix = await llm.ainvoke(
        [
            SystemMessage(
                content=(
                    "修复以下 Python 爬虫代码的运行时错误。只输出完整可运行代码，不要解释。\n"
                    "硬性约束：\n"
                    "- 同步 requests + BeautifulSoup，禁止 asyncio/await/async def\n"
                    "- 入口必须同步 main()，用 raise SystemExit(main())\n"
                    "- 无论条数多少都写入 scraped_data.json；有数据退出 0，无数据退出 1\n"
                    "- TARGET_URL 保持不变，不要改 URL\n"
                    "- requests.Session().headers 只能用 session.headers['Key'] = 'value' "
                    "或 session.headers.update({...})，禁止 headers.add()。"
                )
            ),
            HumanMessage(content=f"错误信息:\n{error_message}\n\n当前代码:\n{code}"),
        ]
    )
    fixed = fix.content if isinstance(fix.content, str) else str(fix.content)
    return _sanitize_python_code(_strip_code_fences(fixed))


async def _execute_spider_with_retry(
    *,
    execute_in_sandbox,
    workspace: SandboxWorkspace,
    llm_api_key: str,
    llm_base_url: str,
    model_name: str,
    target_url: str,
    code_source: str,
    limit: int = 5,
) -> tuple[dict[str, Any], str]:
    """Run spider.py in sandbox; auto-fix runtime errors then fall back to template."""
    spider_code = workspace.read_text("spider.py") or ""
    exec_result: dict[str, Any] = {"success": False}
    source = code_source

    for attempt in range(3):
        sanitized = _sanitize_python_code(spider_code)
        if sanitized != spider_code:
            spider_code = sanitized
            await save_spider_code.ainvoke({"code": spider_code, "filename": "spider.py"})

        exec_result = await execute_in_sandbox.ainvoke({"code": spider_code, "timeout": 120})
        if exec_result.get("success"):
            return exec_result, source

        error_msg = str(
            exec_result.get("error") or exec_result.get("output_preview") or "unknown execution error"
        )

        if attempt == 0 and source != "template":
            spider_code = await _fix_runtime_spider_code(
                llm_api_key=llm_api_key,
                llm_base_url=llm_base_url,
                model_name=model_name,
                code=spider_code,
                error_message=error_msg,
            )
            syntax = await _validate_python_code(spider_code)
            if syntax.get("valid"):
                await save_spider_code.ainvoke({"code": spider_code, "filename": "spider.py"})
                source = "llm_runtime_fixed"
                continue

        if attempt <= 1 and source != "template":
            spider_code = _fallback_spider_code(target_url, limit=limit)
            await save_spider_code.ainvoke({"code": spider_code, "filename": "spider.py"})
            source = "template"
            continue

        break

    return exec_result, source


async def spider_pipeline_stream(
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
    del conversation_history
    yield {"type": "start", "source": "agent"}

    try:
        resolved_url = _resolve_target_url(message, target_url)
    except ValueError as exc:
        yield _error_event(
            code="missing_target_url",
            title="缺少目标网址",
            detail=str(exc),
            hints=[
                "在上方「目标网址」输入框填写完整 http(s) 链接",
                "或在消息中直接粘贴带 http:// / https:// 的地址",
                "尽量使用列表页（如 /top250），而不是只有导航的首页",
            ],
            stage="web_analyzer",
            recoverable=True,
        )
        yield {"type": "done", "source": "agent"}
        return

    try:
        workspace = initialize_session_sandbox(user_id, session_id)
    except Exception as exc:
        yield _error_event(
            code="sandbox_init_failed",
            title="Docker 沙箱初始化失败",
            detail=str(exc),
            hints=[
                "确认 Docker Desktop 已启动",
                "检查后端能否访问 Docker（docker ps）",
                "确认镜像配置 SPIDER_DOCKER_IMAGE 可用",
            ],
            stage="debug_agent",
            recoverable=False,
        )
        yield {"type": "done", "source": "agent"}
        return

    set_sandbox_workspace(workspace)

    execute_in_sandbox = create_execute_in_sandbox_tool(workspace)

    # Stage 1: web_analyzer
    stage_events = await _emit_stage_start("web_analyzer", f"分析 {resolved_url}")
    call_id = stage_events[0]["call_id"]
    for event in stage_events:
        yield event

    fetch_result = await fetch_url.ainvoke({"url": resolved_url})
    if not fetch_result.get("success"):
        yield _error_event(
            code="fetch_failed",
            title="网页抓取失败",
            detail=str(fetch_result.get("error") or "未知网络错误"),
            hints=[
                "检查目标网址是否可在浏览器正常打开",
                "若网站有强反爬，可稍后再试或更换更开放的列表页",
                "确认本机网络可访问该域名",
            ],
            stage="web_analyzer",
            recoverable=False,
        )
        yield {"type": "done", "source": "agent"}
        return

    analysis = await analyze_html_structure.ainvoke(
        {"html_file": fetch_result["html_file"], "url": resolved_url}
    )
    anti = await detect_anti_scraping.ainvoke(
        {"url": resolved_url, "html_file": fetch_result["html_file"]}
    )
    workspace.write_text(
        "analysis_report.json",
        json.dumps(
            {"analysis": analysis, "anti_scraping": anti, "fetch": fetch_result},
            ensure_ascii=False,
            indent=2,
        ),
    )
    for event in await _emit_stage_complete(call_id, _preview(analysis)):
        yield event
    yield _workspace_updated_event(workspace)

    # Stage 2: code_generator
    stage_events = await _emit_stage_start("code_generator", "根据分析结果生成 spider.py")
    call_id = stage_events[0]["call_id"]
    for event in stage_events:
        yield event

    code, code_source = await _generate_spider_code_with_retry(
        llm_api_key=llm_api_key,
        llm_base_url=llm_base_url,
        model_name=model_name,
        target_url=resolved_url,
        analysis=analysis if isinstance(analysis, str) else json.dumps(analysis, ensure_ascii=False),
        anti_scraping=anti if isinstance(anti, dict) else {},
    )
    syntax = await _validate_python_code(code)
    if not syntax.get("valid"):
        yield _workspace_updated_event(workspace)
        yield _error_event(
            code="codegen_syntax_invalid",
            title="生成的爬虫代码语法无效",
            detail=str(syntax.get("message") or "语法检查未通过"),
            hints=[
                "换用更强的代码模型（如 DeepSeek / OpenAI）再试",
                "缩小需求描述，明确要提取的字段",
                "检查本地 Ollama 模型是否过小导致胡乱生成",
            ],
            stage="code_generator",
            recoverable=False,
        )
        yield {"type": "done", "source": "agent"}
        return

    save_msg = await save_spider_code.ainvoke({"code": code, "filename": "spider.py"})
    if code_source == "template":
        save_msg = f"{save_msg}\n（LLM 代码无效，已自动切换为内置通用爬虫模板）"
    for event in await _emit_stage_complete(call_id, save_msg):
        yield event
    yield _workspace_updated_event(workspace)

    # Stage 3: debug_agent
    stage_events = await _emit_stage_start("debug_agent", "在 Docker 沙箱执行 spider.py")
    call_id = stage_events[0]["call_id"]
    for event in stage_events:
        yield event

    exec_result, exec_source = await _execute_spider_with_retry(
        execute_in_sandbox=execute_in_sandbox,
        workspace=workspace,
        llm_api_key=llm_api_key,
        llm_base_url=llm_base_url,
        model_name=model_name,
        target_url=resolved_url,
        code_source=code_source,
    )
    if not exec_result.get("success"):
        detail = str(exec_result.get("error") or exec_result.get("output_preview") or "未知执行错误")
        no_data = (
            not exec_result.get("data_saved")
            and int(exec_result.get("exit_code") or 1) == 0
        ) or "scraped_data.json" in detail
        yield _workspace_updated_event(workspace)
        yield _error_event(
            code="empty_scrape" if no_data or "0 条" in detail else "execution_failed",
            title="未能爬取到有效数据" if no_data or "0 条" in detail or "未生成 scraped_data" in detail else "爬虫执行失败",
            detail=detail,
            hints=[
                "把目标网址换成明确的列表页（例如豆瓣 Top250：https://movie.douban.com/top250）",
                "打开工作区中的 source_page.html / spider.py，核对选择器是否与页面结构一致",
                "小模型生成代码不稳定时，可换官方 API 模型后重试",
                "若页面依赖 JS 渲染，当前流水线暂不支持，请换静态列表页",
            ],
            stage="debug_agent",
            recoverable=False,
        )
        yield {"type": "done", "source": "agent"}
        return

    exec_preview = _preview(exec_result)
    if exec_source == "template":
        exec_preview = f"{exec_preview}\n（LLM 代码运行失败，已自动切换为内置通用爬虫模板）"
    elif exec_source == "llm_runtime_fixed":
        exec_preview = f"{exec_preview}\n（已根据运行错误自动修复代码）"
    for event in await _emit_stage_complete(call_id, exec_preview):
        yield event
    yield _workspace_updated_event(workspace)

    # Stage 4: data_processor
    stage_events = await _emit_stage_start("data_processor", "清洗并验证 scraped_data.json")
    call_id = stage_events[0]["call_id"]
    for event in stage_events:
        yield event

    if not workspace.exists("raw_data.json") and workspace.exists("scraped_data.json"):
        scraped_data = workspace.read_text("scraped_data.json")
        if scraped_data:
            workspace.write_text("raw_data.json", scraped_data)

    if not workspace.exists("raw_data.json"):
        scraped_exists = workspace.exists("scraped_data.json")
        scraped_bytes = workspace.read_bytes("scraped_data.json") if scraped_exists else None
        empty_scraped = scraped_bytes is not None and len(scraped_bytes.strip()) < 3
        yield _workspace_updated_event(workspace)
        detail = (
            "工作区里已有 scraped_data.json，但内容为空或无效，无法进入清洗阶段。"
            if empty_scraped
            else (
                "执行阶段报告成功后仍缺少 raw_data.json / scraped_data.json。"
                "通常是脚本未按约定写出结果文件。"
            )
        )
        yield _error_event(
            code="missing_result_file",
            title="未找到有效的爬取结果",
            detail=detail,
            hints=[
                "查看工作区 spider.py 是否把结果写到 scraped_data.json",
                "打开 scraped_data.json / spider.py 检查是否未 await 异步主函数",
                "更换目标列表页后重新发起任务",
                "换更强的模型再生成一次爬虫代码",
            ],
            stage="data_processor",
            recoverable=False,
        )
        yield {"type": "done", "source": "agent"}
        return

    cleaned_json = await clean_data.ainvoke({"raw_data": "raw_data.json"})
    validation = await validate_data.ainvoke({"data": cleaned_json, "required_fields": None})
    workspace.write_text(
        "validation_report.json",
        json.dumps(validation, ensure_ascii=False, indent=2),
    )
    for event in await _emit_stage_complete(call_id, _preview(validation)):
        yield event
    yield _workspace_updated_event(workspace)

    record_count = validation.get("total_records", 0)
    final_content = (
        f"爬虫流程已完成。\n"
        f"- 目标网站: {resolved_url}\n"
        f"- 沙箱工作区: {workspace.display_path}\n"
        f"- 数据卷: {workspace.volume_name}\n"
        f"- 产出文件: source_page.html, spider.py, raw_data.json, cleaned_data.json\n"
        f"- 数据记录数: {record_count}\n"
        f"- 数据校验: {'通过' if validation.get('valid') else '存在缺失字段'}"
    )
    yield {"type": "chunk", "source": "agent", "content": final_content}
    yield {"type": "final_response", "source": "agent", "content": final_content}
    yield {"type": "done", "source": "agent"}
