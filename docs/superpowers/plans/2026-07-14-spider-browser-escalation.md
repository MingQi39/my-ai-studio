# Spider HTTP→Playwright 分层升级 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Pipeline 默认 HTTP；命中 `js_render` / soft 失败后在现有 Docker 沙箱内升级为 Playwright 抓取与执行，并输出分级错误码；CAPTCHA/hard 不硬破。

**Architecture:** 抽出纯函数 `classify_fetch_result` 做反爬分级。Pipeline 持有 `fetch_mode` / `scrape_engine`；升级时沙箱运行 `playwright_fetch` 写 `source_page.html`，codegen/execute 切换到 Playwright（含 fallback：Playwright 渲染 + BeautifulSoup 解析）。最多一轮同会话升级；镜像缺 Playwright 时返回 `browser_image_unavailable`。

**Tech Stack:** FastAPI SSE Pipeline、Docker 沙箱（`SPIDER_DOCKER_IMAGE`）、Playwright sync API（仅沙箱）、aiohttp、pytest、BeautifulSoup

**Spec:** `docs/superpowers/specs/2026-07-14-spider-browser-escalation-design.md`

**推荐镜像（升级路径）:** `mcr.microsoft.com/playwright/python:v1.61.0-jammy`（文档与 `.env.example` 注释；默认值仍可 `python:3.11-slim`）

---

## File map

| File | Responsibility |
|------|----------------|
| `backend/app/spider/services/anti_scrape.py` | 纯函数分级 + 错误 hints 表 |
| `backend/app/spider/services/tools.py` | `detect_anti_scraping` 委托分级；`use_selenium` docstring 标明 unused |
| `backend/app/spider/services/browser_fetch.py` | 沙箱探针 + `playwright_fetch` 脚本内容/执行封装 |
| `backend/app/spider/services/sandbox.py` | Playwright 路径确保 bs4 依赖（解析仍用 BS） |
| `backend/app/spider/services/spider_pipeline_service.py` | 升级状态机、引擎分流 codegen/execute、错误码 |
| `backend/app/config.py` / `backend/.env.example` | 镜像注释与内存建议 |
| `backend/tests/spider/test_anti_scrape.py` | 分级单测 |
| `backend/tests/spider/test_browser_fetch.py` | 探针/脚本内容单测（mock backend） |
| `backend/tests/spider/test_fallback_playwright_template.py` | Playwright fallback AST + parse 契约 |
| `backend/tests/spider/test_pipeline_browser_escalation.py` | Pipeline 升级分支（mock fetch/sandbox） |

**非本版：** DeepAgent `agent_builder` 全路径对齐、Cookie/代理、前端强制开关、独立 browser worker。

---

### Task 1: 反爬分级纯函数（L0）

**Files:**
- Create: `backend/app/spider/services/anti_scrape.py`
- Create: `backend/tests/spider/test_anti_scrape.py`

- [ ] **Step 1: Write the failing tests**

```python
# backend/tests/spider/test_anti_scrape.py
from app.spider.services.anti_scrape import classify_fetch_result, hints_for_error_code


def test_classify_plain_list_html_is_none():
    html = "<html><body><div class='item'><span class='title'>A</span><a href='/1'>x</a></div></body></html>"
    result = classify_fetch_result(url="https://example.com/list", html=html, status_code=200)
    assert result["level"] == "none"
    assert result["escalate_to_browser"] is False
    assert result["block_hard"] is False


def test_classify_script_shell_is_js_render():
    scripts = "".join(f"<script>var x{i}=1;</script>" for i in range(20))
    html = f"<html><body>{scripts}<div></div></body></html>"
    result = classify_fetch_result(url="https://spa.example/", html=html, status_code=200)
    assert result["level"] == "js_render"
    assert result["escalate_to_browser"] is True
    assert "JavaScript Rendering" in result["detected_mechanisms"]


def test_classify_captcha_is_hard():
    html = "<html><body><div>请完成验证码 captcha</div></body></html>"
    result = classify_fetch_result(url="https://example.com/", html=html, status_code=200)
    assert result["level"] == "hard"
    assert result["block_hard"] is True
    assert result["escalate_to_browser"] is False


def test_classify_cloudflare_challenge_escalates():
    html = "<html><body>cloudflare just a moment checking your browser</body></html>"
    result = classify_fetch_result(url="https://example.com/", html=html, status_code=403)
    assert result["level"] == "js_render"
    assert result["escalate_to_browser"] is True


def test_classify_403_without_captcha_is_soft():
    result = classify_fetch_result(
        url="https://example.com/",
        html="<html><body>Forbidden</body></html>",
        status_code=403,
    )
    assert result["level"] == "soft"
    assert result["block_hard"] is False


def test_hints_for_known_codes():
    hints = hints_for_error_code("browser_image_unavailable")
    assert any(("镜像" in h) or ("Playwright" in h) or ("playwright" in h) for h in hints)
    assert hints_for_error_code("anti_scrape_hard")
    assert hints_for_error_code("unknown_xyz")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && .venv/bin/pytest tests/spider/test_anti_scrape.py -v`

