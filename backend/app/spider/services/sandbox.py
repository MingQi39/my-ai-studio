"""Docker sandbox initialization and execute tool factory."""

from __future__ import annotations

import json
import re
import time
from typing import Any

from langchain_core.tools import tool

from app.config import settings
from app.spider.services.docker_backend import DockerBackend
from app.spider.services.sandbox_workspace import SandboxWorkspace
try:
    import docker
    from docker.errors import NotFound
except ImportError:  # pragma: no cover - optional dependency
    docker = None


def _count_scraped_records(scraped_text: str | None) -> int:
    """Return usable record count from scraped_data.json contents."""
    if not scraped_text or not scraped_text.strip():
        return 0
    try:
        data = json.loads(scraped_text)
    except (TypeError, ValueError, json.JSONDecodeError):
        return 0
    if isinstance(data, list):
        return sum(1 for item in data if item)
    if isinstance(data, dict):
        if data.get("error"):
            return 0
        return 1 if data else 0
    return 0


def _sanitize_volume_token(value: str) -> str:
    token = re.sub(r"[^a-zA-Z0-9_.-]", "-", value.strip())[:48]
    return token or "unknown"


def volume_name_for_session(user_id: str, session_id: str) -> str:
    return f"spider-{_sanitize_volume_token(user_id)}-{_sanitize_volume_token(session_id)}"


def container_name_for_session(session_id: str) -> str:
    """Stable Desktop-friendly name grouped under the compose project prefix."""
    return f"my-ai-studio-spider-{_sanitize_volume_token(session_id)}"


def _ensure_volume(client: Any, volume_name: str) -> None:
    try:
        client.volumes.get(volume_name)
    except NotFound:
        client.volumes.create(name=volume_name)


def _container_matches_configured_image(client: Any, container: Any, image: str) -> bool:
    """True when the running container was created from settings.SPIDER_DOCKER_IMAGE."""
    try:
        expected = client.images.get(image)
    except NotFound:
        return False
    try:
        return container.image.id == expected.id
    except Exception:
        return False


def _find_session_container(client: Any, session_id: str) -> str | None:
    label = f"spider.session_id={session_id}"
    containers = client.containers.list(all=True, filters={"label": label})
    if not containers:
        return None
    container = containers[0]
    if not _container_matches_configured_image(client, container, settings.SPIDER_DOCKER_IMAGE):
        try:
            container.remove(force=True)
        except Exception:
            pass
        return None
    if container.status != "running":
        container.start()
    return container.id


def _create_session_container(
    client: Any,
    *,
    volume_name: str,
    mount_path: str,
    user_id: str,
    session_id: str,
) -> str:
    container = client.containers.run(
        settings.SPIDER_DOCKER_IMAGE,
        name=container_name_for_session(session_id),
        command="tail -f /dev/null",
        detach=True,
        tty=True,
        # Chromium in Docker needs larger /dev/shm or --disable-dev-shm-usage;
        # bump shm so heavy pages (Weibo SPA) are less likely to crash mid-fetch.
        shm_size=settings.SPIDER_DOCKER_SHM_SIZE,
        labels={
            "spider.session_id": session_id,
            "spider.user_id": user_id,
            "spider.app": "my-ai-studio",
            # So Docker Desktop groups sandboxes under the my-ai-studio project.
            "com.docker.compose.project": "my-ai-studio",
            "com.docker.compose.service": "spider",
        },
        volumes={volume_name: {"bind": mount_path, "mode": "rw"}},
        working_dir=mount_path,
        mem_limit=settings.SPIDER_DOCKER_MEMORY_LIMIT,
        cpu_quota=settings.SPIDER_DOCKER_CPU_QUOTA,
        network_disabled=False,
        auto_remove=False,
    )
    return container.id


def remove_session_sandbox(session_id: str) -> None:
    """Best-effort remove of the per-session spider sandbox container."""
    if docker is None:
        return
    try:
        client = docker.from_env()
    except Exception:
        return
    label = f"spider.session_id={session_id}"
    try:
        containers = client.containers.list(all=True, filters={"label": label})
    except Exception:
        return
    for container in containers:
        try:
            container.remove(force=True)
        except Exception:
            pass


