# Spider Codegen 导入守卫 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在进沙箱前用 AST 导入白名单拦住 LLM 幻觉导入（如 `from playwright.sync_api import Soup`），并收紧 codegen / fix prompt。

**Architecture:** 新增纯函数 `validate_spider_imports`（独立模块便于单测）；`_validate_python_code` 组合语法 + 导入校验；`_generate_spider_code_with_retry` 传入 `scrape_engine`；Playwright / requests prompt 与 runtime fix 对齐导入规则。

**Tech Stack:** Python `ast`、pytest、现有 `spider_pipeline_service` codegen 路径

**Spec:** `docs/superpowers/specs/2026-07-14-spider-codegen-import-guard-design.md`

---

## File map

| File | Responsibility |
|------|----------------|
| `backend/app/spider/services/code_guards.py` | `validate_spider_imports(code, *, scrape_engine)` 纯函数 |
| `backend/app/spider/services/spider_pipeline_service.py` | 接线校验；收紧 prompt；fix 路径带上导入错误 message |
| `backend/tests/spider/test_codegen_import_guard.py` | 白名单 / 幻觉导入 / template 契约单测 |

**非本版：** 沙箱镜像、依赖扫描、新 pipeline 阶段。

---

### Task 1: `validate_spider_imports` 纯函数（TDD）

**Files:**
- Create: `backend/app/spider/services/code_guards.py`
- Create: `backend/tests/spider/test_codegen_import_guard.py`

- [ ] **Step 1: Write the failing tests**

```python
# backend/tests/spider/test_codegen_import_guard.py
from app.spider.services.code_guards import validate_spider_imports
from app.spider.services.spider_pipeline_service import _fallback_playwright_spider_code


def test_rejects_soup_from_playwright_sync_api():
    code = (
        "from playwright.sync_api import sync_playwright, Browser, Page, Soup\n"
        "from bs4 import BeautifulSoup\n"
    )
    result = validate_spider_imports(code, scrape_engine="playwright")
    assert result["valid"] is False
    assert "Soup" in result["message"]


def test_accepts_sync_playwright_and_beautifulsoup():
    code = (
        "from playwright.sync_api import sync_playwright\n"
        "from bs4 import BeautifulSoup\n"
        "import json\n"
    )
    result = validate_spider_imports(code, scrape_engine="playwright")
    assert result["valid"] is True


def test_requests_engine_rejects_playwright_import():
    code = (
        "import requests\n"
        "from bs4 import BeautifulSoup\n"
        "from playwright.sync_api import sync_playwright\n"
    )
    result = validate_spider_imports(code, scrape_engine="requests")
    assert result["valid"] is False
    assert "playwright" in result["message"].lower()


def test_fallback_playwright_template_passes():
    code = _fallback_playwright_spider_code("https://example.com", limit=5)
    result = validate_spider_imports(code, scrape_engine="playwright")
    assert result["valid"] is True
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && python -m pytest tests/spider/test_codegen_import_guard.py -v`

Expected: FAIL with `ModuleNotFoundError` / `ImportError` for `code_guards`

- [ ] **Step 3: Implement `code_guards.py`**

