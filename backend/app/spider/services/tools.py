"""LangChain tools for the DeepAgents spider workflow."""

from __future__ import annotations

import ast
import asyncio
import json
import random
import textwrap
import traceback
from collections import Counter
from contextvars import ContextVar
from typing import TYPE_CHECKING, Any

import aiohttp
from bs4 import BeautifulSoup
from langchain.tools import tool

if TYPE_CHECKING:
    from app.spider.services.sandbox_workspace import SandboxWorkspace

_sandbox_var: ContextVar["SandboxWorkspace"] = ContextVar("spider_sandbox_workspace")


def set_sandbox_workspace(workspace: "SandboxWorkspace") -> None:
    _sandbox_var.set(workspace)


def get_sandbox_workspace() -> "SandboxWorkspace":
    return _sandbox_var.get()


async def _read_sandbox_file(filename: str) -> str | None:
    workspace = get_sandbox_workspace()
    return await asyncio.to_thread(workspace.read_text, filename)


def get_safe_headers(url: str) -> dict[str, str]:
    pc_user_agents = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36 Edg/122.0.0.0",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:123.0) Gecko/20100101 Firefox/123.0",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.3 Safari/605.1.15",
    ]
    return {
        "User-Agent": random.choice(pc_user_agents),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        "Accept-Encoding": "gzip, deflate",
        "Referer": url,
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
    }


@tool
async def fetch_url(url: str, use_selenium: bool = False) -> dict[str, Any]:
    """获取网页内容并保存到 Docker 沙箱。

    use_selenium is deprecated and ignored; browser fetch runs inside the Docker
    sandbox via Playwright escalation.
    """
    del use_selenium

    try:
        headers = get_safe_headers(url)
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers, timeout=15) as response:
                final_url = str(response.url)
                if response.status >= 400:
                    response.raise_for_status()

                try:
                    text = await response.text()
                except UnicodeDecodeError:
                    text = await response.text(encoding="gbk", errors="ignore")

                workspace = get_sandbox_workspace()
                await asyncio.to_thread(workspace.write_text, "source_page.html", text)
                await asyncio.to_thread(
                    workspace.write_text,
                    "source_page.meta.json",
                    json.dumps({"url": final_url}, ensure_ascii=False),
                )
                sandbox_path = f"{workspace.display_path}/source_page.html"

                return {
                    "html_preview": text[:1000] + "... (完整内容已保存到沙箱)",
                    "html_file": "source_page.html",
                    "html_content": text,
                    "sandbox_path": sandbox_path,
                    "status_code": response.status,
                    "url": final_url,
                    "encoding": response.get_encoding(),
                    "success": True,
                    "error": None,
                }
    except Exception as exc:
        return {
            "html_preview": "",
            "html_file": "",
            "status_code": 0,
            "url": url,
            "success": False,
            "error": str(exc),
        }


@tool
async def analyze_html_structure(html: str = "", html_file: str = "", url: str = "") -> dict[str, Any] | str:
    """分析 HTML 结构，识别数据元素。"""
    try:
        content = html
        if not content and html_file:
            content = await _read_sandbox_file(html_file) or ""

        if not content:
            return {"success": False, "error": "No HTML content provided"}

        soup = BeautifulSoup(content, "lxml")
        title = soup.title.string if soup.title else ""
        all_tags = [tag.name for tag in soup.find_all()]
        tag_counter = Counter(all_tags)

        common_containers = []
        for tag in ["div", "article", "section", "li"]:
            elements = soup.find_all(tag, class_=True)
            for elem in elements[:5]:
                classes = " ".join(elem.get("class", []))
                if classes:
                    common_containers.append(
                        {
                            "tag": tag,
                            "class": classes,
                            "text_preview": elem.get_text()[:50].strip(),
                        }
                    )

        links = [
            {"href": anchor["href"], "text": anchor.get_text().strip()[:30]}
            for anchor in soup.find_all("a", href=True)[:10]
        ]
        images = [
            {"src": img["src"], "alt": img.get("alt", "")[:30]}
            for img in soup.find_all("img", src=True)[:10]
        ]

        return json.dumps(
            {
                "title": title,
                "url": url,
                "total_tags": len(all_tags),
                "tag_distribution": dict(tag_counter.most_common(10)),
                "links_count": len(soup.find_all("a")),
                "images_count": len(soup.find_all("img")),
                "common_containers": common_containers[:10],
                "sample_links": links,
                "sample_images": images,
                "has_pagination": bool(
                    soup.find_all(
                        ["a", "button"],
                        string=lambda value: value and ("next" in value.lower() or "下一页" in value),
                    )
                ),
                "success": True,
            }
        )
    except Exception as exc:
        return json.dumps(
            {
                "success": False,
                "error": str(exc),
                "traceback": traceback.format_exc(),
            }
        )


@tool
async def detect_anti_scraping(url: str, html: str = "", html_file: str = "") -> dict[str, Any]:
    """检测反爬虫机制。"""
    try:
        from app.spider.services.anti_scrape import classify_fetch_result

        content = html
        if not content and html_file:
            content = await _read_sandbox_file(html_file) or ""

        return classify_fetch_result(url=url, html=content or "")
    except Exception as exc:
        return {"success": False, "error": str(exc)}


