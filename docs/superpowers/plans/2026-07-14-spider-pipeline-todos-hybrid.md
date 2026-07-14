# Spider Pipeline + Todo 混合执行 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 有 URL 时走 Pipeline 并强制四步 Todo 逐步执行与状态更新（含 `failed`）；无 URL 时走 DeepAgent。

**Architecture:** API 用共享 URL 解析分流。Pipeline 在沙箱就绪后发射固定四步 `todos_updated`，每阶段 complete/fail 再发完整快照。前端扩展 `failed` 状态与 Todo 卡片样式。DeepAgent 路径与现有 `write_todos` 契约不变。

**Tech Stack:** FastAPI SSE、现有 spider Pipeline / DeepAgent、React + i18next、pytest

**Spec:** `docs/superpowers/specs/2026-07-14-spider-pipeline-todos-hybrid-design.md`

---

## File map

| File | Responsibility |
|------|----------------|
| `backend/app/spider/services/todo_events.py` | 允许 `failed`；Pipeline 模板 / 快照 helper |
| `backend/app/spider/services/target_url.py` | 共享 `try_resolve_spider_target_url` |
| `backend/app/spider/services/spider_pipeline_service.py` | 推进 todos；缺 URL 由上层分流后很少触发 |
| `backend/app/api/v1/spider.py` | 有 URL → pipeline；无 URL → deepagent |
| `backend/tests/spider/test_todo_events.py` | `failed` + pipeline snapshot helpers |
| `backend/tests/spider/test_target_url.py` | URL 解析 |
| `backend/tests/spider/test_pipeline_todos.py` | 快照推进纯函数 / 无 Docker 场景 |
| `frontend/src/features/spider/types/todo.ts` | `failed` |
| `frontend/src/features/spider/components/SpiderTodoCard.tsx` | failed UI |
| `frontend/src/i18n/locales/zh-CN.json` / `en.json` | `todos.failed` |

---

### Task 1: Backend — `failed` + Pipeline todo helpers

**Files:**
- Modify: `backend/app/spider/services/todo_events.py`
- Modify: `backend/tests/spider/test_todo_events.py`

- [ ] **Step 1: Extend failing tests for `failed` + helpers**

在 `test_todo_events.py` 追加：

```python
def test_normalize_todos_keeps_failed():
    raw = [
        {"content": "分析目标网站结构", "status": "completed"},
        {"content": "生成爬虫代码", "status": "failed"},
        {"content": "在沙箱执行并调试", "status": "pending"},
    ]
    assert normalize_todos(raw) == raw


def test_pipeline_todo_template_initial():
    from app.spider.services.todo_events import pipeline_todo_snapshot

    assert pipeline_todo_snapshot(active_index=0) == [
        {"content": "分析目标网站结构", "status": "in_progress"},
        {"content": "生成爬虫代码", "status": "pending"},
        {"content": "在沙箱执行并调试", "status": "pending"},
        {"content": "清洗并校验数据", "status": "pending"},
    ]


def test_pipeline_todo_snapshot_complete_and_advance():
    from app.spider.services.todo_events import pipeline_todo_snapshot

    assert pipeline_todo_snapshot(completed_through=0, active_index=1)[0]["status"] == "completed"
    assert pipeline_todo_snapshot(completed_through=0, active_index=1)[1]["status"] == "in_progress"


def test_pipeline_todo_snapshot_failed():
    from app.spider.services.todo_events import pipeline_todo_snapshot

    todos = pipeline_todo_snapshot(completed_through=1, failed_index=2)
    assert [t["status"] for t in todos] == [
        "completed",
        "completed",
        "failed",
        "pending",
    ]


def test_pipeline_todo_snapshot_all_completed():
    from app.spider.services.todo_events import pipeline_todo_snapshot

    todos = pipeline_todo_snapshot(completed_through=3)
    assert all(t["status"] == "completed" for t in todos)
```

- [ ] **Step 2: Run tests — expect FAIL**

Run: `cd backend && .venv/bin/pytest tests/spider/test_todo_events.py -v`

Expected: 新用例 FAIL（`failed` 被丢弃 / `pipeline_todo_snapshot` 不存在）

- [ ] **Step 3: Implement**

更新 `todo_events.py`：

