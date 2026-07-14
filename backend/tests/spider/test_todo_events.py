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
