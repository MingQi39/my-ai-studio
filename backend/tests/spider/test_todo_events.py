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