```python
"""Helpers for todos_updated (DeepAgent write_todos + Pipeline template)."""

from __future__ import annotations

from typing import Any

_ALLOWED_STATUS = frozenset({"pending", "in_progress", "completed", "failed"})

PIPELINE_TODO_CONTENTS: tuple[str, ...] = (
    "分析目标网站结构",
    "生成爬虫代码",
    "在沙箱执行并调试",
    "清洗并校验数据",
)


def normalize_todos(raw: Any) -> list[dict[str, str]]:
    if not isinstance(raw, list):
        return []
    result: list[dict[str, str]] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        content = item.get("content")
        status = item.get("status")
        if not isinstance(content, str) or not content.strip():
            continue
        if status not in _ALLOWED_STATUS:
            continue
        result.append({"content": content.strip(), "status": str(status)})
    return result


def build_todos_updated_event(raw_todos: Any) -> dict[str, Any] | None:
    todos = normalize_todos(raw_todos)
    if not todos:
        return None
    return {"type": "todos_updated", "source": "agent", "todos": todos}


def pipeline_todo_snapshot(
    *,
    completed_through: int = -1,
    active_index: int | None = None,
    failed_index: int | None = None,
) -> list[dict[str, str]]:
    """Build the fixed 4-step pipeline todo snapshot.

    - Indices ``0..completed_through`` (inclusive) → completed
    - ``failed_index`` (if set) → failed
    - ``active_index`` (if set and not failed) → in_progress
    - remaining → pending
    """
    todos: list[dict[str, str]] = []
    for i, content in enumerate(PIPELINE_TODO_CONTENTS):
        if failed_index is not None and i == failed_index:
            status = "failed"
        elif i <= completed_through:
            status = "completed"
        elif active_index is not None and i == active_index:
            status = "in_progress"
        else:
            status = "pending"
        todos.append({"content": content, "status": status})
    return todos
```

- [ ] **Step 4: Run tests — expect PASS**

Run: `cd backend && .venv/bin/pytest tests/spider/test_todo_events.py -v`

Expected: PASS

- [ ] **Step 5: Commit**（仅当用户要求提交时执行）

```bash
git add backend/app/spider/services/todo_events.py backend/tests/spider/test_todo_events.py
git commit -m "$(cat <<'EOF'
feat(spider): allow failed todos and pipeline snapshot helper

EOF
)"
```

---

### Task 2: Backend — 共享 URL 解析

**Files:**
- Create: `backend/app/spider/services/target_url.py`
- Create: `backend/tests/spider/test_target_url.py`
- Modify: `backend/app/spider/services/spider_pipeline_service.py`（`_resolve_target_url` 改为调用共享函数）

- [ ] **Step 1: Write failing tests**

```python
# backend/tests/spider/test_target_url.py
from app.spider.services.target_url import try_resolve_spider_target_url


def test_prefers_explicit_target_url():
    assert (
        try_resolve_spider_target_url("随便说说", "https://movie.douban.com/top250")
        == "https://movie.douban.com/top250"
    )


def test_extracts_url_from_message():
    assert (
        try_resolve_spider_target_url(
            "分析 https://movie.douban.com/top250 并爬取标题", None
        )
        == "https://movie.douban.com/top250"
    )


def test_strips_trailing_punctuation():
    assert (
        try_resolve_spider_target_url("看这个 https://example.com/list).", None)
        == "https://example.com/list"
    )


def test_returns_none_when_missing():
    assert try_resolve_spider_target_url("帮我解释一下上次的代码", None) is None
    assert try_resolve_spider_target_url("hello", "   ") is None
```

- [ ] **Step 2: Run — expect FAIL**

Run: `cd backend && .venv/bin/pytest tests/spider/test_target_url.py -v`

Expected: import error

- [ ] **Step 3: Implement `target_url.py`**

```python
"""Resolve spider target URL from request fields."""

from __future__ import annotations


def try_resolve_spider_target_url(message: str, target_url: str | None) -> str | None:
    if target_url and target_url.strip():
        return target_url.strip()
    for token in (message or "").split():
        if token.startswith("http://") or token.startswith("https://"):
            return token.strip(".,;)")
    return None
```

- [ ] **Step 4: Wire Pipeline**

将 `spider_pipeline_service._resolve_target_url` 改为：

```python
from app.spider.services.target_url import try_resolve_spider_target_url


def _resolve_target_url(message: str, target_url: str | None) -> str:
    resolved = try_resolve_spider_target_url(message, target_url)
    if not resolved:
        raise ValueError("请填写目标网址，或在消息中包含 http(s):// 链接")
    return resolved
```

- [ ] **Step 5: Run tests**

Run: `cd backend && .venv/bin/pytest tests/spider/test_target_url.py tests/spider/test_todo_events.py -v`

Expected: PASS

- [ ] **Step 6: Commit**（仅当用户要求提交时）

```bash
git add backend/app/spider/services/target_url.py backend/tests/spider/test_target_url.py backend/app/spider/services/spider_pipeline_service.py
git commit -m "$(cat <<'EOF'
feat(spider): share target URL resolver for hybrid routing

EOF
)"
```

---

### Task 3: Backend — Pipeline 发射并推进 todos