```python
# backend/app/spider/services/code_guards.py
"""AST-based import allowlists for LLM-generated spider scripts."""
from __future__ import annotations

import ast
import textwrap
from typing import Any

_BS4_ALLOWED = frozenset({"BeautifulSoup", "Tag"})
_PLAYWRIGHT_SYNC_ALLOWED = frozenset({"sync_playwright"})
_STDLIB_ROOTS = frozenset(
    {
        "json",
        "logging",
        "os",
        "random",
        "re",
        "sys",
        "time",
        "typing",
        "urllib",
        "pathlib",
        "collections",
        "datetime",
        "hashlib",
        "html",
        "io",
        "math",
        "copy",
        "dataclasses",
        "enum",
        "functools",
        "itertools",
        "operator",
        "string",
        "tempfile",
        "traceback",
        "uuid",
        "warnings",
        "base64",
        "csv",
        "textwrap",
    }
)


def validate_spider_imports(code: str, *, scrape_engine: str) -> dict[str, Any]:
    cleaned = textwrap.dedent(code).strip()
    try:
        tree = ast.parse(cleaned)
    except SyntaxError as exc:
        return {
            "valid": False,
            "errors": [{"line": exc.lineno, "message": exc.msg, "text": exc.text}],
            "message": f"语法错误: {exc.msg}",
        }

    errors: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                errors.extend(_check_import_name(alias.name, scrape_engine=scrape_engine))
        elif isinstance(node, ast.ImportFrom):
            errors.extend(_check_import_from(node, scrape_engine=scrape_engine))

    if errors:
        return {
            "valid": False,
            "errors": errors,
            "message": "非法导入: " + "; ".join(errors),
        }
    return {"valid": True, "errors": [], "message": "导入校验通过"}


def _check_import_name(mod: str, *, scrape_engine: str) -> list[str]:
    root = mod.split(".", 1)[0]
    if root == "Soup" or mod == "Soup":
        return ["禁止 import Soup（请用 from bs4 import BeautifulSoup）"]
    if root in {"playwright", "selenium"}:
        if scrape_engine == "requests":
            return [f"requests 引擎禁止导入 {mod}"]
        if root == "playwright":
            return [
                "禁止 import playwright；请用 from playwright.sync_api import sync_playwright"
            ]
        return [f"禁止导入 {mod}"]
    if root == "requests":
        return []
    if root == "bs4":
        return ["请用 from bs4 import BeautifulSoup，不要 import bs4"]
    if root in _STDLIB_ROOTS:
        return []
    # Allow unknown third-party only if already used in templates? Be strict: reject unknowns
    # except common spider helpers already in sandbox.
    if root in {"lxml", "httpx", "aiohttp"}:
        if root in {"httpx", "aiohttp"} and scrape_engine == "requests":
            return [f"requests 引擎禁止 {root}（保持同步 requests）"]
        if root == "aiohttp":
            return ["禁止 aiohttp（必须同步）"]
        return []
    return [f"不允许的模块: {mod}"]


def _check_import_from(node: ast.ImportFrom, *, scrape_engine: str) -> list[str]:
    if node.module is None:
        return ["不支持相对导入"]
    mod = node.module
    names = [a.name for a in node.names]
    errs: list[str] = []

    if "Soup" in names:
        errs.append("禁止导入 Soup（请用 from bs4 import BeautifulSoup）")

    if mod == "bs4" or mod.startswith("bs4."):
        bad = [n for n in names if n != "*" and n not in _BS4_ALLOWED]
        if "*" in names:
            errs.append("禁止 from bs4 import *")
        if bad:
            errs.append(f"bs4 仅允许 {_BS4_ALLOWED}，禁止: {bad}")
        return errs

    if mod.startswith("playwright") or mod == "selenium" or mod.startswith("selenium."):
        if scrape_engine == "requests":
            errs.append(f"requests 引擎禁止导入 {mod}")
            return errs
        if mod != "playwright.sync_api":
            errs.append(
                "Playwright 仅允许 from playwright.sync_api import sync_playwright"
            )
            return errs
        bad = [n for n in names if n != "*" and n not in _PLAYWRIGHT_SYNC_ALLOWED]
        if "*" in names:
            errs.append("禁止 from playwright.sync_api import *")
        if bad:
            errs.append(
                f"playwright.sync_api 仅允许 {_PLAYWRIGHT_SYNC_ALLOWED}，禁止: {bad}"
            )
        return errs

    if mod == "requests" or mod.startswith("requests."):
        return errs

    root = mod.split(".", 1)[0]
    if root in _STDLIB_ROOTS:
        return errs
    if root in {"lxml"}:
        return errs
    if root in {"aiohttp", "httpx"}:
        errs.append(f"禁止导入 {mod}（保持同步）")
        return errs

    errs.append(f"不允许的模块: {mod}")
    return errs
```

Note: 若 `_fallback_spider_code` 使用的 stdlib/第三方超出名单，Step 4 应用 template 跑一遍并补白名单，避免误杀 template。

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && python -m pytest tests/spider/test_codegen_import_guard.py -v`

Expected: 4 passed

- [ ] **Step 5: Commit**（仅在用户要求时执行；本会话默认跳过 commit）

```bash
git add backend/app/spider/services/code_guards.py backend/tests/spider/test_codegen_import_guard.py
git commit -m "$(cat <<'EOF'
feat(spider): add AST import allowlist for codegen scripts

EOF
)"
```

---

### Task 2: 接线 `_validate_python_code` + retry fix message

**Files:**
- Modify: `backend/app/spider/services/spider_pipeline_service.py`
- Modify: `backend/tests/spider/test_codegen_import_guard.py`（可选：测试组合校验入口）

- [ ] **Step 1: 改 `_validate_python_code` 接受 `scrape_engine`**

定位现有：

```python
async def _validate_python_code(code: str) -> dict[str, Any]:
    return await validate_code_syntax.ainvoke({"code": code})