Expected: FAIL（模块不存在）

- [ ] **Step 3: Implement `anti_scrape.py`**

```python
"""Classify fetch results for spider anti-scrape handling."""

from __future__ import annotations

from typing import Any

from bs4 import BeautifulSoup

_TEXT_THRESHOLD = 500
_CF_CHALLENGE_TOKENS = ("just a moment", "checking your browser", "cf-challenge", "attention required")
_CAPTCHA_TOKENS = ("captcha", "recaptcha", "验证码", "hcaptcha")

_ERROR_HINTS: dict[str, list[str]] = {
    "fetch_failed": [
        "检查目标网址是否可在浏览器正常打开",
        "确认本机网络可访问该域名",
        "若需 JS 渲染，将 SPIDER_DOCKER_IMAGE 换为 Playwright 镜像后重试",
    ],
    "anti_scrape_hard": [
        "目标页需要人工验证码，当前不支持自动绕过",
        "请换更开放的公开列表页，或稍后再试",
    ],
    "browser_image_unavailable": [
        "将 SPIDER_DOCKER_IMAGE 设为 mcr.microsoft.com/playwright/python:v1.61.0-jammy（或等价镜像）",
        "docker pull 该镜像后重启后端，并建议 SPIDER_DOCKER_MEMORY_LIMIT≥2g",
        "新会话会创建新容器；旧会话容器仍指向旧镜像时请新开会话",
    ],
    "browser_fetch_failed": [
        "浏览器沙箱抓取失败，检查目标站是否可访问",
        "适当增大超时后重试，或换静态列表页",
    ],
    "empty_scrape": [
        "把目标网址换成明确的列表页",
        "打开工作区 source_page.html / spider.py，核对选择器",
        "若页面强依赖登录或验证码，当前流水线无法完成",
    ],
    "execution_failed": [
        "查看沙箱运行输出定位异常",
        "小模型生成不稳时可换官方 API 模型",
    ],
}


def classify_fetch_result(
    *,
    url: str,
    html: str = "",
    status_code: int | None = None,
) -> dict[str, Any]:
    content = html or ""
    lowered = content.lower()
    mechanisms: list[str] = []
    recommendations: list[str] = []

    has_captcha = any(t in lowered for t in _CAPTCHA_TOKENS)
    if has_captcha:
        mechanisms.append("CAPTCHA")
        recommendations.append("需要人工验证；当前不自动绕过")
        return {
            "url": url,
            "level": "hard",
            "detected_mechanisms": mechanisms,
            "recommendations": recommendations,
            "escalate_to_browser": False,
            "block_hard": True,
            "has_anti_scraping": True,
            "success": True,
            "status_code": status_code,
        }

    cf = "cloudflare" in lowered
    cf_challenge = cf and any(t in lowered for t in _CF_CHALLENGE_TOKENS)
    if cf:
        mechanisms.append("Cloudflare")

    soup = BeautifulSoup(content, "lxml") if content else None
    visible = soup.get_text().strip() if soup else ""
    script_heavy = bool(soup and soup.find_all("script") and len(visible) < _TEXT_THRESHOLD)
    if script_heavy:
        mechanisms.append("JavaScript Rendering")
        recommendations.append("使用沙箱内 Playwright 渲染后再解析")

    if cf_challenge or script_heavy:
        return {
            "url": url,
            "level": "js_render",
            "detected_mechanisms": mechanisms,
            "recommendations": recommendations or ["使用 Playwright"],
            "escalate_to_browser": True,
            "block_hard": False,
            "has_anti_scraping": True,
            "success": True,
            "status_code": status_code,
        }

    soft_status = status_code in {401, 403, 429, 503}
    if soft_status:
        mechanisms.append(f"HTTP {status_code}")
        recommendations.extend(["稍后重试", "必要时升级 Playwright 再抓一次"])
        return {
            "url": url,
            "level": "soft",
            "detected_mechanisms": mechanisms,
            "recommendations": recommendations,
            "escalate_to_browser": False,
            "block_hard": False,
            "has_anti_scraping": True,
            "success": True,
            "status_code": status_code,
        }

    if not recommendations:
        recommendations = [
            "添加随机延迟 (1-3秒)",
            "使用随机 User-Agent",
            "设置合理的请求头",
        ]

    return {
        "url": url,
        "level": "none",
        "detected_mechanisms": mechanisms,
        "recommendations": recommendations,
        "escalate_to_browser": False,
        "block_hard": False,
        "has_anti_scraping": len(mechanisms) > 0,
        "success": True,
        "status_code": status_code,
    }


def hints_for_error_code(code: str) -> list[str]:
    return list(
        _ERROR_HINTS.get(code)
        or [
            "检查目标网址与网络",
            "查看会话工作区日志后重试",
        ]
    )
```

