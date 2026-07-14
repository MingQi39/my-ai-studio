# Spider Run Checkpoint Restore Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 流式执行过程中增量 upsert 助手消息（含 pending 工具），页面刷新后完整恢复第一次执行气泡内已展示的工具 / 子 agent / todos / 正文 / failure。

**Architecture:** 抽出纯函数状态机 `stream_checkpoint` 消费 SSE 事件并产出有序 `tool_trace`；`_persist_spider_stream` 在显著事件与 finally 中调用 `upsert_spider_assistant_message`；前端映射 `isComplete`，恢复时对未完成消息打中断态。

**Tech Stack:** FastAPI、SQLAlchemy async `SessionService`、现有 `spider_meta`、React `useSpiderSessionRestore`

**Spec:** `docs/superpowers/specs/2026-07-14-spider-run-checkpoint-restore-design.md`

---

## File map

| File | Responsibility |
|------|----------------|
| `backend/app/spider/services/stream_checkpoint.py` | 纯状态机：事件 → 快照 / 是否立即 checkpoint |
| `backend/app/services/session_service.py` | 新增 `update_message` |
| `backend/app/spider/services/chat_persistence.py` | `upsert_spider_assistant_message` |
| `backend/app/api/v1/spider.py` | `_persist_spider_stream` 增量落库 + finally |
| `backend/tests/spider/test_stream_checkpoint.py` | 状态机单测 |
| `backend/tests/spider/test_upsert_assistant_message.py` | upsert 契约（AsyncMock） |
| `backend/tests/spider/test_persist_spider_stream.py` | persist 流集成（fake stream + mock service） |
| `frontend/src/features/spider/services/api/sessions.ts` | 映射 `isComplete` |
| `frontend/src/features/spider/hooks/useSpiderSessionRestore.ts` | 中断判定含 `isComplete === false` |
| `frontend/src/hooks/studioChat/types.ts` | 已有 `isComplete?`，确认即可，一般不必改 |

---

### Task 1: Backend — `stream_checkpoint` 纯状态机

**Files:**
- Create: `backend/app/spider/services/stream_checkpoint.py`
- Create: `backend/tests/spider/test_stream_checkpoint.py`

- [ ] **Step 1: Write the failing tests**

```python
# backend/tests/spider/test_stream_checkpoint.py
from app.spider.services.stream_checkpoint import (
    SpiderCheckpointState,
    apply_persist_event,
    has_persistable_snapshot,
    ordered_tool_trace,
    resolve_persist_content,
)


def test_tool_start_keeps_pending_in_ordered_trace():
    state = SpiderCheckpointState()
    action = apply_persist_event(
        state,
        {
            "type": "tool_call_start",
            "call_id": "c1",
            "tool_name": "task",
            "raw_tool_name": "task",
            "tool_args": {"subagent_type": "code_generator"},
        },
    )
    assert action == "immediate"
    trace = ordered_tool_trace(state)
    assert len(trace) == 1
    assert trace[0]["id"] == "c1"
    assert trace[0]["status"] == "pending"
    assert trace[0]["raw_tool_name"] == "task"
    assert has_persistable_snapshot(state) is True


def test_tool_result_updates_same_entry_not_duplicate():
    state = SpiderCheckpointState()
    apply_persist_event(
        state,
        {
            "type": "tool_call_start",
            "call_id": "c1",
            "tool_name": "task",
            "tool_args": {},
        },
    )
    action = apply_persist_event(
        state,
        {
            "type": "tool_call_result",
            "call_id": "c1",
            "result": "ok",
            "status": "success",
        },
    )
    assert action == "immediate"
    trace = ordered_tool_trace(state)
    assert len(trace) == 1
    assert trace[0]["status"] == "success"
    assert trace[0]["result"] == "ok"


def test_ordered_trace_preserves_start_order_with_mixed_pending():
    state = SpiderCheckpointState()
    apply_persist_event(
        state,
        {"type": "tool_call_start", "call_id": "a", "tool_name": "task", "tool_args": {}},
    )
    apply_persist_event(
        state,
        {
            "type": "tool_call_result",
            "call_id": "a",
            "result": "done",
            "status": "success",
        },
    )
    apply_persist_event(
        state,
        {"type": "tool_call_start", "call_id": "b", "tool_name": "task", "tool_args": {}},
    )
    ids = [item["id"] for item in ordered_tool_trace(state)]
    assert ids == ["a", "b"]
    assert ordered_tool_trace(state)[1]["status"] == "pending"


def test_todos_and_error_are_immediate():
    state = SpiderCheckpointState()
    assert (
        apply_persist_event(
            state,
            {
                "type": "todos_updated",
                "todos": [{"content": "分析", "status": "in_progress"}],
            },
        )
        == "immediate"
    )
    assert state.latest_todos == [{"content": "分析", "status": "in_progress"}]

    assert (
        apply_persist_event(
            state,
            {
                "type": "error",
                "message": "失败了",
                "code": "x",
                "title": "错误",
            },
        )
        == "immediate"
    )
    assert state.has_error is True
    assert state.failure is not None
    assert state.content_buffer == "失败了"


def test_chunk_returns_debounced():
    state = SpiderCheckpointState()
    assert apply_persist_event(state, {"type": "chunk", "content": "你好"}) == "debounced"
    assert state.content_buffer == "你好"


def test_resolve_content_incomplete_keeps_empty():
    state = SpiderCheckpointState()
    assert resolve_persist_content(state, complete=False) == ""


def test_resolve_content_complete_uses_placeholder():
    state = SpiderCheckpointState()
    apply_persist_event(
        state,
        {"type": "tool_call_start", "call_id": "c1", "tool_name": "task", "tool_args": {}},
    )
    assert resolve_persist_content(state, complete=True) == "（无回复内容）"


def test_resolve_content_complete_error_fallback():
    state = SpiderCheckpointState()
    apply_persist_event(state, {"type": "error", "message": "", "title": "任务执行失败"})
    # message empty → has_error with empty buffer
    state.content_buffer = ""
    state.has_error = True
    assert resolve_persist_content(state, complete=True) == "任务执行失败"


def test_empty_state_not_persistable():
    assert has_persistable_snapshot(SpiderCheckpointState()) is False
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && .venv/bin/pytest tests/spider/test_stream_checkpoint.py -v`

