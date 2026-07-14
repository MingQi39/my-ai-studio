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
    assert "SPIDER_COOKIE" in PLAYWRIGHT_FETCH_SCRIPT
    assert "set_extra_http_headers" in PLAYWRIGHT_FETCH_SCRIPT
    assert "--disable-dev-shm-usage" in PLAYWRIGHT_FETCH_SCRIPT
    assert "document.documentElement.outerHTML" in PLAYWRIGHT_FETCH_SCRIPT


def test_playwright_fetch_script_handles_content_errors():
    assert "traceback" in PLAYWRIGHT_FETCH_SCRIPT.lower() or "Traceback" in PLAYWRIGHT_FETCH_SCRIPT
    assert "except Exception" in PLAYWRIGHT_FETCH_SCRIPT or "except Exception as" in PLAYWRIGHT_FETCH_SCRIPT


def test_probe_playwright_available_true():
    backend = SimpleNamespace(execute=lambda cmd: SimpleNamespace(exit_code=0, output="ok"))
    workspace = SimpleNamespace(backend=backend)
    assert probe_playwright_available(workspace) is True


def test_probe_playwright_available_false():
    backend = SimpleNamespace(execute=lambda cmd: SimpleNamespace(exit_code=1, output="No module"))
    workspace = SimpleNamespace(backend=backend)
    assert probe_playwright_available(workspace) is False


def test_probe_playwright_available_installs_package_when_browsers_exist():
    """Official image has browsers but may lack the playwright Python package."""
    calls: list[str] = []

    def execute(cmd: str):
        calls.append(cmd)
        if "from playwright.sync_api" in cmd:
            # Fail until pip install has run
            if any("pip install" in c and "playwright" in c for c in calls[:-1]):
                return SimpleNamespace(exit_code=0, output="ok")
            return SimpleNamespace(exit_code=1, output="No module named 'playwright'")
        if "ms-playwright" in cmd or "PLAYWRIGHT_BROWSERS_PATH" in cmd:
            return SimpleNamespace(exit_code=0, output="ok")
        if "pip install" in cmd and "playwright" in cmd:
            return SimpleNamespace(exit_code=0, output="Successfully installed playwright")
        return SimpleNamespace(exit_code=1, output="unexpected")

    workspace = SimpleNamespace(backend=SimpleNamespace(execute=execute))
    assert probe_playwright_available(workspace) is True
    assert any("pip install" in c and "playwright" in c for c in calls)


def test_probe_playwright_available_false_without_browsers_or_package():
    def execute(cmd: str):
        if "from playwright.sync_api" in cmd:
            return SimpleNamespace(exit_code=1, output="No module")
        if "ms-playwright" in cmd or "PLAYWRIGHT_BROWSERS_PATH" in cmd:
            return SimpleNamespace(exit_code=1, output="missing")
        return SimpleNamespace(exit_code=1, output="fail")

    workspace = SimpleNamespace(backend=SimpleNamespace(execute=execute))
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