**Files:**
- Modify: `backend/app/spider/services/spider_pipeline_service.py`
- Create: `backend/tests/spider/test_pipeline_todos.py`（可选轻量：只测调用 helper 的集成方式；主逻辑在 snapshot 单测已覆盖时，本任务以改 pipeline 为主）

- [ ] **Step 1: 在 `spider_pipeline_stream` 注入 todos**

导入：

```python
from app.spider.services.todo_events import build_todos_updated_event, pipeline_todo_snapshot
```

辅助（同文件内）：

```python
def _todos_event(**kwargs) -> dict[str, Any]:
    event = build_todos_updated_event(pipeline_todo_snapshot(**kwargs))
    assert event is not None
    return event
```

在 **沙箱初始化成功**、`set_sandbox_workspace(workspace)` 之后、Stage 1 `_emit_stage_start` **之前**：

```python
yield _todos_event(active_index=0)
```

每个阶段：

1. `_emit_stage_start` / 跑逻辑前无需再改（第 0 步已 in_progress；后续步在上一步 complete 时设 in_progress）
2. **阶段成功** `_emit_stage_complete` 之后：

```python
# stage index: web_analyzer=0, code_generator=1, debug_agent=2, data_processor=3
stage_index = 0  # 替换为实际索引
if stage_index < 3:
    yield _todos_event(completed_through=stage_index, active_index=stage_index + 1)
else:
    yield _todos_event(completed_through=3)
```

3. **阶段失败**（在现有 `yield _error_event(...)` **之前**）：

```python
yield _todos_event(completed_through=stage_index - 1, failed_index=stage_index)
```

具体挂载点：

| 失败点 | `completed_through` | `failed_index` |
|--------|---------------------|----------------|
| `fetch_failed` | `-1` | `0` |
| `codegen_syntax_invalid` | `0` | `1` |
| `execution_failed` / `empty_scrape` | `1` | `2` |
| `missing_result_file` | `2` | `3` |

**不要**在沙箱 init 失败路径发 todos（符合规格）。

`missing_target_url` 路径：API 分流后极少进入；若仍进入，保持现有 error，可不发 todos。

- [ ] **Step 2: 冒烟逻辑自检（无 Docker 时至少语法导入）**

Run: `cd backend && .venv/bin/python -c "from app.spider.services.spider_pipeline_service import spider_pipeline_stream; print('ok')"`

Expected: `ok`

- [ ] **Step 3: Commit**（仅当用户要求提交时）

```bash
git add backend/app/spider/services/spider_pipeline_service.py
git commit -m "$(cat <<'EOF'
feat(spider): emit progressive pipeline todos including failed

EOF
)"
```

---

### Task 4: Backend — API 按 URL 路由

**Files:**
- Modify: `backend/app/api/v1/spider.py`
- Create: `backend/tests/spider/test_agent_run_routing.py`（纯函数级：抽一个小 helper 测分流，避免起 FastAPI）

为便于单测，在 `spider.py`（或 `target_url.py` 旁）增加：

```python
# backend/app/spider/services/runtime_route.py
from __future__ import annotations

from typing import Literal

from app.spider.services.target_url import try_resolve_spider_target_url

SpiderRuntime = Literal["pipeline", "deepagent"]


def choose_spider_runtime(message: str, target_url: str | None) -> SpiderRuntime:
    if try_resolve_spider_target_url(message, target_url):
        return "pipeline"
    return "deepagent"
```

- [ ] **Step 1: 单测**

```python
# backend/tests/spider/test_agent_run_routing.py
from app.spider.services.runtime_route import choose_spider_runtime


def test_with_url_uses_pipeline():
    assert choose_spider_runtime("爬取", "https://example.com") == "pipeline"
    assert choose_spider_runtime("看 https://example.com/a", None) == "pipeline"


def test_without_url_uses_deepagent():
    assert choose_spider_runtime("解释上次清洗结果", None) == "deepagent"
```

- [ ] **Step 2: Run — FAIL then implement module — PASS**

Run: `cd backend && .venv/bin/pytest tests/spider/test_agent_run_routing.py -v`

- [ ] **Step 3: Wire `spider_agent_run`**

```python
from app.spider.services.runtime_route import choose_spider_runtime
from app.spider.services.spider_agent_service import spider_agent_stream
from app.spider.services.spider_pipeline_service import spider_pipeline_stream


# inside event_stream:
runtime = choose_spider_runtime(request.message, request.target_url)
stream_fn = spider_pipeline_stream if runtime == "pipeline" else spider_agent_stream
inner = stream_fn(
    message=request.message,
    conversation_history=conversation_history,
    user_id=str(user_id),
    session_id=str(session_id),
    llm_api_key=ctx.api_key,
    llm_base_url=ctx.base_url,
    model_name=ctx.model_id,
    target_url=request.target_url,
)
```

