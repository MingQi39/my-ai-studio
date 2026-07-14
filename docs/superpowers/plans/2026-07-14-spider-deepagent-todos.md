# Spider DeepAgent Todo Card Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 切回 DeepAgent，在助手消息中按 `write_todos` 快照实时渲染可折叠 Todo 进度卡片，并持久化恢复；简单任务无卡片。

**Architecture:** 后端在 `tool_call_start` 识别 `write_todos` 后立即发 `todos_updated`；`spider_meta.todos` 落最终快照；前端 `useSpiderChat` 写入 `message.todos`，`SpiderTodoCard` 渲染；默认工具列表隐藏 `write_todos`，折叠「工具详情」可见。

**Tech Stack:** FastAPI SSE、DeepAgents/`TodoListMiddleware`、React + i18next、现有 studio chat 组件。

**Spec:** `docs/superpowers/specs/2026-07-14-spider-deepagent-todos-design.md`

---

## File map

| File | Responsibility |
|------|----------------|
| `backend/app/spider/services/todo_events.py` | 规范化 todos；构造 `todos_updated` 事件 |
| `backend/app/spider/services/spider_agent_service.py` | DeepAgent 流里发出 `todos_updated` |
| `backend/app/spider/services/chat_persistence.py` | `spider_meta.todos` 读写 |
| `backend/app/api/v1/spider.py` | 切回 DeepAgent；persist 收集 todos |
| `backend/tests/spider/test_todo_events.py` | 规范化 & 事件单测 |
| `backend/tests/spider/test_chat_persistence_todos.py` | meta todos 单测 |
| `frontend/src/features/spider/types/events.ts` | SSE 联合类型 |
| `frontend/src/features/spider/types/todo.ts` | `SpiderTodoItem` 类型 |
| `frontend/src/hooks/studioChat/types.ts` | `StudioChatMessage.todos` |
| `frontend/src/components/chat/ChatToolRunBlock.tsx` | `ChatToolRun.raw_tool_name?` |
| `frontend/src/features/spider/components/SpiderTodoCard.tsx` | Todo 卡片 UI |
| `frontend/src/components/chat/StudioAssistantMessage.tsx` | 插入卡片 + 工具详情 |
| `frontend/src/components/chat/StudioChatMessageList.tsx` | 透传 `todos` |
| `frontend/src/features/spider/hooks/useSpiderChat.ts` | 消费 `todos_updated` |
| `frontend/src/features/spider/services/api/sessions.ts` | 恢复 todos |
| `frontend/src/i18n/locales/zh-CN.json` / `en.json` | 文案 |

---

### Task 1: Backend — `normalize_todos` + `todos_updated` 事件工厂

**Files:**
- Create: `backend/app/spider/services/todo_events.py`
- Create: `backend/tests/spider/__init__.py` (空文件即可)
- Create: `backend/tests/spider/test_todo_events.py`

- [ ] **Step 1: Write the failing tests**

```python
# backend/tests/spider/test_todo_events.py
from app.spider.services.todo_events import build_todos_updated_event, normalize_todos


def test_normalize_todos_keeps_valid_items():
    raw = [
        {"content": "分析网站", "status": "completed"},
        {"content": "生成代码", "status": "in_progress"},
        {"content": "执行", "status": "pending"},
    ]
    assert normalize_todos(raw) == raw


def test_normalize_todos_drops_invalid_items():
    raw = [
        {"content": "ok", "status": "pending"},
        {"content": "", "status": "pending"},
        {"content": "bad", "status": "done"},
        {"status": "pending"},
        "not-a-dict",
        None,
    ]
    assert normalize_todos(raw) == [{"content": "ok", "status": "pending"}]


def test_normalize_todos_empty_input():
    assert normalize_todos(None) == []
    assert normalize_todos([]) == []
    assert normalize_todos("nope") == []


def test_build_todos_updated_event_none_when_empty():
    assert build_todos_updated_event([]) is None
    assert build_todos_updated_event(None) is None


def test_build_todos_updated_event_payload():
    event = build_todos_updated_event(
        [{"content": "A", "status": "pending"}, {"content": "", "status": "pending"}]
    )
    assert event == {
        "type": "todos_updated",
        "source": "agent",
        "todos": [{"content": "A", "status": "pending"}],
    }
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && .venv/bin/pytest tests/spider/test_todo_events.py -v`