- [ ] **Step 4: Run tests — expect PASS**

Run: `cd backend && .venv/bin/pytest tests/spider/test_anti_scrape.py -v`

- [ ] **Step 5: Commit**

```bash
git add backend/app/spider/services/anti_scrape.py backend/tests/spider/test_anti_scrape.py
git commit -m "$(cat <<'EOF'
feat(spider): add anti-scrape classification helpers

EOF
)"
```

---

### Task 2: 接入 `detect_anti_scraping` + 废弃 `use_selenium` 说明

**Files:**
- Modify: `backend/app/spider/services/tools.py`
- Modify: `backend/tests/spider/test_anti_scrape.py`

- [ ] **Step 1: Write failing tool test**

```python
import pytest
from app.spider.services.tools import detect_anti_scraping


@pytest.mark.asyncio
async def test_detect_anti_scraping_returns_level_fields():
    html = "<html><body>请完成验证码 captcha</body></html>"
    result = await detect_anti_scraping.ainvoke({"url": "https://x.test", "html": html})
    assert result["success"] is True
    assert result["level"] == "hard"
    assert result["block_hard"] is True
    assert "has_anti_scraping" in result
```

- [ ] **Step 2: Run — expect FAIL**（缺 `level`）

Run: `cd backend && .venv/bin/pytest tests/spider/test_anti_scrape.py::test_detect_anti_scraping_returns_level_fields -v`

- [ ] **Step 3: Implement**

在 `detect_anti_scraping` 内读取 html/html_file 后调用 `classify_fetch_result`，返回其字典（保留异常时 `success/error` 分支）。

`fetch_url` 保留 `use_selenium` 参数，docstring 改为：`use_selenium is deprecated and ignored; browser fetch runs inside the Docker sandbox via Playwright escalation.`

- [ ] **Step 4: Run tests PASS**

Run: `cd backend && .venv/bin/pytest tests/spider/test_anti_scrape.py -v`

- [ ] **Step 5: Commit**

```bash
git add backend/app/spider/services/tools.py backend/tests/spider/test_anti_scrape.py
git commit -m "$(cat <<'EOF'
feat(spider): wire detect_anti_scraping to classify_fetch_result

EOF
)"
```

---