```

改为：

```python
async def _validate_python_code(
    code: str, *, scrape_engine: str = "requests"
) -> dict[str, Any]:
    from app.spider.services.code_guards import validate_spider_imports

    syntax = await validate_code_syntax.ainvoke({"code": code})
    if not syntax.get("valid"):
        return syntax
    return validate_spider_imports(code, scrape_engine=scrape_engine)
```

- [ ] **Step 2: 更新 `_generate_spider_code_with_retry` 调用点**

两处 `await _validate_python_code(code)` / `await _validate_python_code(fixed)` 改为传入 `scrape_engine=scrape_engine`。

修复 SystemMessage 带上首次失败原因：

```python
    syntax = await _validate_python_code(code, scrape_engine=scrape_engine)
    if syntax.get("valid"):
        return code, "llm"

    llm = ChatOpenAI(...)
    fix = await llm.ainvoke(
        [
            SystemMessage(
                content=(
                    "修复以下 Python 爬虫代码的语法或导入错误。"
                    "只输出完整可运行代码，不要解释，不要使用全角标点。\n"
                    f"校验失败原因: {syntax.get('message', '')}\n"
                    "Playwright 路径仅允许: from playwright.sync_api import sync_playwright；"
                    "解析用 from bs4 import BeautifulSoup。禁止从 playwright 导入 Soup/Browser/Page。"
                )
            ),
            HumanMessage(content=code),
        ]
    )
```

二次校验同样 `scrape_engine=`。

搜索文件内其它 `_validate_python_code(` 调用并补齐参数。

- [ ] **Step 3: 加组合校验单测（同步函数路径即可）**

在 `test_codegen_import_guard.py` 追加对 `validate_spider_imports` 与 template 的覆盖已足够；若有同步包装则再测。**不要**在单测里打真 LLM。

- [ ] **Step 4: Run regression**

Run:

```bash
cd backend && python -m pytest tests/spider/test_codegen_import_guard.py tests/spider/test_fallback_playwright_template.py tests/spider/test_fallback_template.py -v
```

Expected: all pass

- [ ] **Step 5: Commit**（用户要求时再执行）

---

### Task 3: 收紧 codegen / runtime-fix prompts

**Files:**
- Modify: `backend/app/spider/services/spider_pipeline_service.py` — `_codegen_system_prompt`、`_fix_runtime_spider_code`

- [ ] **Step 1: Playwright `_codegen_system_prompt` 追加硬性导入条款**

在现有 Playwright 分支 `要求：` 列表中，于 sync Playwright 那条之后插入：

```python
            "- 合法导入示例（照抄）：from playwright.sync_api import sync_playwright；"
            "from bs4 import BeautifulSoup\n"
            "- 禁止从 playwright / playwright.sync_api 导入 Soup、BeautifulSoup、Browser、Page；"
            "禁止 import playwright\n"
            "- 可用 BeautifulSoup 解析 page.content() 返回的 HTML\n"
```

删除或合并旧的宽松一句「可用 BeautifulSoup…」避免重复（保留一条即可）。

- [ ] **Step 2: requests 分支追加**

```python
            "- 禁止导入 playwright / selenium；解析只用 from bs4 import BeautifulSoup\n"
```

- [ ] **Step 3: `_fix_runtime_spider_code` playwright `constraints` 追加**

```python
            "- 合法导入: from playwright.sync_api import sync_playwright 与 "
            "from bs4 import BeautifulSoup；禁止 Soup/Browser/Page 从 playwright 导入\n"
```

- [ ] **Step 4: 快速 grep 确认**

Run: `rg -n "Soup|合法导入|validate_spider_imports" backend/app/spider/services/`

Expected: prompt 与 `code_guards` / 接线均有命中

- [ ] **Step 5: 全量相关测试**

Run: `cd backend && python -m pytest tests/spider/ -v --tb=short -q`

Expected: pass（或仅与本改动无关的既有失败——若有，记录但不在本任务范围「修无关 flaky」）

---

## Spec coverage checklist

| Spec 项 | Task |
|---------|------|
| Prompt 收紧（PW / fix / requests） | Task 3 |
| `validate_spider_imports` API | Task 1 |
| 组合 syntax + imports | Task 2 |
| retry → llm_fixed → template | Task 2（现有路径，传入 scrape_engine） |
| 测试 Soup 拒绝 / 合法通过 / requests 拒 PW / template 通过 | Task 1 |

## 执行手顺

实现时严格 TDD：Task1 → Task2 → Task3。不要先扩白名单「以防万一」——以 template + 单测失败为准再放行。