Expected: FAIL（模块不存在 / import error）

- [ ] **Step 3: Implement**

```python
# backend/app/spider/services/todo_events.py
"""Helpers for DeepAgent write_todos → SSE todos_updated."""

from __future__ import annotations

from typing import Any

_ALLOWED_STATUS = frozenset({"pending", "in_progress", "completed"})


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
```

Also create empty `backend/tests/spider/__init__.py`.

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && .venv/bin/pytest tests/spider/test_todo_events.py -v`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/spider/services/todo_events.py backend/tests/spider/
git commit -m "$(cat <<'EOF'
feat(spider): add write_todos normalize helpers for SSE

EOF
)"
```

---

### Task 2: Backend — DeepAgent 流发出 `todos_updated`

**Files:**
- Modify: `backend/app/spider/services/spider_agent_service.py`

- [ ] **Step 1: Add import**

Near other service imports:

```python
from app.spider.services.todo_events import build_todos_updated_event
```

- [ ] **Step 2: After yielding `tool_call_start`, emit todos when `write_todos`**

Locate the block that yields `tool_call_start` (around the `task` special-case). Immediately after the existing `tool_call_start` yield (and before/after the `task` branch — order does not matter), add:

```python
                            if tool_name == "write_todos":
                                todos_event = build_todos_updated_event(
                                    tool_args.get("todos")
                                )
                                if todos_event is not None:
                                    yield todos_event
```

Full local shape for clarity (existing yields stay):

```python
                            yield {
                                "type": "tool_call_start",
                                "source": "agent",
                                "call_id": call_id,
                                "tool_name": display_name,
                                "tool_args": tool_args,
                                "raw_tool_name": tool_name,
                            }

                            if tool_name == "write_todos":
                                todos_event = build_todos_updated_event(
                                    tool_args.get("todos")
                                )
                                if todos_event is not None:
                                    yield todos_event

                            if tool_name == "task":
                                # existing subagent_start yield unchanged
```

- [ ] **Step 3: Smoke-check import**

Run: `cd backend && .venv/bin/python -c "from app.spider.services.spider_agent_service import spider_agent_stream; print('ok')"`

Expected: `ok`

- [ ] **Step 4: Commit**

```bash
git add backend/app/spider/services/spider_agent_service.py
git commit -m "$(cat <<'EOF'
feat(spider): emit todos_updated on DeepAgent write_todos

EOF
)"
```

---

### Task 3: Backend — `spider_meta` 持久化 todos

**Files:**
- Modify: `backend/app/spider/services/chat_persistence.py`
- Create: `backend/tests/spider/test_chat_persistence_todos.py`

- [ ] **Step 1: Write failing tests**

```python
# backend/tests/spider/test_chat_persistence_todos.py
from app.spider.services.chat_persistence import build_spider_tool_calls, parse_spider_meta


def test_build_spider_tool_calls_includes_todos():
    todos = [
        {"content": "分析", "status": "completed"},
        {"content": "生成", "status": "pending"},
    ]
    tool_calls = build_spider_tool_calls(todos=todos)
    meta = parse_spider_meta(tool_calls)
    assert meta is not None
    assert meta["type"] == "spider_meta"
    assert meta["todos"] == todos


def test_build_spider_tool_calls_omits_empty_todos():
    tool_calls = build_spider_tool_calls(todos=[])
    meta = parse_spider_meta(tool_calls)
    assert meta is not None
    assert "todos" not in meta


def test_build_spider_tool_calls_combines_trace_and_todos():
    tool_calls = build_spider_tool_calls(
        tool_trace=[{"id": "c1", "tool_name": "write_todos", "status": "success"}],
        todos=[{"content": "A", "status": "pending"}],
    )
    meta = parse_spider_meta(tool_calls)
    assert meta is not None
    assert len(meta["tool_trace"]) == 1
    assert meta["todos"][0]["content"] == "A"
```

- [ ] **Step 2: Run tests — expect FAIL**