Expected: FAIL（模块不存在）

- [ ] **Step 3: Implement**

```python
# backend/app/spider/services/stream_checkpoint.py
"""In-memory checkpoint state for spider SSE persistence."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

from app.spider.services.todo_events import normalize_todos

PersistAction = Literal["immediate", "debounced", "none"]


@dataclass
class SpiderCheckpointState:
    content_buffer: str = ""
    pending: dict[str, dict[str, Any]] = field(default_factory=dict)
    order: list[str] = field(default_factory=list)
    has_error: bool = False
    failure: dict[str, Any] | None = None
    latest_todos: list[dict[str, str]] | None = None


def ordered_tool_trace(state: SpiderCheckpointState) -> list[dict[str, Any]]:
    return [state.pending[call_id] for call_id in state.order if call_id in state.pending]


def has_persistable_snapshot(state: SpiderCheckpointState) -> bool:
    return bool(
        state.content_buffer
        or state.order
        or state.failure
        or state.latest_todos
    )


def resolve_persist_content(state: SpiderCheckpointState, *, complete: bool) -> str:
    if state.content_buffer:
        return state.content_buffer
    if not complete:
        return ""
    if state.has_error:
        return "任务执行失败"
    return "（无回复内容）"


def apply_persist_event(state: SpiderCheckpointState, event: dict[str, Any]) -> PersistAction:
    etype = event.get("type")

    if etype == "chunk" and event.get("content"):
        state.content_buffer += str(event["content"])
        return "debounced"

    if etype == "final_response" and event.get("content"):
        state.content_buffer = str(event["content"])
        return "debounced"

    if etype == "tool_call_start":
        call_id = str(event.get("call_id") or "")
        if not call_id:
            return "none"
        entry = {
            "id": call_id,
            "tool_name": event.get("tool_name") or event.get("raw_tool_name") or "unknown",
            "tool_args": event.get("tool_args") or {},
            "status": "pending",
        }
        if event.get("raw_tool_name"):
            entry["raw_tool_name"] = event.get("raw_tool_name")
        if call_id not in state.pending:
            state.order.append(call_id)
        state.pending[call_id] = entry
        return "immediate"

    if etype == "tool_call_result":
        call_id = str(event.get("call_id") or "")
        if not call_id or call_id not in state.pending:
            return "none"
        entry = state.pending[call_id]
        entry["result"] = event.get("result")
        entry["status"] = event.get("status") or ("error" if event.get("error") else "success")
        if event.get("error") is not None:
            entry["error"] = event.get("error")
        return "immediate"

    if etype == "todos_updated":
        normalized = normalize_todos(event.get("todos"))
        if not normalized:
            return "none"
        state.latest_todos = normalized
        return "immediate"

    if etype == "error":
        state.has_error = True
        if event.get("message"):
            state.content_buffer = str(event["message"])
        state.failure = {
            "code": event.get("code"),
            "title": event.get("title") or "任务执行失败",
            "detail": event.get("detail") or event.get("message") or "",
            "hints": event.get("hints") or [],
            "stage": event.get("stage"),
            "recoverable": bool(event.get("recoverable")),
        }
        return "immediate"

    return "none"
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && .venv/bin/pytest tests/spider/test_stream_checkpoint.py -v`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/spider/services/stream_checkpoint.py backend/tests/spider/test_stream_checkpoint.py
git commit -m "feat(spider): add stream checkpoint state machine for mid-run persist"
```

---

### Task 2: Backend — `SessionService.update_message` + `upsert_spider_assistant_message`

**Files:**
- Modify: `backend/app/services/session_service.py`（在 `add_message` 后新增 `update_message`）
- Modify: `backend/app/spider/services/chat_persistence.py`
- Create: `backend/tests/spider/test_upsert_assistant_message.py`

- [ ] **Step 1: Write the failing tests**

```python
# backend/tests/spider/test_upsert_assistant_message.py
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from app.spider.services.chat_persistence import upsert_spider_assistant_message


