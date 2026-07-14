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
from app.spider.services.target_url import try_resolve_spider_target_url
from app.spider.services.todo_events import build_todos_updated_event, pipeline_todo_snapshot
from app.spider.services.anti_scrape import classify_fetch_result, hints_for_error_code
from app.spider.services.browser_fetch import probe_playwright_available, run_playwright_fetch
from app.spider.services.tools import (
    analyze_html_structure,
    clean_data,
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
    resolved = try_resolve_spider_target_url(message, target_url)
    if not resolved:
        raise ValueError("请填写目标网址，或在消息中包含 http(s):// 链接")
    return resolved


def _todos_event(**kwargs: Any) -> dict[str, Any]:
    event = build_todos_updated_event(pipeline_todo_snapshot(**kwargs))
    assert event is not None
    return event


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


        def _pick_title(node: Any, title_sel: str | None) -> str:
            candidates: list[str] = []
            if title_sel:
                candidates.extend(
                    el.get_text(" ", strip=True) for el in node.select(title_sel)
                )
            for sel in ("span.title", ".title", "h2", "h3", "a[href]"):
                candidates.extend(
                    el.get_text(" ", strip=True) for el in node.select(sel)
                )
            for text in candidates:
                cleaned = text.replace("\xa0", " ").strip()
                if cleaned.startswith("/"):
                    cleaned = cleaned.lstrip("/").strip()
                if cleaned:
                    return cleaned.split("/")[0].strip() or cleaned
            return ""


        def _pick_href(node: Any) -> str:
            for link in node.select("a[href]"):
                href = (link.get("href") or "").strip()
                if href and not href.startswith(("javascript:", "#")):
                    return href
            return ""


        def parse_items(soup: BeautifulSoup) -> list[dict[str, Any]]:
            items: list[dict[str, Any]] = []
            selectors = [
                ("div.item", "span.title", "small.author", "a.tag"),
                ("div.quote", "span.text", "small.author", "a.tag"),
                ("li", "span.title", None, None),
                ("article", "h2", None, None),
                ("div.item", None, None, None),
                ("li", "a", None, None),
            ]
            for container_sel, title_sel, author_sel, tag_sel in selectors:
                containers = soup.select(container_sel)
                if not containers:
                    continue
                batch: list[dict[str, Any]] = []
                for node in containers[:LIMIT]:
                    try:
                        title = _pick_title(node, title_sel)
                        href = _pick_href(node)
                        author = ""
                        if author_sel:
                            author_el = node.select_one(author_sel)
                            author = author_el.get_text(strip=True) if author_el else ""
                        tags: list[str] = []
                        if tag_sel:
                            tags = [t.get_text(strip=True) for t in node.select(tag_sel)]
                        if title and href:
                            batch.append({{
                                "title": title,
                                "url": href,
                                "author": author,
                                "tags": tags,
                            }})
                    except Exception:
                        continue
                if batch and all(item["title"] for item in batch):
                    items = batch
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


def _fallback_playwright_spider_code(target_url: str, *, limit: int = 10) -> str:
    """Deterministic Playwright+BS template when LLM output is invalid."""
    return textwrap.dedent(
        f'''
        #!/usr/bin/env python3
        # -*- coding: utf-8 -*-
        import json
        import logging
        import random
        import time
        from typing import Any

        from bs4 import BeautifulSoup
        from playwright.sync_api import sync_playwright

        logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
        logger = logging.getLogger("spider")

        TARGET_URL = {target_url!r}
        LIMIT = {limit}


        def random_delay() -> None:
            time.sleep(random.uniform(0.5, 1.5))


        def fetch_html(url: str) -> str | None:
            try:
                random_delay()
                with sync_playwright() as p:
                    browser = p.chromium.launch(headless=True)
                    try:
                        page = browser.new_page(
                            user_agent=(
                                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                                "AppleWebKit/537.36 (KHTML, like Gecko) "
                                "Chrome/122.0.0.0 Safari/537.36"
                            )
                        )
                        page.goto(url, wait_until="domcontentloaded", timeout=45000)
                        return page.content()
                    finally:
                        browser.close()
            except Exception as exc:
                logger.error("playwright fetch failed: %s", exc)
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
            html = fetch_html(TARGET_URL)
            if not html:
                with open("scraped_data.json", "w", encoding="utf-8") as f:
                    json.dump([], f, ensure_ascii=False, indent=2)
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


def decide_initial_fetch_mode(anti: dict[str, Any], *, http_success: bool) -> str:
    """Return 'playwright' | 'http' | 'block_hard'."""
    if anti.get("block_hard"):
        return "block_hard"
    if anti.get("escalate_to_browser"):
        return "playwright"
    if not http_success:
        return "playwright"
    return "http"


def should_escalate_after_empty_scrape(
    *,
    scrape_engine: str,
    anti_level: str,
    already_escalated: bool,
) -> bool:
    if already_escalated or scrape_engine != "requests":
        return False
    return anti_level in {"soft", "js_render"}


def is_empty_scrape_result(exec_result: dict[str, Any], detail: str) -> bool:
    """True when failure is zero usable records, not a runtime crash."""
    if exec_result.get("data_saved"):
        return False
    detail_l = (detail or "").lower()
    if "scraped_data.json" in detail_l or "0 条" in detail or "saved 0 records" in detail_l:
        return True
    if int(exec_result.get("exit_code") or 1) == 0:
        return True
    if exec_result.get("data_file") and int(exec_result.get("record_count") or 0) == 0:
        return True
    return False


async def _validate_python_code(code: str) -> dict[str, Any]:
    return await validate_code_syntax.ainvoke({"code": code})


def _codegen_system_prompt(*, scrape_engine: str, limit: int) -> str:
    if scrape_engine == "playwright":
        return (
            "你是 Python 爬虫工程师。根据网站分析结果生成可运行的同步 Playwright 爬虫脚本。\n"
            "要求：\n"
            "- 只输出纯 Python 源码，禁止 Markdown 代码块\n"
            "- 代码中只能使用 ASCII 标点符号（冒号/逗号/括号必须用英文半角 : , ( )）\n"
            "- 中文内容只能出现在字符串字面量或注释中\n"
            "- 必须使用同步 Playwright（from playwright.sync_api import sync_playwright），禁止 asyncio / await\n"
            "- 可用 BeautifulSoup 解析 page.content() 返回的 HTML\n"
            "- 入口必须是同步 def main() -> int，并用 if __name__ == '__main__': raise SystemExit(main())\n"
            "- TARGET_URL 必须等于给定目标 URL，禁止改写\n"
            "- chromium.launch(headless=True)，设置合理 timeout 与短暂延迟\n"
            "- 无论解析到多少条，都要把 list 写入 scraped_data.json；0 条也要写 []\n"
            "- 有有效记录返回 0，0 条记录返回 1\n"
            f"- 最多爬取 {limit} 条记录\n"
        )
    return (
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
        "- 每条记录必须同时包含非空 title 与 url；图片海报链接（a>img、文本为空）不能当 title\n"
        "- 列表页优先用文本节点取标题（如 span.title / .title / h2），href 单独从 a[href] 取\n"
        "- 若某选择器抽出的 title 大量为空，必须换选择器，禁止写入空 title\n"
        "- 只爬取首页前几条数据即可\n"
        f"- 最多爬取 {limit} 条记录\n"
    )


async def _generate_spider_code(
    *,
    llm_api_key: str,
    llm_base_url: str,
    model_name: str,
    target_url: str,
    analysis: str,
    anti_scraping: dict[str, Any],
    limit: int = 5,
    scrape_engine: str = "requests",
) -> str:
    llm = ChatOpenAI(
        api_key=llm_api_key,
        base_url=llm_base_url,
        model=model_name,
        temperature=0,
    )
    system = SystemMessage(content=_codegen_system_prompt(scrape_engine=scrape_engine, limit=limit))
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
    scrape_engine: str = "requests",
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
        scrape_engine=scrape_engine,
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

    if scrape_engine == "playwright":
        return _fallback_playwright_spider_code(target_url, limit=limit), "template"
    return _fallback_spider_code(target_url, limit=limit), "template"


async def _fix_runtime_spider_code(
    *,
    llm_api_key: str,
    llm_base_url: str,
    model_name: str,
    code: str,
    error_message: str,
    scrape_engine: str = "requests",
) -> str:
    llm = ChatOpenAI(
        api_key=llm_api_key,
        base_url=llm_base_url,
        model=model_name,
        temperature=0,
    )
    if scrape_engine == "playwright":
        constraints = (
            "硬性约束：\n"
            "- 同步 Playwright（sync_playwright），可用 BeautifulSoup 解析 page.content()\n"
            "- 禁止 asyncio/await/async def\n"
            "- 入口必须同步 main()，用 raise SystemExit(main())\n"
            "- 无论条数多少都写入 scraped_data.json；有数据退出 0，无数据退出 1\n"
            "- TARGET_URL 保持不变，不要改 URL\n"
        )
    else:
        constraints = (
            "硬性约束：\n"
            "- 同步 requests + BeautifulSoup，禁止 asyncio/await/async def\n"
            "- 入口必须同步 main()，用 raise SystemExit(main())\n"
            "- 无论条数多少都写入 scraped_data.json；有数据退出 0，无数据退出 1\n"
            "- TARGET_URL 保持不变，不要改 URL\n"
            "- requests.Session().headers 只能用 session.headers['Key'] = 'value' "
            "或 session.headers.update({...})，禁止 headers.add()。\n"
        )
    fix = await llm.ainvoke(
        [
            SystemMessage(
                content=(
                    "修复以下 Python 爬虫代码的运行时错误。只输出完整可运行代码，不要解释。\n"
                    + constraints
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
    scrape_engine: str = "requests",
) -> tuple[dict[str, Any], str]:
    """Run spider.py in sandbox; auto-fix runtime errors then fall back to template."""
    spider_code = workspace.read_text("spider.py") or ""
    exec_result: dict[str, Any] = {"success": False}
    source = code_source
    fallback_from_error: str | None = None

    for attempt in range(3):
        sanitized = _sanitize_python_code(spider_code)
        if sanitized != spider_code:
            spider_code = sanitized
            await save_spider_code.ainvoke({"code": spider_code, "filename": "spider.py"})

        exec_result = await execute_in_sandbox.ainvoke({"code": spider_code, "timeout": 120})
        if exec_result.get("success"):
            if fallback_from_error and source == "template":
                exec_result = {**exec_result, "fallback_from_error": fallback_from_error}
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
                scrape_engine=scrape_engine,
            )
            syntax = await _validate_python_code(spider_code)
            if syntax.get("valid"):
                await save_spider_code.ainvoke({"code": spider_code, "filename": "spider.py"})
                source = "llm_runtime_fixed"
                continue

        if attempt <= 1 and source != "template":
            fallback_from_error = error_msg
            if scrape_engine == "playwright":
                spider_code = _fallback_playwright_spider_code(target_url, limit=limit)
            else:
                spider_code = _fallback_spider_code(target_url, limit=limit)
            await save_spider_code.ainvoke({"code": spider_code, "filename": "spider.py"})
            source = "template"
            continue

        break

    if fallback_from_error and isinstance(exec_result, dict):
        exec_result = {**exec_result, "fallback_from_error": fallback_from_error}
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
    yield _todos_event(active_index=0)
    stage_events = await _emit_stage_start("web_analyzer", f"分析 {resolved_url}")
    call_id = stage_events[0]["call_id"]
    for event in stage_events:
        yield event

    fetch_result = await fetch_url.ainvoke({"url": resolved_url})
    html_for_classify = str(fetch_result.get("html_content") or "")
    anti = classify_fetch_result(
        url=resolved_url,
        html=html_for_classify,
        status_code=fetch_result.get("status_code") if fetch_result.get("success") else (
            fetch_result.get("status_code") or 0
        ),
    )
    mode = decide_initial_fetch_mode(anti, http_success=bool(fetch_result.get("success")))
    fetch_mode = "http"
    scrape_engine = "requests"
    escalation_reason: str | None = None
    already_escalated = False

    if mode == "block_hard":
        yield _todos_event(completed_through=-1, failed_index=0)
        yield _error_event(
            code="anti_scrape_hard",
            title="目标站启用了验证码/人机校验",
            detail=str(anti.get("recommendations") or anti.get("detected_mechanisms") or "hard anti-scrape"),
            hints=hints_for_error_code("anti_scrape_hard"),
            stage="web_analyzer",
            recoverable=False,
        )
        yield {"type": "done", "source": "agent"}
        return

    if mode == "playwright":
        escalation_reason = (
            "classify_escalate"
            if anti.get("escalate_to_browser")
            else "http_fetch_failed"
        )
        if not probe_playwright_available(workspace):
            yield _todos_event(completed_through=-1, failed_index=0)
            yield _error_event(
                code="browser_image_unavailable",
                title="需要浏览器抓取，但沙箱镜像未提供 Playwright",
                detail=str(fetch_result.get("error") or "HTTP 抓取不足，需升级 Playwright"),
                hints=hints_for_error_code("browser_image_unavailable"),
                stage="web_analyzer",
                recoverable=False,
            )
            yield {"type": "done", "source": "agent"}
            return

        pw = run_playwright_fetch(workspace, resolved_url)
        if not pw.get("success"):
            code = "fetch_failed" if not fetch_result.get("success") else "browser_fetch_failed"
            yield _todos_event(completed_through=-1, failed_index=0)
            yield _error_event(
                code=code,
                title="网页抓取失败",
                detail=str(pw.get("error") or fetch_result.get("error") or "browser fetch failed"),
                hints=hints_for_error_code(code),
                stage="web_analyzer",
                recoverable=False,
            )
            yield {"type": "done", "source": "agent"}
            return

        already_escalated = True
        fetch_mode = "playwright"
        scrape_engine = "playwright"
        anti = classify_fetch_result(
            url=resolved_url,
            html=str(pw.get("html_content") or ""),
            status_code=200,
        )
        if anti.get("block_hard"):
            yield _todos_event(completed_through=-1, failed_index=0)
            yield _error_event(
                code="anti_scrape_hard",
                title="浏览器渲染后仍是验证码/人机校验页",
                detail=str(anti.get("detected_mechanisms") or "hard anti-scrape"),
                hints=hints_for_error_code("anti_scrape_hard"),
                stage="web_analyzer",
                recoverable=False,
            )
            yield {"type": "done", "source": "agent"}
            return
        fetch_result = {
            **fetch_result,
            "success": True,
            "html_file": pw.get("html_file") or "source_page.html",
            "html_content": pw.get("html_content") or "",
            "fetch_mode": "playwright",
        }
    elif not fetch_result.get("success"):
        yield _todos_event(completed_through=-1, failed_index=0)
        yield _error_event(
            code="fetch_failed",
            title="网页抓取失败",
            detail=str(fetch_result.get("error") or "未知网络错误"),
            hints=hints_for_error_code("fetch_failed"),
            stage="web_analyzer",
            recoverable=False,
        )
        yield {"type": "done", "source": "agent"}
        return

    analysis = await analyze_html_structure.ainvoke(
        {"html_file": fetch_result["html_file"], "url": resolved_url}
    )
    workspace.write_text(
        "analysis_report.json",
        json.dumps(
            {
                "analysis": analysis,
                "anti_scraping": anti,
                "fetch": {
                    k: v
                    for k, v in fetch_result.items()
                    if k != "html_content"
                },
                "fetch_mode": fetch_mode,
                "scrape_engine": scrape_engine,
                "anti_level": anti.get("level"),
                "escalation_reason": escalation_reason,
            },
            ensure_ascii=False,
            indent=2,
        ),
    )
    for event in await _emit_stage_complete(call_id, _preview(analysis)):
        yield event
    yield _todos_event(completed_through=0, active_index=1)
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
        scrape_engine=scrape_engine,
    )
    syntax = await _validate_python_code(code)
    if not syntax.get("valid"):
        yield _workspace_updated_event(workspace)
        yield _todos_event(completed_through=0, failed_index=1)
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
        engine_label = "Playwright" if scrape_engine == "playwright" else "通用"
        save_msg = f"{save_msg}\n（LLM 代码无效，已自动切换为内置{engine_label}爬虫模板）"
    for event in await _emit_stage_complete(call_id, save_msg):
        yield event
    yield _todos_event(completed_through=1, active_index=2)
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
        scrape_engine=scrape_engine,
    )
    if not exec_result.get("success"):
        detail = str(exec_result.get("error") or exec_result.get("output_preview") or "未知执行错误")
        no_data = is_empty_scrape_result(exec_result, detail)

        if no_data and should_escalate_after_empty_scrape(
            scrape_engine=scrape_engine,
            anti_level=str(anti.get("level") or "none"),
            already_escalated=already_escalated,
        ):
            if not probe_playwright_available(workspace):
                yield _workspace_updated_event(workspace)
                yield _todos_event(completed_through=1, failed_index=2)
                yield _error_event(
                    code="browser_image_unavailable",
                    title="空爬取后需升级浏览器，但沙箱镜像无 Playwright",
                    detail=detail,
                    hints=hints_for_error_code("browser_image_unavailable"),
                    stage="debug_agent",
                    recoverable=False,
                )
                yield {"type": "done", "source": "agent"}
                return

            pw = run_playwright_fetch(workspace, resolved_url)
            if not pw.get("success"):
                yield _workspace_updated_event(workspace)
                yield _todos_event(completed_through=1, failed_index=2)
                yield _error_event(
                    code="browser_fetch_failed",
                    title="空爬取后的浏览器重抓失败",
                    detail=str(pw.get("error") or detail),
                    hints=hints_for_error_code("browser_fetch_failed"),
                    stage="debug_agent",
                    recoverable=False,
                )
                yield {"type": "done", "source": "agent"}
                return

            already_escalated = True
            scrape_engine = "playwright"
            fetch_mode = "playwright"
            escalation_reason = "empty_scrape_soft"
            anti = classify_fetch_result(
                url=resolved_url,
                html=str(pw.get("html_content") or ""),
                status_code=200,
            )
            if anti.get("block_hard"):
                yield _workspace_updated_event(workspace)
                yield _todos_event(completed_through=1, failed_index=2)
                yield _error_event(
                    code="anti_scrape_hard",
                    title="升级浏览器后仍是验证码页",
                    detail=str(anti.get("detected_mechanisms") or detail),
                    hints=hints_for_error_code("anti_scrape_hard"),
                    stage="debug_agent",
                    recoverable=False,
                )
                yield {"type": "done", "source": "agent"}
                return

            analysis = await analyze_html_structure.ainvoke(
                {"html_file": pw.get("html_file") or "source_page.html", "url": resolved_url}
            )
            code, code_source = await _generate_spider_code_with_retry(
                llm_api_key=llm_api_key,
                llm_base_url=llm_base_url,
                model_name=model_name,
                target_url=resolved_url,
                analysis=analysis if isinstance(analysis, str) else json.dumps(analysis, ensure_ascii=False),
                anti_scraping=anti if isinstance(anti, dict) else {},
                scrape_engine=scrape_engine,
            )
            await save_spider_code.ainvoke({"code": code, "filename": "spider.py"})
            exec_result, exec_source = await _execute_spider_with_retry(
                execute_in_sandbox=execute_in_sandbox,
                workspace=workspace,
                llm_api_key=llm_api_key,
                llm_base_url=llm_base_url,
                model_name=model_name,
                target_url=resolved_url,
                code_source=code_source,
                scrape_engine=scrape_engine,
            )

        if not exec_result.get("success"):
            detail = str(exec_result.get("error") or exec_result.get("output_preview") or "未知执行错误")
            no_data = is_empty_scrape_result(exec_result, detail)
            err_code = "empty_scrape" if no_data else "execution_failed"
            yield _workspace_updated_event(workspace)
            yield _todos_event(completed_through=1, failed_index=2)
            yield _error_event(
                code=err_code,
                title="未能爬取到有效数据" if no_data else "爬虫执行失败",
                detail=detail,
                hints=hints_for_error_code(err_code),
                stage="debug_agent",
                recoverable=False,
            )
            yield {"type": "done", "source": "agent"}
            return

    exec_preview = _preview(exec_result)
    if exec_source == "template":
        exec_preview = f"{exec_preview}\n（LLM 代码运行失败，已自动切换为内置爬虫模板）"
        original_err = str(exec_result.get("fallback_from_error") or "").strip()
        if original_err:
            workspace.write_text("llm_exec_error.txt", original_err)
            exec_preview = f"{exec_preview}\n原始错误: {_preview(original_err, limit=400)}"
    elif exec_source == "llm_runtime_fixed":
        exec_preview = f"{exec_preview}\n（已根据运行错误自动修复代码）"
    if fetch_mode == "playwright":
        exec_preview = f"{exec_preview}\n（fetch_mode=playwright）"
    for event in await _emit_stage_complete(call_id, exec_preview):
        yield event
    yield _todos_event(completed_through=2, active_index=3)
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
        yield _todos_event(completed_through=2, failed_index=3)
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
    validation = await validate_data.ainvoke({"data": cleaned_json, "required_fields": ["title"]})
    workspace.write_text(
        "validation_report.json",
        json.dumps(validation, ensure_ascii=False, indent=2),
    )
    if not validation.get("valid"):
        yield _workspace_updated_event(workspace)
        yield _todos_event(completed_through=2, failed_index=3)
        issues = validation.get("issues") or []
        detail = (
            f"清洗后数据缺少必填字段 title（无效 {validation.get('invalid_records', 0)}/"
            f"{validation.get('total_records', 0)} 条）。"
        )
        if issues:
            detail = f"{detail} 示例: {json.dumps(issues[:3], ensure_ascii=False)}"
        yield _error_event(
            code="validation_failed",
            title="数据校验未通过",
            detail=detail,
            hints=[
                "打开 cleaned_data.json，确认每条记录都有非空 title",
                "检查 spider.py 选择器是否取到了文本标题（勿用仅含图片的 a 标签）",
                "换更强的模型重新生成爬虫代码后重试",
            ],
            stage="data_processor",
            recoverable=False,
        )
        yield {"type": "done", "source": "agent"}
        return

    for event in await _emit_stage_complete(call_id, _preview(validation)):
        yield event
    yield _todos_event(completed_through=3)
    yield _workspace_updated_event(workspace)

    record_count = validation.get("total_records", 0)
    final_content = (
        f"爬虫流程已完成。\n"
        f"- 目标网站: {resolved_url}\n"
        f"- 沙箱工作区: {workspace.display_path}\n"
        f"- 数据卷: {workspace.volume_name}\n"
        f"- 产出文件: source_page.html, spider.py, raw_data.json, cleaned_data.json\n"
        f"- 数据记录数: {record_count}\n"
        f"- 数据校验: 通过"
    )
    yield {"type": "chunk", "source": "agent", "content": final_content}
    yield {"type": "final_response", "source": "agent", "content": final_content}
    yield {"type": "done", "source": "agent"}