Run: `cd backend && .venv/bin/pytest tests/spider/test_chat_persistence_todos.py -v`

Expected: FAIL（`todos` kwarg unexpected）

- [ ] **Step 3: Update `build_spider_tool_calls` and `save_spider_assistant_message`**

In `chat_persistence.py`:

```python
def build_spider_tool_calls(
    *,
    tool_trace: list[dict[str, Any]] | None = None,
    target_url: str | None = None,
    failure: dict[str, Any] | None = None,
    todos: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    meta: dict[str, Any] = {"type": SPIDER_META_KEY}
    if tool_trace:
        meta["tool_trace"] = tool_trace
    if target_url:
        meta["target_url"] = target_url
    if failure:
        meta["failure"] = failure
    if todos:
        meta["todos"] = todos
    return [meta]
```

```python
async def save_spider_assistant_message(
    session_service: SessionService,
    session_id: UUID,
    content: str,
    *,
    tool_trace: list[dict[str, Any]] | None = None,
    failure: dict[str, Any] | None = None,
    todos: list[dict[str, Any]] | None = None,
) -> None:
    await session_service.add_message(
        session_id,
        MessageCreate(
            role=MessageRole.assistant,
            content=content,
            tool_calls=build_spider_tool_calls(
                tool_trace=tool_trace,
                failure=failure,
                todos=todos,
            ),
        ),
    )
```

- [ ] **Step 4: Run tests — expect PASS**

Run: `cd backend && .venv/bin/pytest tests/spider/test_chat_persistence_todos.py -v`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/spider/services/chat_persistence.py backend/tests/spider/test_chat_persistence_todos.py
git commit -m "$(cat <<'EOF'
feat(spider): persist todos snapshot in spider_meta

EOF
)"
```

---

### Task 4: Backend — API 切回 DeepAgent + persist 收集 todos

**Files:**
- Modify: `backend/app/api/v1/spider.py`

- [ ] **Step 1: Switch stream import**

Replace:

```python
from app.spider.services.spider_pipeline_service import spider_pipeline_stream as spider_agent_stream
```

With:

```python
from app.spider.services.spider_agent_service import spider_agent_stream
from app.spider.services.todo_events import normalize_todos
```

Do **not** delete `spider_pipeline_service.py`.

- [ ] **Step 2: Collect `latest_todos` in `_persist_spider_stream`**

At top of the function (with other locals):

```python
    latest_todos: list[dict[str, Any]] | None = None
```

Inside the event loop, after existing handlers:

```python
        if etype == "todos_updated":
            normalized = normalize_todos(event.get("todos"))
            if normalized:
                latest_todos = normalized
```

Update the save call:

```python
    await save_spider_assistant_message(
        session_service=session_service,
        session_id=session_id,
        content=content_buffer,
        tool_trace=tool_trace if tool_trace else None,
        failure=failure,
        todos=latest_todos,
    )
```

Also soften the early-return so a stream that only had todos still persists (optional but safer). Change:

```python
    if not content_buffer and not tool_trace and not failure:
        return
```

To:

```python
    if not content_buffer and not tool_trace and not failure and not latest_todos:
        return
```

- [ ] **Step 3: Verify import wiring**

Run: `cd backend && .venv/bin/python -c "from app.api.v1.spider import spider_agent_run; from app.spider.services.spider_agent_service import spider_agent_stream; print(spider_agent_stream.__module__)"`

Expected: `app.spider.services.spider_agent_service`

- [ ] **Step 4: Commit**

```bash
git add backend/app/api/v1/spider.py
git commit -m "$(cat <<'EOF'
feat(spider): wire DeepAgent stream and persist todos_updated

EOF
)"
```

---

### Task 5: Frontend — 类型

**Files:**
- Create: `frontend/src/features/spider/types/todo.ts`
- Modify: `frontend/src/features/spider/types/events.ts`
- Modify: `frontend/src/hooks/studioChat/types.ts`
- Modify: `frontend/src/components/chat/ChatToolRunBlock.tsx`

- [ ] **Step 1: Create todo types**

```ts
// frontend/src/features/spider/types/todo.ts
export type SpiderTodoStatus = 'pending' | 'in_progress' | 'completed';