def initialize_session_sandbox(user_id: str, session_id: str) -> SandboxWorkspace:
    """Open or create a per-session Docker sandbox backed by a named volume."""
    if docker is None:
        raise ImportError(
            "docker package is not installed. Please install it with `pip install docker`."
        )

    volume_name = volume_name_for_session(user_id, session_id)
    mount_path = settings.SPIDER_CONTAINER_MOUNT_PATH.rstrip("/")
    client = docker.from_env()

    _ensure_volume(client, volume_name)

    container_id = _find_session_container(client, session_id)
    if container_id is None:
        container_id = _create_session_container(
            client,
            volume_name=volume_name,
            mount_path=mount_path,
            user_id=user_id,
            session_id=session_id,
        )

    backend = DockerBackend(
        image=settings.SPIDER_DOCKER_IMAGE,
        container_id=container_id,
        network_disabled=False,
        memory_limit=settings.SPIDER_DOCKER_MEMORY_LIMIT,
        cpu_quota=settings.SPIDER_DOCKER_CPU_QUOTA,
        auto_remove=False,
        working_dir=mount_path,
    )

    return SandboxWorkspace(
        backend=backend,
        container_path=mount_path,
        volume_name=volume_name,
        user_id=user_id,
        session_id=session_id,
    )


def create_execute_in_sandbox_tool(workspace: SandboxWorkspace):
    @tool
    async def execute_in_sandbox(code: str, timeout: int = 60) -> dict[str, Any]:
        """在 Docker 沙箱中执行爬虫代码。"""
        del timeout
        start_time = time.time()
        backend = workspace.backend

        try:
            from app.spider.services.request_cookies import (
                RUNTIME_COOKIE_FILENAME,
                get_request_cookies,
            )

            workspace.write_text("spider.py", code)

            check_result = backend.execute("pip show requests > /dev/null 2>&1")
            if check_result.exit_code != 0:
                backend.execute(
                    "pip install --no-cache-dir requests beautifulsoup4 lxml fake-useragent 2>&1"
                )

            cookie = get_request_cookies()
            if cookie:
                workspace.write_text(RUNTIME_COOKIE_FILENAME, cookie)
                cookie_export = (
                    f'export SPIDER_COOKIE="$(cat {RUNTIME_COOKIE_FILENAME} 2>/dev/null)"; '
                )
            else:
                cookie_export = ""

            try:
                exec_result = backend.execute(
                    f"cd {backend.working_dir} && {cookie_export}python spider.py 2>&1"
                )
            finally:
                if cookie:
                    backend.execute(f"rm -f {RUNTIME_COOKIE_FILENAME}")

            duration = time.time() - start_time

            scraped_data = None
            try:
                scraped_data = workspace.read_text("scraped_data.json")
                if scraped_data:
                    workspace.write_text("raw_data.json", scraped_data)
            except Exception:
                pass

            record_count = _count_scraped_records(scraped_data)
            data_saved = record_count > 0
            exit_ok = exec_result.exit_code == 0
            success = exit_ok and data_saved

            output_preview = exec_result.output[:500] if exec_result.output else ""
            if exec_result.output and len(exec_result.output) > 500:
                output_preview += f"\n... [截断 {len(exec_result.output) - 500} 字符]"

            error: str | None = None
            if not success:
                if not exit_ok:
                    error = output_preview or f"exit_code={exec_result.exit_code}"
                elif scraped_data is None:
                    error = (
                        "脚本退出码为 0，但未生成 scraped_data.json。"
                        "常见原因：入口未真正执行（如 async main 未 asyncio.run）、"
                        "或只在条数达标时才写文件。"
                    )
                else:
                    error = (
                        "脚本退出码为 0，但 scraped_data.json 为空（0 条有效记录）。"
                        "常见原因：目标页不是列表页、CSS 选择器与页面结构不匹配、或页面内容被反爬屏蔽。"
                    )
                if output_preview and exit_ok:
                    error = f"{error}\n运行输出: {output_preview}"

            return {
                "success": success,
                "output_preview": output_preview,
                "exit_code": exec_result.exit_code,
                "error": error,
                "duration": duration,
                "data_saved": data_saved,
                "record_count": record_count,
                "data_file": "scraped_data.json" if scraped_data is not None else None,
            }
        except Exception as exc:
            return {
                "success": False,
                "error": str(exc)[:200],
                "exit_code": 1,
                "duration": time.time() - start_time,
            }

    return execute_in_sandbox


def list_workspace_files(workspace: SandboxWorkspace) -> list[dict[str, Any]]:
    from app.spider.services.request_cookies import RUNTIME_COOKIE_FILENAME

    try:
        files = workspace.list_files()
    except Exception:
        return []
    hidden = {RUNTIME_COOKIE_FILENAME}
    return [
        item
        for item in files
        if not str(item.get("name", "")).endswith(".meta.json")
        and str(item.get("name", "")) not in hidden
    ]
