# Spider Visitor Wall Hard Fail Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Detect login/visitor walls as `anti_scrape_hard` before Playwright escalation, and classify “saved 0 records” failures as `empty_scrape` instead of `execution_failed`.

**Architecture:** Extend `classify_fetch_result` with visitor/login tokens checked before `js_render` heuristics. Extract `is_empty_scrape_result` used by the pipeline so exit≠0 + empty `scraped_data.json` maps to `empty_scrape`. Reuse existing `anti_scrape_hard` error path; no new error codes.

**Tech Stack:** Python 3, pytest, existing spider pipeline / anti_scrape module

**Spec:** [`docs/superpowers/specs/2026-07-14-spider-visitor-wall-hard-fail-design.md`](../specs/2026-07-14-spider-visitor-wall-hard-fail-design.md)

---

## File map

| File | Responsibility |
|---|---|
| `backend/app/spider/services/anti_scrape.py` | Visitor-wall classification + hardened hints |
| `backend/app/spider/services/spider_pipeline_service.py` | `is_empty_scrape_result` + both call sites |
| `backend/tests/spider/test_anti_scrape.py` | Visitor wall / hint tests |
| `backend/tests/spider/test_pipeline_browser_escalation.py` | Empty-scrape classification tests |

---

### Task 1: Classify visitor/login wall as hard

**Files:**
- Modify: `backend/app/spider/services/anti_scrape.py`
- Test: `backend/tests/spider/test_anti_scrape.py`

- [ ] **Step 1: Write the failing tests**

Append to `backend/tests/spider/test_anti_scrape.py`:

```python
def test_classify_sina_visitor_system_is_hard():
    html = (
        "<!DOCTYPE html><html><head><title>Sina Visitor System</title></head>"
        "<body><span id='message'></span>"
        "<script src='/js/visitor/mini_original.js'></script></body></html>"
    )
    result = classify_fetch_result(
        url="https://www.weibo.com/",
        html=html,
        status_code=200,
    )
    assert result["level"] == "hard"
    assert result["block_hard"] is True
    assert result["escalate_to_browser"] is False
    assert "Login/Visitor Wall" in result["detected_mechanisms"]


def test_classify_visitor_url_is_hard_even_with_scripts():
    scripts = "".join(f"<script>var x{i}=1;</script>" for i in range(20))
    html = f"<html><body>{scripts}<div>loading</div></body></html>"
    result = classify_fetch_result(
        url="https://passport.weibo.com/visitor/visitor?entry=miniblog&a=enter&url=https://www.weibo.com/",
        html=html,
        status_code=200,
    )
    assert result["level"] == "hard"
    assert result["block_hard"] is True
    assert result["escalate_to_browser"] is False


def test_anti_scrape_hard_hints_mention_login_or_public_list():
    hints = hints_for_error_code("anti_scrape_hard")
    joined = " ".join(hints)
    assert ("登录" in joined) or ("Cookie" in joined) or ("公开" in joined)
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
cd backend && .venv/bin/pytest tests/spider/test_anti_scrape.py::test_classify_sina_visitor_system_is_hard tests/spider/test_anti_scrape.py::test_classify_visitor_url_is_hard_even_with_scripts tests/spider/test_anti_scrape.py::test_anti_scrape_hard_hints_mention_login_or_public_list -v
```

Expected: FAIL — visitor HTML currently classified as `js_render`; hints lack login wording.

- [ ] **Step 3: Minimal implementation**

In `backend/app/spider/services/anti_scrape.py`:

1. Add tokens near CAPTCHA constants:

```python
_VISITOR_WALL_TOKENS = (
    "sina visitor system",
    "visitor system",
    "/visitor/visitor",
    "passport.weibo.com/visitor",
    "请先登录",
    "login required",
)
```

2. Update hints:

```python
"anti_scrape_hard": [
    "目标页需要人工验证或登录态，当前不支持自动绕过 / Cookie 注入",
    "请换更开放的公开列表页，或稍后再试",
],
```

3. Inside `classify_fetch_result`, after computing `lowered = content.lower()`, and **before** CAPTCHA/Cloudflare/`js_render` branches that would escalate, also check URL:

```python
url_lower = (url or "").lower()
haystack = f"{lowered}\n{url_lower}"
has_visitor_wall = any(t in haystack for t in _VISITOR_WALL_TOKENS)
if has_visitor_wall:
    return {
        "url": url,
        "level": "hard",
        "detected_mechanisms": ["Login/Visitor Wall"],
        "recommendations": ["需要登录态或换公开列表页；当前不自动绕过"],
        "escalate_to_browser": False,
        "block_hard": True,
        "has_anti_scraping": True,
        "success": True,
        "status_code": status_code,
    }
```

