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
    state.content_buffer = ""
    state.has_error = True
    assert resolve_persist_content(state, complete=True) == "任务执行失败"


def test_empty_state_not_persistable():
    assert has_persistable_snapshot(SpiderCheckpointState()) is False