### Task 3: 沙箱 Playwright 探针与 fetch 封装

**Files:**
- Create: `backend/app/spider/services/browser_fetch.py`
- Create: `backend/tests/spider/test_browser_fetch.py`

- [ ] **Step 1: Write failing tests**

```python
# backend/tests/spider/test_browser_fetch.py
from types import SimpleNamespace

from app.spider.services.browser_fetch import (
    PLAYWRIGHT_FETCH_SCRIPT,
    probe_playwright_available,
    run_playwright_fetch,
)


def test_playwright_fetch_script_writes_source_page():
    assert "sync_playwright" in PLAYWRIGHT_FETCH_SCRIPT
    assert "source_page.html" in PLAYWRIGHT_FETCH_SCRIPT
    assert "headless" in PLAYWRIGHT_FETCH_SCRIPT.lower()


def test_probe_playwright_available_true():
    backend = SimpleNamespace(execute=lambda cmd: SimpleNamespace(exit_code=0, output="ok"))
    workspace = SimpleNamespace(backend=backend)
    assert probe_playwright_available(workspace) is True


def test_probe_playwright_available_false():
    backend = SimpleNamespace(execute=lambda cmd: SimpleNamespace(exit_code=1, output="No module"))
    workspace = SimpleNamespace(backend=backend)
    assert probe_playwright_available(workspace) is False


def test_run_playwright_fetch_success():
    writes: dict[str, str] = {}

    class WS:
        backend = SimpleNamespace(
            execute=lambda cmd: SimpleNamespace(exit_code=0, output="fetched"),
            working_dir="/workspace",
        )

        def write_text(self, name, text):
            writes[name] = text

        def read_text(self, name):
            if name == "source_page.html":
                return "<html>ok</html>"
            if name == "source_page.meta.json":
                return '{"url": "https://example.com", "fetch_mode": "playwright"}'
            return None

    result = run_playwright_fetch(WS(), "https://example.com")
    assert result["success"] is True
    assert "playwright_fetch.py" in writes
    assert result["html_file"] == "source_page.html"
```

- [ ] **Step 2: Run — expect FAIL**

Run: `cd backend && .venv/bin/pytest tests/spider/test_browser_fetch.py -v`

- [ ] **Step 3: Implement `browser_fetch.py`**

要点：

- `PLAYWRIGHT_FETCH_SCRIPT`：`sync_playwright`；`chromium.launch(headless=True)`；从 `sys.argv[1]` 读 URL（避免 shell 注入）；`goto(..., wait_until="domcontentloaded", timeout=45000)`；写 `source_page.html`；写 `source_page.meta.json`（含 `fetch_mode: "playwright"`）。
- `probe_playwright_available(workspace) -> bool`：执行  
  `python -c "from playwright.sync_api import sync_playwright; print('ok')"`。
- `run_playwright_fetch(workspace, url) -> dict`：写入 `playwright_fetch.py`；`backend.execute` 用 list 不可用时，对 URL 做 `shlex.quote` 后：  
  `cd {working_dir} && python playwright_fetch.py {quoted_url}`；  
  返回 `{success, html_file, error, output_preview}`。

- [ ] **Step 4: Run PASS**

Run: `cd backend && .venv/bin/pytest tests/spider/test_browser_fetch.py -v`

- [ ] **Step 5: Commit**

```bash
git add backend/app/spider/services/browser_fetch.py backend/tests/spider/test_browser_fetch.py
git commit -m "$(cat <<'EOF'
feat(spider): add sandbox playwright probe and fetch helper

EOF
)"
```

---

### Task 4: Playwright fallback 爬虫模板

**Files:**
- Modify: `backend/app/spider/services/spider_pipeline_service.py`（新增 `_fallback_playwright_spider_code`）
- Create: `backend/tests/spider/test_fallback_playwright_template.py`

- [ ] **Step 1: Write failing tests**

