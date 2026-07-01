"""Built-in handlers for main chat tools."""

from __future__ import annotations

import io
import json
import math
import re
import contextlib
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from app.config import settings
from app.travel.services.tavily_client import TavilyClient

CHAT_TZ = ZoneInfo("Asia/Shanghai")
_YEAR_RE = re.compile(r"\b(20\d{2})\b")
_RELATIVE_TODAY = ("今天", "今日", "today")


def chat_today() -> datetime:
    """Current date/time in the default chat timezone (Asia/Shanghai)."""
    return datetime.now(CHAT_TZ)


def today_date_hint() -> str:
    """Human-readable date string for system prompts."""
    return chat_today().strftime("%Y-%m-%d")


def normalize_search_query(query: str, *, now: datetime | None = None) -> str:
    """Fix stale years and enrich date-relative search queries."""
    now = now or chat_today()
    year = now.year
    q = query.strip()
    if not q:
        return q

    lower = q.casefold()
    has_today = any(k in lower for k in _RELATIVE_TODAY)

    if has_today:
        def _fix_year(match: re.Match[str]) -> str:
            y = int(match.group(1))
            return str(year) if y < year else match.group(1)

        q = _YEAR_RE.sub(_fix_year, q)
        if str(year) not in q:
            q = f"{now.strftime('%Y-%m-%d')} {q}"

    return q


async def web_search_handler(query: str) -> str:
    """Web search via Tavily (Google Search UI toggle)."""
    if not settings.TAVILY_API_KEY:
        return json.dumps(
            {"error": "未配置 TAVILY_API_KEY，请在服务端 .env 中设置以启用联网搜索"},
            ensure_ascii=False,
        )

    normalized = normalize_search_query(query)
    client = TavilyClient(
        settings.TAVILY_API_KEY,
        timeout=settings.HTTP_TIMEOUT_SECONDS,
        max_results=settings.TAVILY_MAX_RESULTS,
    )
    try:
        results = await client.search(normalized)
    except Exception as exc:  # noqa: BLE001
        return json.dumps({"error": f"搜索失败: {exc}"}, ensure_ascii=False)

    payload: dict = {
        "query": normalized,
        "results": results,
        "source": "tavily",
        "today": today_date_hint(),
    }
    if normalized != query.strip():
        payload["original_query"] = query
    return json.dumps(payload, ensure_ascii=False)


async def execute_python_handler(code: str) -> str:
    """Run Python in a restricted sandbox (stdout capture)."""
    safe_globals = {
        "__builtins__": {},
        "print": print,
        "math": math,
        "datetime": datetime,
    }
    stdout = io.StringIO()

    def _capture_print(*args, **kwargs):
        sep = kwargs.get("sep", " ")
        end = kwargs.get("end", "\n")
        stdout.write(sep.join(str(a) for a in args) + end)

    safe_globals["print"] = _capture_print

    try:
        with contextlib.redirect_stdout(stdout):
            exec(code, safe_globals, {})  # noqa: S102
        output = stdout.getvalue().strip()
        return json.dumps(
            {"success": True, "stdout": output, "code": code},
            ensure_ascii=False,
        )
    except Exception as exc:  # noqa: BLE001
        return json.dumps(
            {"success": False, "error": str(exc), "code": code},
            ensure_ascii=False,
        )


async def calculate_handler(expression: str) -> str:
    """Safe math expression evaluation."""
    allowed_chars = set("0123456789+-*/()., ")
    if not all(c in allowed_chars for c in expression):
        return json.dumps({"error": "表达式包含非法字符"}, ensure_ascii=False)
    try:
        result = eval(expression, {"__builtins__": {}}, {})  # noqa: S307
        return json.dumps({"expression": expression, "result": result}, ensure_ascii=False)
    except Exception as exc:  # noqa: BLE001
        return json.dumps({"error": f"计算失败: {exc}"}, ensure_ascii=False)


async def get_current_time_handler() -> str:
    """Return current UTC time."""
    now = datetime.now(timezone.utc)
    return json.dumps(
        {
            "utc": now.isoformat(),
            "timestamp": int(now.timestamp()),
        },
        ensure_ascii=False,
    )