@pytest.mark.asyncio
async def test_upsert_creates_when_message_id_none():
    session_id = uuid4()
    created_id = uuid4()
    session_service = MagicMock()
    msg = MagicMock()
    msg.id = str(created_id)
    session_service.add_message = AsyncMock(return_value=msg)

    result = await upsert_spider_assistant_message(
        session_service=session_service,
        session_id=session_id,
        message_id=None,
        content="",
        tool_trace=[{"id": "c1", "tool_name": "task", "status": "pending"}],
        is_complete=False,
    )

    assert result == created_id
    session_service.add_message.assert_awaited_once()
    kwargs = session_service.add_message.await_args
    data = kwargs.args[1]
    assert data.is_complete is False
    assert data.content == ""
    assert data.tool_calls[0]["tool_trace"][0]["status"] == "pending"
    session_service.update_message.assert_not_called()


@pytest.mark.asyncio
async def test_upsert_updates_existing_message():
    session_id = uuid4()
    message_id = uuid4()
    session_service = MagicMock()
    session_service.update_message = AsyncMock(return_value=MagicMock())

    result = await upsert_spider_assistant_message(
        session_service=session_service,
        session_id=session_id,
        message_id=message_id,
        content="你好",
        tool_trace=[{"id": "c1", "tool_name": "task", "status": "success", "result": "ok"}],
        todos=[{"content": "分析", "status": "completed"}],
        is_complete=True,
    )

    assert result == message_id
    session_service.update_message.assert_awaited_once()
    call_kwargs = session_service.update_message.await_args.kwargs
    assert call_kwargs["content"] == "你好"
    assert call_kwargs["is_complete"] is True
    assert call_kwargs["tool_calls"][0]["todos"][0]["content"] == "分析"
    session_service.add_message.assert_not_called()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && .venv/bin/pytest tests/spider/test_upsert_assistant_message.py -v`

Expected: FAIL（`upsert_spider_assistant_message` 未定义）

- [ ] **Step 3: Implement `update_message` on SessionService**

在 `add_message` 方法之后插入：

```python
async def update_message(
    self,
    message_id: UUID,
    *,
    content: str | None = None,
    tool_calls: list[dict] | None = None,
    is_complete: bool | None = None,
    thinking_content: str | None = None,
) -> Optional[Message]:
    """Update an existing message's content / tool_calls / completion flag."""
    message = await self.get_message(message_id)
    if not message:
        return None

    if content is not None:
        message.content = content
    if tool_calls is not None:
        message.tool_calls = tool_calls
    if is_complete is not None:
        message.is_complete = is_complete
    if thinking_content is not None:
        message.thinking_content = thinking_content

    # bump session updated_at
    stmt = select(Session).where(Session.id == message.session_id)
    result = await self.db.execute(stmt)
    session = result.scalar_one_or_none()
    if session:
        session.updated_at = datetime.utcnow()

    await self.db.commit()
    await self.db.refresh(message)
    return message