```python
import ast

from app.spider.services.spider_pipeline_service import _fallback_playwright_spider_code


def test_fallback_playwright_template_is_valid_python():
    code = _fallback_playwright_spider_code("https://example.com/list", limit=5)
    ast.parse(code)
    assert "sync_playwright" in code
    assert "BeautifulSoup" in code
    assert "scraped_data.json" in code
    assert "https://example.com/list" in code
    assert "requests.Session" not in code
```

- [ ] **Step 2: Run — expect FAIL**

Run: `cd backend && .venv/bin/pytest tests/spider/test_fallback_playwright_template.py -v`

- [ ] **Step 3: Implement `_fallback_playwright_spider_code`**

结构要求：

- `TARGET_URL` / `LIMIT` 常量
- `with sync_playwright() as p:` → `chromium.launch(headless=True)` → `page.goto` → `html = page.content()`
- 解析复用 BS 模板同款选择器逻辑（允许内联精简版；若抽公共片段必须跑通原 `test_fallback_template.py`）
- `main() -> int`；0 条写 `[]` 且 exit 1

- [ ] **Step 4: Run PASS + 回归 BS 模板**

Run: `cd backend && .venv/bin/pytest tests/spider/test_fallback_playwright_template.py tests/spider/test_fallback_template.py -v`

- [ ] **Step 5: Commit**

```bash
git add backend/app/spider/services/spider_pipeline_service.py backend/tests/spider/test_fallback_playwright_template.py
git commit -m "$(cat <<'EOF'
feat(spider): add playwright fallback spider template

EOF
)"
```

---

### Task 5: Codegen / execute 按 `scrape_engine` 分流

**Files:**
- Modify: `backend/app/spider/services/spider_pipeline_service.py`
- Modify: `backend/app/spider/services/sandbox.py`
- Modify: `backend/tests/spider/test_fallback_template.py`

- [ ] **Step 1: Write failing test**

```python
@pytest.mark.asyncio
async def test_execute_retry_playwright_engine_does_not_fall_back_to_requests():
    from types import SimpleNamespace
    from app.spider.services.spider_pipeline_service import _execute_spider_with_retry

    workspace = SimpleNamespace(read_text=lambda name: "print('x')\n", write_text=lambda *a, **k: None)
    llm_fail = {"success": False, "error": "boom", "exit_code": 1, "data_saved": False}
    template_ok = {
        "success": True,
        "exit_code": 0,
        "data_saved": True,
        "record_count": 1,
        "output_preview": "ok",
    }
    calls: list[str] = []

    async def execute_in_sandbox(code: str, timeout: int = 60):
        calls.append(code)
        if "sync_playwright" in code:
            return template_ok
        return llm_fail

    result, source = await _execute_spider_with_retry(
        execute_in_sandbox=execute_in_sandbox,
        workspace=workspace,
        llm_api_key="k",
        llm_base_url="http://x",
        model_name="m",
        target_url="https://example.com",
        code_source="llm",
        scrape_engine="playwright",
    )
    assert source == "template"
    assert result["success"] is True
    assert any("sync_playwright" in c for c in calls)
```

- [ ] **Step 2: Run — expect FAIL**

- [ ] **Step 3: Implement**

1. `_generate_spider_code(..., scrape_engine: str = "requests")`：`playwright` 时用同步 Playwright system 约束（spec §5.2）。
2. `_generate_spider_code_with_retry` 透传 `scrape_engine`；template 回退到对应 fallback。
3. `_execute_spider_with_retry(..., scrape_engine="requests")`：按引擎选 fallback；**playwright 不得回退 requests**。
4. `sandbox.execute_in_sandbox`：继续确保 `requests`/`beautifulsoup4`/`lxml`；**不要**在容器内 `playwright install`（镜像预制浏览器）。

- [ ] **Step 4: Run PASS**

Run: `cd backend && .venv/bin/pytest tests/spider/test_fallback_template.py tests/spider/test_fallback_playwright_template.py -v`

- [ ] **Step 5: Commit**

```bash
git add backend/app/spider/services/spider_pipeline_service.py backend/app/spider/services/sandbox.py backend/tests/spider/test_fallback_template.py
git commit -m "$(cat <<'EOF'
feat(spider): branch codegen and execute by scrape_engine

EOF
)"
```

