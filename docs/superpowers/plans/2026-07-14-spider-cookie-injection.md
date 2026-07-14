# Spider Cookie 注入 Implementation Plan

> **For agentic workers:** Implement task-by-task with TDD. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让用户可选注入登录 Cookie，Pipeline / DeepAgent 的分析抓取与沙箱执行均带上该 Cookie，且 Cookie 不落库、不写入生成代码字面量。

**Architecture:** 请求体 `cookies` → 请求级 ContextVar → HTTP/Playwright Header；沙箱执行经临时文件 + `SPIDER_COOKIE` 环境变量注入；前端会话级配置，可选 `sessionStorage`。

**Tech Stack:** FastAPI/Pydantic, aiohttp, Docker sandbox, React/Zustand, pytest

**Spec:** [`docs/superpowers/specs/2026-07-14-spider-cookie-injection-design.md`](../specs/2026-07-14-spider-cookie-injection-design.md)

---

## File map

| File | Responsibility |
|---|---|
| `backend/app/spider/services/request_cookies.py` | ContextVar + normalize/validate helpers |
| `backend/app/spider/schemas.py` | `cookies` field |
| `backend/app/api/v1/spider.py` | set/clear ContextVar around stream |
| `backend/app/spider/services/tools.py` | attach Cookie on fetch |
| `backend/app/spider/services/browser_fetch.py` | pass SPIDER_COOKIE into playwright fetch |
| `backend/app/spider/services/sandbox.py` | write/delete runtime cookie file; export on execute; list filter |
| `backend/app/spider/services/spider_pipeline_service.py` | templates/prompts read env |
| `backend/app/spider/services/anti_scrape.py` | updated hints |
| `backend/app/spider/services/agent_builder.py` / spider_agent_service | ensure cookies context for DeepAgent |
| Frontend store / SpiderChatView / useSpiderChat | UI + payload |
| Tests under `backend/tests/spider/` | unit coverage |

---

### Task 1: request cookies ContextVar + normalize

**Files:**
- Create: `backend/app/spider/services/request_cookies.py`
- Test: `backend/tests/spider/test_request_cookies.py`

- [ ] Write failing tests for normalize (trim/empty→None), max length, set/get ContextVar
- [ ] Implement module
- [ ] Pass tests

### Task 2: anti_scrape hints

**Files:**
- Modify: `backend/app/spider/services/anti_scrape.py`
- Test: `backend/tests/spider/test_anti_scrape.py`

- [ ] Failing tests for new hints / `cookies_configured`
- [ ] Implement
- [ ] Pass

### Task 3: fetch_url attaches Cookie header

**Files:**
- Modify: `backend/app/spider/services/tools.py`
- Test: `backend/tests/spider/test_fetch_url_cookies.py` (or extend existing)

- [ ] Failing test (mock aiohttp or extract header builder)
- [ ] Implement
- [ ] Pass

### Task 4: sandbox execute injects SPIDER_COOKIE + filters file list

**Files:**
- Modify: `backend/app/spider/services/sandbox.py`
- Test: `backend/tests/spider/test_sandbox_cookies.py`

- [ ] Failing tests
- [ ] Implement
- [ ] Pass

### Task 5: browser_fetch + codegen templates

**Files:**
- Modify: `browser_fetch.py`, `spider_pipeline_service.py`
- Tests: existing browser_fetch + new template assert

### Task 6: API schema + stream entry

**Files:**
- Modify: `schemas.py`, `api/v1/spider.py`, agent/pipeline entrypoints

### Task 7: Frontend

**Files:**
- Modify: store, constants, SpiderChatView, useSpiderChat, i18n

### Task 8: Verification

- [ ] Run spider-related pytest subset
- [ ] Mark design status 已定稿 if needed