```

确保文件顶部已有 `select`、`Session`、`datetime`、`Optional`、`Message` 导入（本文件已具备则勿重复）。

- [ ] **Step 4: Implement `upsert_spider_assistant_message`**

在 `chat_persistence.py` 的 `save_spider_assistant_message` 旁新增：

```python
async def upsert_spider_assistant_message(
    session_service: SessionService,
    session_id: UUID,
    content: str,
    *,
    message_id: UUID | None = None,
    tool_trace: list[dict[str, Any]] | None = None,
    failure: dict[str, Any] | None = None,
    todos: list[dict[str, Any]] | None = None,
    is_complete: bool = True,
) -> UUID:
    tool_calls = build_spider_tool_calls(
        tool_trace=tool_trace,
        failure=failure,
        todos=todos,
    )
    if message_id is None:
        message = await session_service.add_message(
            session_id,
            MessageCreate(
                role=MessageRole.assistant,
                content=content,
                tool_calls=tool_calls,
                is_complete=is_complete,
            ),
        )
        return UUID(str(message.id))

    await session_service.update_message(
        message_id,
        content=content,
        tool_calls=tool_calls,
        is_complete=is_complete,
    )
    return message_id
```

保留现有 `save_spider_assistant_message`（可内部改为调用 upsert，或原样保留给其他调用方；本规格新路径用 upsert）。

- [ ] **Step 5: Run tests**

Run: `cd backend && .venv/bin/pytest tests/spider/test_upsert_assistant_message.py -v`

Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add backend/app/services/session_service.py backend/app/spider/services/chat_persistence.py backend/tests/spider/test_upsert_assistant_message.py
git commit -m "feat(spider): upsert in-progress assistant messages for checkpoint"
```

---

### Task 3: Backend — 改造 `_persist_spider_stream`

**Files:**
- Modify: `backend/app/api/v1/spider.py`
- Create: `backend/tests/spider/test_persist_spider_stream.py`

- [ ] **Step 1: Write the failing tests**

```python
# backend/tests/spider/test_persist_spider_stream.py
import asyncio
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from app.api.v1.spider import _persist_spider_stream


async def _collect(agen):
    return [item async for item in agen]


@pytest.mark.asyncio
async def test_persist_checkpoints_on_tool_start_and_finalizes():
    session_id = uuid4()
    message_id = uuid4()
    session_service = MagicMock()

    # First upsert (create) returns id; subsequent updates keep same id
    created = MagicMock()
    created.id = str(message_id)

    async def fake_stream():
        yield {
            "type": "tool_call_start",
            "call_id": "c1",
            "tool_name": "task",
            "raw_tool_name": "task",
            "tool_args": {"subagent_type": "code_generator"},
        }
        yield {
            "type": "tool_call_result",
            "call_id": "c1",
            "result": "ok",
            "status": "success",
        }
        yield {"type": "final_response", "content": "完成"}
        yield {"type": "done"}

    upsert = AsyncMock(side_effect=[message_id, message_id, message_id])
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(
            "app.api.v1.spider.upsert_spider_assistant_message",
            upsert,
        )
        events = await _collect(_persist_spider_stream(fake_stream(), session_service, session_id))

    assert any(e.get("type") == "tool_call_start" for e in events)
    # at least one incomplete checkpoint + one complete finalize
    assert upsert.await_count >= 2
    final_kwargs = upsert.await_args_list[-1].kwargs
    assert final_kwargs.get("is_complete") is True or (
        len(upsert.await_args_list[-1].args) >= 0
        and upsert.await_args_list[-1].kwargs.get("is_complete", True) is True
    )
    # Prefer checking call kwargs for is_complete True on last call:
    last_call = upsert.await_args_list[-1]
    assert last_call.kwargs["is_complete"] is True
    assert last_call.kwargs["content"] == "完成"
    trace = last_call.kwargs["tool_trace"]
    assert len(trace) == 1
    assert trace[0]["status"] == "success"


@pytest.mark.asyncio
async def test_persist_flush_incomplete_on_cancel():
    session_id = uuid4()
    message_id = uuid4()
    session_service = MagicMock()
    upsert = AsyncMock(return_value=message_id)

    async def fake_stream():
        yield {
            "type": "tool_call_start",
            "call_id": "c1",
            "tool_name": "task",
            "tool_args": {},
        }
        raise asyncio.CancelledError()

    with pytest.MonkeyPatch.context() as mp:
        mp.setattr("app.api.v1.spider.upsert_spider_assistant_message", upsert)
        with pytest.raises(asyncio.CancelledError):
            await _collect(_persist_spider_stream(fake_stream(), session_service, session_id))

    assert upsert.await_count >= 1
    last = upsert.await_args_list[-1]
    assert last.kwargs["is_complete"] is False
    assert last.kwargs["tool_trace"][0]["status"] == "pending"
```