---

### Task 6: Pipeline 升级状态机（分析阶段）

**Files:**
- Modify: `backend/app/spider/services/spider_pipeline_service.py`
- Create: `backend/tests/spider/test_pipeline_browser_escalation.py`

- [ ] **Step 1: Write failing decision tests**

```python
from app.spider.services.spider_pipeline_service import decide_initial_fetch_mode


def test_decide_block_hard():
    assert decide_initial_fetch_mode({"block_hard": True}, http_success=True) == "block_hard"


def test_decide_escalate_js_render():
    assert (
        decide_initial_fetch_mode({"escalate_to_browser": True, "block_hard": False}, True)
        == "playwright"
    )


def test_decide_http_fail_escalates():
    assert (
        decide_initial_fetch_mode({"block_hard": False, "escalate_to_browser": False}, False)
        == "playwright"
    )


def test_decide_http_ok_none():
    assert (
        decide_initial_fetch_mode(
            {"block_hard": False, "escalate_to_browser": False, "level": "none"},
            True,
        )
        == "http"
    )
```

- [ ] **Step 2: Implement `decide_initial_fetch_mode` → PASS**

- [ ] **Step 3: 接入 `spider_pipeline_stream` 分析段**

```text
fetch_result = await fetch_url(...)
html = fetch_result.get("html_content") or ""
anti = classify_fetch_result(url=..., html=html, status_code=fetch_result.get("status_code"))

mode = decide_initial_fetch_mode(anti, http_success=bool(fetch_result.get("success")))
if mode == "block_hard":
    yield error anti_scrape_hard + hints_for_error_code(...)
    return

scrape_engine = "requests"
fetch_mode = "http"
if mode == "playwright":
    if not probe_playwright_available(workspace):
        yield error browser_image_unavailable
        return
    pw = run_playwright_fetch(workspace, resolved_url)
    if not pw["success"]:
        yield browser_fetch_failed 或 fetch_failed
        return
    # 用渲染后 HTML 再 classify；若 hard → anti_scrape_hard
    fetch_mode = "playwright"
    scrape_engine = "playwright"

# analysis_report.json 含 anti + fetch_mode + scrape_engine + escalation_reason
# codegen/execute 传入 scrape_engine
# 相关 _error_event 使用 hints_for_error_code(code)
```

- [ ] **Step 4: Mock 流式用例**

- HTTP success + none → `run_playwright_fetch` 调用 0 次  
- escalate + probe False → `code=browser_image_unavailable`  
- escalate + probe True → `_generate_spider_code_with_retry` 收到 `scrape_engine=="playwright"`

- [ ] **Step 5: Run**

Run: `cd backend && .venv/bin/pytest tests/spider/test_pipeline_browser_escalation.py tests/spider/test_anti_scrape.py -v`

- [ ] **Step 6: Commit**

```bash
git add backend/app/spider/services/spider_pipeline_service.py backend/tests/spider/test_pipeline_browser_escalation.py
git commit -m "$(cat <<'EOF'
feat(spider): escalate pipeline fetch to sandbox playwright

EOF
)"
```

---

### Task 7: 同轮 soft 空爬取升级（最多一轮）

**Files:**
- Modify: `backend/app/spider/services/spider_pipeline_service.py`
- Modify: `backend/tests/spider/test_pipeline_browser_escalation.py`

- [ ] **Step 1: Write failing test**

```python
from app.spider.services.spider_pipeline_service import should_escalate_after_empty_scrape


def test_should_escalate_after_empty_scrape():
    assert should_escalate_after_empty_scrape(
        scrape_engine="requests", anti_level="soft", already_escalated=False
    )
    assert not should_escalate_after_empty_scrape(
        scrape_engine="requests", anti_level="none", already_escalated=False
    )
    assert not should_escalate_after_empty_scrape(
        scrape_engine="playwright", anti_level="soft", already_escalated=False
    )
    assert not should_escalate_after_empty_scrape(
        scrape_engine="requests", anti_level="soft", already_escalated=True
    )
    assert should_escalate_after_empty_scrape(
        scrape_engine="requests", anti_level="js_render", already_escalated=False
    )
```