export type SpiderTodoItem = {
  content: string;
  status: SpiderTodoStatus;
};

export function isSpiderTodoStatus(value: unknown): value is SpiderTodoStatus {
  return value === 'pending' || value === 'in_progress' || value === 'completed';
}

export function normalizeSpiderTodos(raw: unknown): SpiderTodoItem[] {
  if (!Array.isArray(raw)) return [];
  const result: SpiderTodoItem[] = [];
  for (const item of raw) {
    if (!item || typeof item !== 'object') continue;
    const content = (item as { content?: unknown }).content;
    const status = (item as { status?: unknown }).status;
    if (typeof content !== 'string' || !content.trim()) continue;
    if (!isSpiderTodoStatus(status)) continue;
    result.push({ content: content.trim(), status });
  }
  return result;
}
```

- [ ] **Step 2: Extend SSE events**

In `events.ts`, add to the union:

```ts
  | {
      type: 'todos_updated';
      source?: string;
      todos: Array<{ content: string; status: 'pending' | 'in_progress' | 'completed' }>;
    }
```

- [ ] **Step 3: Extend message + ChatToolRun**

In `hooks/studioChat/types.ts`:

```ts
import type { SpiderTodoItem } from '@/features/spider/types/todo';
```

Add to `StudioChatMessage`:

```ts
  /** DeepAgent write_todos snapshot; omit when task has no plan. */
  todos?: SpiderTodoItem[];
```

In `ChatToolRunBlock.tsx` type:

```ts
export type ChatToolRun = {
  call_id?: string;
  tool_name: string;
  raw_tool_name?: string;
  tool_type?: string;
  tool_input?: Record<string, unknown>;
  tool_output?: string;
  status: 'running' | 'completed' | 'error';
};
```

- [ ] **Step 4: Commit**

```bash
git add frontend/src/features/spider/types/todo.ts frontend/src/features/spider/types/events.ts \
  frontend/src/hooks/studioChat/types.ts frontend/src/components/chat/ChatToolRunBlock.tsx
git commit -m "$(cat <<'EOF'
feat(spider): add todos types for DeepAgent progress card

EOF
)"
```

---

### Task 6: Frontend — i18n 文案

**Files:**
- Modify: `frontend/src/i18n/locales/zh-CN.json`
- Modify: `frontend/src/i18n/locales/en.json`

- [ ] **Step 1: Add keys under `spider.chat`**

`zh-CN.json`（放在 `progress` 旁）:

```json
"todos": {
  "completedCount": "{{completed}}/{{total}} 已完成",
  "collapse": "折叠任务列表",
  "expand": "展开任务列表",
  "toolDetails": "工具详情",
  "inProgress": "进行中"
}
```

`en.json`:

```json
"todos": {
  "completedCount": "{{completed}}/{{total}} completed",
  "collapse": "Collapse task list",
  "expand": "Expand task list",
  "toolDetails": "Tool details",
  "inProgress": "In progress"
}
```

确保 JSON 逗号合法（嵌在现有 `"chat": { ... }` 内）。

- [ ] **Step 2: Commit**

```bash
git add frontend/src/i18n/locales/zh-CN.json frontend/src/i18n/locales/en.json
git commit -m "$(cat <<'EOF'
feat(spider): add i18n for todo progress card

EOF
)"
```

---

### Task 7: Frontend — `SpiderTodoCard` 组件

**Files:**
- Create: `frontend/src/features/spider/components/SpiderTodoCard.tsx`

- [ ] **Step 1: Implement component**

```tsx
// frontend/src/features/spider/components/SpiderTodoCard.tsx
import { useState } from 'react';
import { Check, ListTodo, Loader2, X } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import { cn } from '@/components/ui/utils';
import type { SpiderTodoItem } from '@/features/spider/types/todo';

type SpiderTodoCardProps = {
  todos: SpiderTodoItem[];
  isDarkMode?: boolean;
};