@tool
async def validate_code_syntax(code: str) -> dict[str, Any]:
    """验证 Python 代码语法。"""
    try:
        cleaned_code = textwrap.dedent(code).strip()
        ast.parse(cleaned_code)
        return {"valid": True, "errors": [], "message": "代码语法正确"}
    except SyntaxError as exc:
        return {
            "valid": False,
            "errors": [{"line": exc.lineno, "message": exc.msg, "text": exc.text}],
            "message": f"语法错误: {exc.msg}",
        }
    except Exception as exc:
        return {"valid": False, "errors": [str(exc)], "message": f"验证失败: {str(exc)}"}


@tool
async def save_spider_code(code: str, filename: str = "spider.py") -> str:
    """保存爬虫代码到 Docker 沙箱。"""
    try:
        final_code = textwrap.dedent(code).strip()
        workspace = get_sandbox_workspace()
        await asyncio.to_thread(workspace.write_text, filename, final_code)
        return f"✅ 代码已成功保存到沙箱: {workspace.display_path}/{filename}"
    except Exception as exc:
        return f"❌ 保存代码失败: {str(exc)}"


@tool
async def parse_error(error_message: str, code: str = "") -> dict[str, Any]:
    """分析错误信息，提供修复建议。"""
    del code
    error_lower = error_message.lower()
    error_type = "Unknown"
    cause = ""
    suggestions: list[str] = []

    if any(keyword in error_lower for keyword in ["connection", "timeout", "network"]):
        error_type, cause = "NetworkError", "网络连接问题"
        suggestions = ["增加超时时间 (timeout=30)", "添加重试逻辑", "检查网络连接", "使用代理"]
    elif any(keyword in error_lower for keyword in ["parse", "beautifulsoup", "lxml"]):
        error_type, cause = "ParseError", "HTML 解析失败"
        suggestions = [
            "检查 HTML 内容是否完整",
            "尝试使用不同的解析器 (html.parser/lxml)",
            "检查选择器是否正确",
        ]
    elif any(keyword in error_lower for keyword in ["403", "forbidden", "401", "unauthorized"]):
        error_type, cause = "PermissionError", "访问被拒绝"
        suggestions = ["添加或更换 User-Agent", "添加 Cookie 或认证信息", "降低请求频率", "使用代理 IP"]
    elif "404" in error_lower:
        error_type, cause = "NotFoundError", "页面不存在"
        suggestions = ["检查 URL 是否正确", "检查页面是否已被删除或移动"]
    elif any(keyword in error_lower for keyword in ["encode", "decode", "unicode"]):
        error_type, cause = "EncodingError", "字符编码问题"
        suggestions = ["指定正确的编码 (utf-8/gbk)", "使用 errors='ignore' 忽略错误字符"]
    elif "import" in error_lower or "module" in error_lower:
        error_type, cause = "ImportError", "模块导入失败"
        suggestions = ["安装缺失的依赖包", "检查包名是否正确"]
    else:
        suggestions = ["检查代码逻辑", "添加异常处理", "查看完整的错误堆栈"]

    return {
        "error_type": error_type,
        "cause": cause,
        "suggestions": suggestions,
        "original_error": error_message[:500],
    }


@tool
async def clean_data(raw_data: str) -> str:
    """清洗数据：去除空值、格式化、去重。"""
    try:
        workspace = get_sandbox_workspace()
        data: Any

        if raw_data.endswith(".json") and await asyncio.to_thread(workspace.exists, raw_data):
            file_content = await asyncio.to_thread(workspace.read_text, raw_data)
            if file_content is None:
                raise ValueError(f"无法读取沙箱文件: {raw_data}")
            data = json.loads(file_content)
        elif isinstance(raw_data, str):
            data = json.loads(raw_data)
        else:
            data = raw_data

        if not isinstance(data, list):
            data = [data]

        cleaned: list[dict[str, Any]] = []
        seen: set[str] = set()
        for item in data:
            if not item:
                continue
            cleaned_item = {key: value for key, value in item.items() if value}
            item_str = json.dumps(cleaned_item, sort_keys=True)
            if item_str not in seen:
                seen.add(item_str)
                cleaned.append(cleaned_item)

        result_json = json.dumps(cleaned, ensure_ascii=False, indent=2)
        await asyncio.to_thread(workspace.write_text, "cleaned_data.json", result_json)
        return result_json
    except Exception as exc:
        return json.dumps({"error": str(exc)})


@tool
async def validate_data(data: str, required_fields: list[str] | None = None) -> dict[str, Any]:
    """验证数据完整性。"""
    try:
        data_list = json.loads(data) if isinstance(data, str) else data
        if not isinstance(data_list, list):
            data_list = [data_list]

        total_records = len(data_list)
        invalid_records = 0
        issues: list[dict[str, Any]] = []

        if required_fields:
            for index, item in enumerate(data_list):
                missing_fields = [field for field in required_fields if field not in item or not item[field]]
                if missing_fields:
                    invalid_records += 1
                    issues.append({"record_index": index, "missing_fields": missing_fields})

        return {
            "valid": invalid_records == 0,
            "total_records": total_records,
            "valid_records": total_records - invalid_records,
            "invalid_records": invalid_records,
            "issues": issues[:10],
        }
    except Exception as exc:
        return {"valid": False, "error": str(exc)}


SPIDER_TOOLS = [
    fetch_url,
    analyze_html_structure,
    detect_anti_scraping,
    save_spider_code,
    validate_code_syntax,
    parse_error,
    clean_data,
    validate_data,
]