- [ ] **Step 2: Implement helper + pipeline 分支**

debug_agent 判定 `empty_scrape` 时：

```text
if should_escalate_after_empty_scrape(...):
    already_escalated = True
    probe → playwright_fetch → re-classify（hard 则停）
    scrape_engine = playwright
    重新 codegen + save + execute
    仍失败 → empty_scrape / execution_failed
else:
    现有失败路径
```

Todo：失败仍在 index 2；升级成功则继续推进。禁止第二轮升级。

- [ ] **Step 3: Run PASS**

Run: `cd backend && .venv/bin/pytest tests/spider/test_pipeline_browser_escalation.py -v`

- [ ] **Step 4: Commit**

```bash
git add backend/app/spider/services/spider_pipeline_service.py backend/tests/spider/test_pipeline_browser_escalation.py
git commit -m "$(cat <<'EOF'
feat(spider): allow one soft empty-scrape browser escalation

EOF
)"
```

---

### Task 8: 配置与文档注释

**Files:**
- Modify: `backend/.env.example`
- Modify: `backend/app/config.py`

- [ ] **Step 1: Update `.env.example`**

```bash
# Spider Agent (DeepAgents, Docker named volume sandbox)
SPIDER_CONTAINER_MOUNT_PATH=/workspace
# Default slim is fine for static HTTP pages.
# For JS-render escalation use e.g. mcr.microsoft.com/playwright/python:v1.61.0-jammy
SPIDER_DOCKER_IMAGE=python:3.11-slim
# Playwright path works more reliably at >=2g
SPIDER_DOCKER_MEMORY_LIMIT=1g
SPIDER_DOCKER_CPU_QUOTA=100000
```

- [ ] **Step 2: 在 `config.py` 对应字段旁加同样说明注释**

- [ ] **Step 3: Commit**

```bash
git add backend/.env.example backend/app/config.py
git commit -m "$(cat <<'EOF'
docs(spider): document playwright docker image for browser escalation

EOF
)"
```

---

### Task 9: 全量回归 + 手工清单

- [ ] **Step 1: Run spider 单测包**

Run: `cd backend && .venv/bin/pytest tests/spider/ -v`

Expected: 全部 PASS

- [ ] **Step 2: 手工验证清单（本地，非 CI）**

1. 默认 `python:3.11-slim`：静态列表页（如豆瓣 Top250）仍走 HTTP 成功。
2. 换 Playwright 镜像并 `docker pull` 后 **新开会话**：JS 壳页应出现浏览器升级（工作区有 `playwright_fetch.py` 或 meta `fetch_mode=playwright`）。
3. 验证码页：`anti_scrape_hard`。
4. slim 镜像下触发升级：`browser_image_unavailable` hints 可读。

- [ ] **Step 3: 仅当有未提交改动时再收尾 commit**

---

## Spec coverage checklist

| Spec 项 | Task |
|---------|------|
| 分级 `none/soft/hard/js_render` | Task 1–2 |
| 错误码 hints | Task 1 + 6 |
| 沙箱 Playwright | Task 3 |
| 探针 / `browser_image_unavailable` | Task 3 + 6 |
| 分析+执行一并升级 | Task 5–6 |
| Playwright codegen + fallback | Task 4–5 |
| HTTP 失败升级一次 | Task 6 |
| soft 空爬取同轮升级一轮 | Task 7 |
| hard 不硬破 | Task 1 + 6 |
| Cookie/代理/DeepAgent 非目标 | 无 task |
| `.env` 镜像文档 | Task 8 |

## Placeholder / consistency review

- `scrape_engine` ∈ `{requests, playwright}`；`fetch_mode` ∈ `{http, playwright}`；决策 ∈ `{http, playwright, block_hard}`。
- 镜像 tag 锁定 `v1.61.0-jammy`。
- 无 TBD；前端强制开关未列入。