测试里对 `upsert` 的 kwargs 签名须与实现一致（见 Step 3）：统一使用关键字参数 `content=` / `tool_trace=` / `is_complete=` / `message_id=`。

若 `MonkeyPatch.context()` 在项目 pytest 版本不便，改用：

```python
from unittest.mock import patch

with patch("app.api.v1.spider.upsert_spider_assistant_message", upsert):
    ...
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && .venv/bin/pytest tests/spider/test_persist_spider_stream.py -v`

Expected: FAIL（仍用旧 persist 行为）

- [ ] **Step 3: Rewrite `_persist_spider_stream`**

替换 `backend/app/api/v1/spider.py` 中该函数与相关 import：

```python
from app.spider.services.chat_persistence import (
    messages_to_history,
    resolve_spider_session,
    save_spider_user_message,
    upsert_spider_assistant_message,
)
from app.spider.services.stream_checkpoint import (
    SpiderCheckpointState,
    apply_persist_event,
    has_persistable_snapshot,
    ordered_tool_trace,
    resolve_persist_content,
)

CHUNK_CHECKPOINT_INTERVAL_S = 2.0
CHUNK_CHECKPOINT_MIN_CHARS = 200


async def _persist_spider_stream(
    stream: AsyncIterator[dict[str, Any]],
    session_service,
    session_id: UUID,
) -> AsyncIterator[dict[str, Any]]:
    state = SpiderCheckpointState()
    assistant_message_id: UUID | None = None
    last_flush_at = 0.0
    chars_since_flush = 0
    finalized = False

    async def flush(*, is_complete: bool) -> None:
        nonlocal assistant_message_id, last_flush_at, chars_since_flush, finalized
        if not has_persistable_snapshot(state):
            return
        if is_complete:
            finalized = True
        content = resolve_persist_content(state, complete=is_complete)
        trace = ordered_tool_trace(state)
        try:
            assistant_message_id = await upsert_spider_assistant_message(
                session_service=session_service,
                session_id=session_id,
                message_id=assistant_message_id,
                content=content,
                tool_trace=trace if trace else None,
                failure=state.failure,
                todos=state.latest_todos,
                is_complete=is_complete,
            )
        except Exception:
            # checkpoint failure must not kill SSE
            pass
        last_flush_at = asyncio.get_event_loop().time()
        chars_since_flush = 0

    try:
        async for event in stream:
            yield event
            action = apply_persist_event(state, event)

            if action == "immediate":
                await flush(is_complete=False)
            elif action == "debounced":
                chars_since_flush += len(str(event.get("content") or ""))
                now = asyncio.get_event_loop().time()
                if (
                    chars_since_flush >= CHUNK_CHECKPOINT_MIN_CHARS
                    or (now - last_flush_at) >= CHUNK_CHECKPOINT_INTERVAL_S
                ):
                    await flush(is_complete=False)

        if has_persistable_snapshot(state):
            await flush(is_complete=True)
    except (asyncio.CancelledError, GeneratorExit):
        if not finalized and has_persistable_snapshot(state):
            await flush(is_complete=False)
        raise
    finally:
        if not finalized and has_persistable_snapshot(state):
            await flush(is_complete=False)
```

注意：

- 删除对 `save_spider_assistant_message` / `normalize_todos` 在本文件内的旧用法（todos 已在状态机处理）。
- `finally` 与 `except` 都可能 flush：保证 **最多一条** 助手消息（依赖 upsert 同 id）；`finalized` 防止完成后 finally 再写成 `is_complete=False`。
- `asyncio.get_event_loop().time()` 若告警，可改 `asyncio.get_running_loop().time()`。

- [ ] **Step 4: Run tests**

Run: `cd backend && .venv/bin/pytest tests/spider/test_persist_spider_stream.py tests/spider/test_stream_checkpoint.py tests/spider/test_upsert_assistant_message.py -v`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/api/v1/spider.py backend/tests/spider/test_persist_spider_stream.py
git commit -m "feat(spider): checkpoint assistant message during SSE and on disconnect"
```

---

### Task 4: Frontend — 映射 `isComplete` + 恢复中断判定

**Files:**
- Modify: `frontend/src/features/spider/services/api/sessions.ts`
- Modify: `frontend/src/features/spider/hooks/useSpiderSessionRestore.ts`
- Confirm: `frontend/src/hooks/studioChat/types.ts` 已有 `isComplete?: boolean`（无需改则跳过）

- [ ] **Step 1: Update `mapStoredMessageToChat`**

在 `sessions.ts` 的 return 对象中增加：

```ts
isComplete: msg.is_complete !== false,
```

完整 return 示例片段：

```ts
  return {
    id: msg.id,
    role: role as 'user' | 'assistant',
    content: failure ? '' : msg.content,
    isComplete: msg.is_complete !== false,
    ...(toolRuns ? { toolRuns } : {}),
    ...(todos.length > 0 ? { todos } : {}),
    ...(failure ? { failure } : {}),
  };
