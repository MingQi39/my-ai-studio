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
