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