删除仅导入 `spider_agent_stream` 的单路径。

- [ ] **Step 4: Run related tests**

Run: `cd backend && .venv/bin/pytest tests/spider/ -v`

Expected: PASS

- [ ] **Step 5: Commit**（仅当用户要求提交时）

```bash
git add backend/app/spider/services/runtime_route.py backend/app/api/v1/spider.py backend/tests/spider/test_agent_run_routing.py
git commit -m "$(cat <<'EOF'
feat(spider): route agent run to pipeline when URL present

EOF
)"
```

---

### Task 5: Frontend — `failed` 状态与 Todo 卡片

**Files:**
- Modify: `frontend/src/features/spider/types/todo.ts`
- Modify: `frontend/src/features/spider/components/SpiderTodoCard.tsx`
- Modify: `frontend/src/i18n/locales/zh-CN.json`
- Modify: `frontend/src/i18n/locales/en.json`

- [ ] **Step 1: 扩展类型**

```ts
export type SpiderTodoStatus = 'pending' | 'in_progress' | 'completed' | 'failed';

export function isSpiderTodoStatus(value: unknown): value is SpiderTodoStatus {
  return (
    value === 'pending' ||
    value === 'in_progress' ||
    value === 'completed' ||
    value === 'failed'
  );
}
```

- [ ] **Step 2: `SpiderTodoCard` 渲染 `failed`**

在 map 内增加分支（lucide 已有 `X`；失败用 `CircleAlert` 或红底叉）：

```tsx
import { Check, CircleAlert, ListTodo, Loader2, X } from 'lucide-react';

// ...
const isFailed = todo.status === 'failed';
const isDone = todo.status === 'completed';
const isRunning = todo.status === 'in_progress';

// icon:
{isDone ? (
  // existing green check
) : isFailed ? (
  <span
    className="flex h-4 w-4 items-center justify-center rounded-full bg-red-500 text-white"
    aria-label={t('spider.chat.todos.failed')}
  >
    <X size={10} strokeWidth={3} />
  </span>
) : isRunning ? (
  // spinner
) : (
  // pending ring
)}

// text className:
isDone
  ? 'text-[var(--text-secondary)] line-through'
  : isFailed
    ? 'text-red-600'
    : 'text-[var(--text-primary)]'
```

Header 计数保持 `todos.filter(t => t.status === 'completed').length`（failed 不计入）。

- [ ] **Step 3: i18n**

`zh-CN.json` `spider.chat.todos` 增加：`"failed": "失败"`  
`en.json`：`"failed": "Failed"`

- [ ] **Step 4: 类型检查（若项目惯用）**

Run: `cd frontend && npx tsc --noEmit -p tsconfig.json`（若太慢可只依赖 IDE / 跳过）

- [ ] **Step 5: Commit**（仅当用户要求提交时）

```bash
git add frontend/src/features/spider/types/todo.ts frontend/src/features/spider/components/SpiderTodoCard.tsx frontend/src/i18n/locales/zh-CN.json frontend/src/i18n/locales/en.json
git commit -m "$(cat <<'EOF'
feat(spider): render failed todo status in progress card

EOF
)"
```

---

### Task 6: 手动冒烟清单

- [ ] 填入 `https://movie.douban.com/top250` +「爬取电影标题和链接」→ 应见 Todo 卡片逐步推进，**不是**教程长文；工作区出现文件。
- [ ] 无 URL 纯文字 → DeepAgent（可不出现固定四步）。
- [ ] 人为断网或坏 URL → 第 1 步 `failed` + 失败卡片。
- [ ] 刷新会话 → todos（含 failed/completed）仍在。

---

## Spec coverage self-check

| Spec 要求 | Task |
|-----------|------|
| 有 URL → Pipeline | Task 4 |
| 无 URL → DeepAgent | Task 4 |
| 固定四步模板 | Task 1 + 3 |
| 逐步 todos_updated | Task 3 |
| `failed` 状态 | Task 1 + 5 |
| 沙箱失败不发 todos | Task 3 |
| 推翻「不为 pipeline 伪造 todo」 | Task 3（显式伪造） |
| UI failed | Task 5 |
| 持久化 | 已有 checkpoint；normalize 接受 failed 即可（Task 1/5） |

## Placeholder scan

无 TBD / 「类似 Task N」含糊步骤。

## Type consistency

- 状态四字面量：`pending` \| `in_progress` \| `completed` \| `failed`
- 事件：`todos_updated` + `source: "agent"`
- 路由：`choose_spider_runtime` → `"pipeline"` \| `"deepagent"`