export function SpiderTodoCard({ todos, isDarkMode = false }: SpiderTodoCardProps) {
  const { t } = useTranslation();
  const [collapsed, setCollapsed] = useState(false);

  if (todos.length === 0) return null;

  const completed = todos.filter((item) => item.status === 'completed').length;
  const total = todos.length;

  return (
    <div
      className={cn(
        'rounded-xl border border-[var(--border-color)] shadow-sm overflow-hidden',
        isDarkMode ? 'bg-slate-900/60' : 'bg-slate-50',
      )}
    >
      <div className="flex items-center justify-between gap-2 px-3 py-2">
        <div className="flex min-w-0 items-center gap-2 text-sm text-[var(--text-primary)]">
          <ListTodo size={16} className="shrink-0 text-violet-500" />
          <span className="truncate font-medium">
            {t('spider.chat.todos.completedCount', { completed, total })}
          </span>
        </div>
        <button
          type="button"
          className="shrink-0 rounded p-1 text-[var(--text-secondary)] hover:bg-[var(--bg-subtle)]"
          aria-label={collapsed ? t('spider.chat.todos.expand') : t('spider.chat.todos.collapse')}
          onClick={() => setCollapsed((v) => !v)}
        >
          {collapsed ? <ListTodo size={14} /> : <X size={14} />}
        </button>
      </div>

      {!collapsed && (
        <ul className="max-h-48 space-y-1.5 overflow-y-auto border-t border-[var(--border-color)] px-3 py-2">
          {todos.map((todo, index) => {
            const isDone = todo.status === 'completed';
            const isRunning = todo.status === 'in_progress';
            return (
              <li key={`${index}-${todo.content}`} className="flex items-center gap-2 min-w-0">
                <span className="shrink-0">
                  {isDone ? (
                    <span className="flex h-4 w-4 items-center justify-center rounded-full bg-emerald-500 text-white">
                      <Check size={10} strokeWidth={3} />
                    </span>
                  ) : isRunning ? (
                    <Loader2 size={16} className="animate-spin text-slate-400" aria-label={t('spider.chat.todos.inProgress')} />
                  ) : (
                    <span className="block h-4 w-4 rounded-full border border-slate-300" />
                  )}
                </span>
                <span
                  className={cn(
                    'min-w-0 flex-1 truncate text-sm',
                    isDone
                      ? 'text-[var(--text-secondary)] line-through'
                      : 'text-[var(--text-primary)]',
                  )}
                  title={todo.content}
                >
                  {todo.content}
                </span>
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}
```

- [ ] **Step 2: Typecheck / lint the file if convenient**

Run from `frontend`: `npx tsc --noEmit -p tsconfig.json 2>&1 | head -40`  
（若项目无单独 spider 类型检查，也可依赖 IDE；本步不阻塞。）

- [ ] **Step 3: Commit**

```bash
git add frontend/src/features/spider/components/SpiderTodoCard.tsx
git commit -m "$(cat <<'EOF'
feat(spider): add SpiderTodoCard progress UI

EOF
)"
```

---

### Task 8: Frontend — 助手消息接入卡片 + 工具详情

**Files:**
- Modify: `frontend/src/components/chat/StudioAssistantMessage.tsx`
- Modify: `frontend/src/components/chat/StudioChatMessageList.tsx`

- [ ] **Step 1: Update `StudioAssistantMessage`**

Add imports:

```tsx
import type { SpiderTodoItem } from '@/features/spider/types/todo';
import { SpiderTodoCard } from '@/features/spider/components/SpiderTodoCard';
import { useState } from 'react';
```

（若文件已 `import type { ReactNode } from 'react'`，改为 `import { useState, type ReactNode } from 'react'`。）

Extend props:

```tsx
  todos?: SpiderTodoItem[];
```

Destructure `todos`；在组件内：

```tsx
  const [showToolDetails, setShowToolDetails] = useState(false);

  const isWriteTodosRun = (run: ChatToolRun) =>
    run.raw_tool_name === 'write_todos' || run.tool_name === 'write_todos';

  const visibleToolRuns = toolRuns?.filter((run) => !isWriteTodosRun(run) && run.tool_name !== 'execute_python');
  const hiddenToolRuns = toolRuns?.filter((run) => isWriteTodosRun(run)) ?? [];
  const hasTodoCard = Boolean(todos && todos.length > 0);
```

Render order inside `AssistantMessageShell`（卡片在 status / tool 之前，贴近截图「思考中」上方）：

```tsx
      {hasTodoCard && todos && <SpiderTodoCard todos={todos} isDarkMode={isDarkMode} />}

      {thinking && <ThinkingBlock text={thinking} isStreaming={isThinking} isDarkMode={isDarkMode} />}

      {statusLabel && isThinking && (
        <GeneratingIndicator layout="spinner" label={statusLabel} />
      )}

      {visibleToolRuns?.map((run, index) => (
        <ChatToolRunBlock key={`${run.tool_name}-${index}`} run={run} isDarkMode={isDarkMode} />
      ))}

      {hiddenToolRuns.length > 0 && (
        <div className="text-xs">
          <button
            type="button"
            className="text-[var(--text-secondary)] underline-offset-2 hover:underline"
            onClick={() => setShowToolDetails((v) => !v)}
          >
            {t('spider.chat.todos.toolDetails')}
          </button>
          {showToolDetails && (
            <div className="mt-2 flex flex-col gap-2">
              {hiddenToolRuns.map((run, index) => (
                <ChatToolRunBlock
                  key={`hidden-${run.tool_name}-${index}`}
                  run={run}
                  isDarkMode={isDarkMode}
                />
              ))}
            </div>
          )}
        </div>
      )}
```

Keep existing `tool` / `failureSlot` / `content` / recovery blocks unchanged. Remove the old unconditional filter map that only skipped `execute_python` —它已被 `visibleToolRuns` 替代，但仍须继续过滤 `execute_python`。

- [ ] **Step 2: Pass `todos` from message list**

In `StudioChatMessageList.tsx`:

```tsx
            <StudioAssistantMessage
              thinking={msg.thinking}
              statusLabel={msg.statusLabel}
              isThinking={msg.isThinking}
              todos={msg.todos}
              toolRuns={msg.toolRuns}
              tool={msg.tool}
              content={msg.content}
              failureSlot={renderFailure?.(msg)}
              isDarkMode={isDarkMode}
              recoveryPrompt={msg.recoveryPrompt}
              onRecoveryRetry={msg.recoveryPrompt ? onRecoveryRetry : undefined}
              isRecoveryRetrying={isRecoveryRetrying}
            />
```

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/chat/StudioAssistantMessage.tsx frontend/src/components/chat/StudioChatMessageList.tsx
git commit -m "$(cat <<'EOF'
feat(spider): render todo card and hide write_todos by default

EOF
)"
```

---

### Task 9: Frontend — 流式消费 `todos_updated`

**Files:**
- Modify: `frontend/src/features/spider/hooks/useSpiderChat.ts`

- [ ] **Step 1: Import normalize helper**

```ts
import { normalizeSpiderTodos } from '@/features/spider/types/todo';
```

- [ ] **Step 2: Track todos + set `raw_tool_name` on tool runs**

Near `toolRuns` locals:

```ts
    let todos: ReturnType<typeof normalizeSpiderTodos> | undefined;
```

In `syncAssistant` patch type, add `todos?: typeof todos`。

In `tool_call_start` handler:

```ts
          const run: ChatToolRun = {
            call_id: event.call_id,
            tool_name: event.tool_name,
            raw_tool_name: 'raw_tool_name' in event ? event.raw_tool_name : undefined,
            tool_input: event.tool_args,
            status: 'running',
          };
```

After `tool_call_start` handling (or dedicated branch):

```ts
        if (event.type === 'todos_updated') {
          const next = normalizeSpiderTodos(event.todos);
          if (next.length > 0) {
            todos = next;
            syncAssistant({
              content: contentBuffer,
              statusLabel: currentWorkingText || undefined,
              isThinking: true,
              toolRuns: [...toolRuns],
              todos,
            });
          }
        }
```

Wherever `syncAssistant` / `syncWorkingStatus` already spreads `toolRuns`, also pass `todos` when defined:

```ts
        toolRuns: [...toolRuns],
        ...(todos ? { todos } : {}),
```

Apply this to **all** update paths in the same `onEvent` that currently set `toolRuns: [...toolRuns]`（start/progress/chunk/final/error/done），避免后续 patch 冲掉 todos。

- [ ] **Step 3: Commit**

```bash
git add frontend/src/features/spider/hooks/useSpiderChat.ts
git commit -m "$(cat <<'EOF'
feat(spider): apply todos_updated snapshots in chat stream

EOF
)"
```

---

### Task 10: Frontend — 会话恢复 todos

**Files:**
- Modify: `frontend/src/features/spider/services/api/sessions.ts`

- [ ] **Step 1: Import + map**

```ts
import { normalizeSpiderTodos } from '@/features/spider/types/todo';
```

In `mapStoredMessageToChat`, after parsing meta:

```ts
  const todos = normalizeSpiderTodos(meta?.todos);

  return {
    id: msg.id,
    role: role as 'user' | 'assistant',
    content: failure ? '' : msg.content,
    ...(toolRuns ? { toolRuns } : {}),
    ...(todos.length > 0 ? { todos } : {}),
    ...(failure ? { failure } : {}),
  };
```

When restoring `tool_trace`, set `raw_tool_name` if available so hidden filter works:

In `mapToolTraceToRuns`:

```ts
      raw_tool_name:
        typeof raw.raw_tool_name === 'string'
          ? raw.raw_tool_name
          : toolName === 'write_todos'
            ? 'write_todos'
            : undefined,
```

（持久化的 `tool_name` 对 write_todos 即为 `write_todos`，靠 `tool_name` 过滤也够；此项为增强。）

- [ ] **Step 2: Commit**

```bash
git add frontend/src/features/spider/services/api/sessions.ts
git commit -m "$(cat <<'EOF'
feat(spider): restore DeepAgent todos from spider_meta

EOF
)"
```

---

### Task 11: 手动冒烟验证

**Files:** none (manual)

- [ ] **Step 1: Restart backend** so API import switch takes effect（若 `start-macos-linux.sh` 未热重载，重启进程）。

- [ ] **Step 2: 简单任务**

在 Spider 页发一句简单请求（例如「你好」或「爬虫是什么」）。

Expected:
- 无 Todo 卡片
- 无「工具详情」入口（除非有其它被隐藏工具）

- [ ] **Step 3: 复杂任务**

配置好模型与 Docker，带 `target_url` 发复杂爬虫需求。

Expected:
- Agent 调用 `write_todos` 后出现卡片，`n/m 已完成` 随快照更新
- `completed` 项删除线 + 绿勾
- 默认工具流不出现 `write_todos` 块；「工具详情」可展开看到
- × 折叠为仅 header（或摘要）

- [ ] **Step 4: 刷新恢复**

刷新页面 / 切回同一会话。

Expected: 助手消息仍显示最终 todos 快照。

- [ ] **Step 5: 跑后端单测汇总**

Run: `cd backend && .venv/bin/pytest tests/spider/ -v`

Expected: all PASS

- [ ] **Step 6: Final commit only if there are leftover fixes**

若冒烟时修了小问题，单独 commit；否则结束。

---

## Spec coverage self-check

| Spec requirement | Task |
|------------------|------|
| 切回 DeepAgent | Task 4 |
| `todos_updated` SSE on write_todos start | Task 1–2 |
| 简单任务无卡片 | Task 7–9（空/无事件不渲染） |
| 卡片嵌助手消息、可折叠 | Task 7–8 |
| write_todos 进工具详情 | Task 8–9 |
| `spider_meta.todos` 持久化 + 恢复 | Task 3–4, 10 |
| 非法项过滤 | Task 1（后端）+ Task 5（前端 normalize） |
| 中断保留快照 | Task 4（latest_todos 不因 error 清空） |
| i18n | Task 6 |
| 不伪造 pipeline todo | 全任务均未做 |
| DeepAgent hang 非目标 | 未新增 hang 恢复 |

## Type consistency

- 后端/前端 status：`pending | in_progress | completed`
- 事件名：`todos_updated`
- 消息字段：`todos: SpiderTodoItem[]`
- 工具识别：`raw_tool_name === 'write_todos'` 或 `tool_name === 'write_todos'`