```

- [ ] **Step 2: Expand interrupt detection in `useSpiderSessionRestore`**

替换 restore `.then` 内逻辑：

```ts
      .then(({ messages: restored, targetUrl }) => {
        const wasGenerating =
          sessionStorage.getItem(SPIDER_GENERATING_SESSION_KEY) === currentSessionId;
        const hasIncomplete = restored.some(
          (message) => message.role === 'assistant' && message.isComplete === false,
        );
        const interrupted = wasGenerating || hasIncomplete;

        if (wasGenerating) {
          sessionStorage.removeItem(SPIDER_GENERATING_SESSION_KEY);
        }

        if (interrupted) {
          setRestoreInterruptedHint(true);
          setMessages(markInterruptedToolRuns(restored));
        } else {
          setRestoreInterruptedHint(false);
          setMessages(restored);
        }
        setTargetUrl(targetUrl ?? readStoredTargetUrl(currentSessionId));
        void refreshWorkspace();
      })
```

`markInterruptedToolRuns` 保持不变（只把 `running` → `error` + 中断文案，并清 `isThinking`）。

- [ ] **Step 3: Typecheck（可选快速校验）**

Run: `cd frontend && npx tsc --noEmit -p tsconfig.json 2>&1 | head -40`

Expected: 与 spider 改动相关的文件无新增错误（若仓库已有无关错误，忽略非本改动文件）。

- [ ] **Step 4: Commit**

```bash
git add frontend/src/features/spider/services/api/sessions.ts frontend/src/features/spider/hooks/useSpiderSessionRestore.ts
git commit -m "fix(spider): restore mid-run tool/todo UI after page refresh"
```

---

### Task 5: 手动冒烟

**Files:** 无代码改动

- [ ] **Step 1: 启动前后端**（若未在跑）

- [ ] **Step 2: 中途刷新**

1. 打开 Spider 会话，发一条会跑多阶段工具的任务（如爬取豆瓣电影标题）。
2. 至少一个工具块已出现、任务尚未 `done` 时刷新浏览器。
3. **期望：**
   - 气泡内仍能看到刷新前已出现的工具 / 子 agent 块（含输出）。
   - 仍在跑的块为失败/中断文案，不再转圈。
   - 若有 todos，卡片仍在。
   - 顶部浅蓝 `restoreInterrupted` 条出现。
   - 右侧工作区短时自动刷新。

- [ ] **Step 3: 正常完成再刷新**

1. 等任务跑完。
2. 刷新。
3. **期望：** 终态完整、`is_complete` 助手仅一条、无中断条（且无 generating 标记）。

- [ ] **Step 4: 提交冒烟无代码则跳过 commit**；若冒烟发现需小修，修完再单独 commit。

---

## Spec coverage checklist

| Spec 要求 | Task |
|-----------|------|
| 增量 upsert + 单条消息 | 2, 3 |
| tool_trace 含 pending、按开始顺序 | 1, 3 |
| 显著事件立即写 / chunk 防抖 | 1, 3 |
| 断开 finally `is_complete=False` | 3 |
| 正常结束 `is_complete=True` | 3 |
| 无占位「执行中…」 | 1 `resolve_persist_content` |
| 前端 `isComplete` + 中断判定 | 4 |
| 不恢复 statusLabel | 4（未写入 messages） |
| 实时 UI 不改主交互 | 4（未改 useSpiderChat） |
| Checkpoint 失败不杀 SSE | 3 `flush` try/except |

---

## Self-review notes

- 无 TBD /「类似 Task N」占位。
- `upsert_spider_assistant_message` 签名在 Task 2/3 一致：`message_id` 关键字、返回 `UUID`。
- `StudioChatMessage.isComplete` 类型已存在，Task 4 只做映射与恢复逻辑。
- `save_spider_assistant_message` 可保留以免破坏其他调用；新 persist 路径只用 upsert。