Place this **before** the CAPTCHA return (or immediately after CAPTCHA — same hard outcome). Must run **before** the `script_heavy → js_render` return.

Keep existing CAPTCHA / Cloudflare / soft / none paths unchanged.

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd backend && .venv/bin/pytest tests/spider/test_anti_scrape.py -v
```

Expected: PASS (all anti_scrape tests).

- [ ] **Step 5: Commit** (only if user asked to commit)

```bash
git add backend/app/spider/services/anti_scrape.py backend/tests/spider/test_anti_scrape.py
git commit -m "$(cat <<'EOF'
fix(spider): treat visitor/login walls as anti_scrape_hard

Detect Sina Visitor System and similar login gates before js_render
escalation so pipelines fail early with accurate hints.
EOF
)"
```

---

### Task 2: Classify exit≠0 + zero records as empty_scrape

**Files:**
- Modify: `backend/app/spider/services/spider_pipeline_service.py`
- Test: `backend/tests/spider/test_pipeline_browser_escalation.py`

- [ ] **Step 1: Write the failing tests**

Append to `backend/tests/spider/test_pipeline_browser_escalation.py` (import `is_empty_scrape_result` once it exists alongside `should_escalate_after_empty_scrape`):

```python
from app.spider.services.spider_pipeline_service import (
    is_empty_scrape_result,
    should_escalate_after_empty_scrape,
)


def test_is_empty_scrape_when_saved_zero_records_nonzero_exit():
    exec_result = {
        "success": False,
        "data_saved": False,
        "exit_code": 1,
        "record_count": 0,
        "data_file": "scraped_data.json",
        "error": "2026-07-14 06:50:25,825 INFO saved 0 records",
        "output_preview": "2026-07-14 06:50:25,825 INFO saved 0 records",
    }
    detail = str(exec_result["error"])
    assert is_empty_scrape_result(exec_result, detail) is True


def test_is_empty_scrape_when_exit_zero_no_data():
    exec_result = {
        "success": False,
        "data_saved": False,
        "exit_code": 0,
        "record_count": 0,
        "data_file": "scraped_data.json",
        "error": "脚本退出码为 0，但 scraped_data.json 为空（0 条有效记录）。",
    }
    assert is_empty_scrape_result(exec_result, exec_result["error"]) is True


def test_not_empty_scrape_on_real_runtime_error():
    exec_result = {
        "success": False,
        "data_saved": False,
        "exit_code": 1,
        "record_count": 0,
        "data_file": None,
        "error": "ModuleNotFoundError: No module named 'foo'",
        "output_preview": "ModuleNotFoundError: No module named 'foo'",
    }
    assert is_empty_scrape_result(exec_result, exec_result["error"]) is False
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd backend && .venv/bin/pytest tests/spider/test_pipeline_browser_escalation.py::test_is_empty_scrape_when_saved_zero_records_nonzero_exit tests/spider/test_pipeline_browser_escalation.py::test_is_empty_scrape_when_exit_zero_no_data tests/spider/test_pipeline_browser_escalation.py::test_not_empty_scrape_on_real_runtime_error -v
```

Expected: FAIL — `is_empty_scrape_result` not importable.

- [ ] **Step 3: Minimal implementation**

Near `should_escalate_after_empty_scrape` in `spider_pipeline_service.py`:

```python
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
```

Replace both duplicated `no_data = (...)` blocks (~lines 952–955 and ~1040–1043) with:

```python
no_data = is_empty_scrape_result(exec_result, detail)
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd backend && .venv/bin/pytest tests/spider/test_anti_scrape.py tests/spider/test_pipeline_browser_escalation.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit** (only if user asked to commit)

```bash
git add backend/app/spider/services/spider_pipeline_service.py backend/tests/spider/test_pipeline_browser_escalation.py
git commit -m "$(cat <<'EOF'
fix(spider): map zero-record exits to empty_scrape

Treat scraped_data.json with 0 records / saved 0 records as empty
scrape even when exit_code is non-zero, avoiding misleading model hints.
EOF
)"
```

---

## Spec coverage check

| Spec requirement | Task |
|---|---|
| Visitor wall → hard before js_render | Task 1 |
| hints cover login / public list | Task 1 |
| Pipeline uses existing `anti_scrape_hard` | Task 1 (classify only; path already exists) |
| exit≠0 + 0 records → `empty_scrape` | Task 2 |
| real runtime error stays `execution_failed` | Task 2 |
| No cookie / new error code | Both (non-goals honored) |
