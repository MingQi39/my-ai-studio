"""Docker sandbox workspace — all session artifacts live in a named volume."""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any

from app.spider.services.docker_backend import DockerBackend
from app.spider.services.file_mtime import format_file_mtime


@dataclass
class SandboxWorkspace:
    """Session-scoped workspace backed by a Docker named volume."""

    backend: DockerBackend
    container_path: str
    volume_name: str
    user_id: str
    session_id: str

    @property
    def display_path(self) -> str:
        return self.container_path

    def _file_path(self, filename: str) -> str:
        name = filename.lstrip("/")
        base = self.container_path.rstrip("/")
        return f"{base}/{name}"

    def _upload_arcname(self, filename: str) -> str:
        return self._file_path(filename).lstrip("/")

    def write_text(self, filename: str, content: str) -> None:
        arcname = self._upload_arcname(filename)
        results = self.backend.upload_files([(arcname, content.encode("utf-8"))])
        if not results or results[0].error:
            raise RuntimeError(f"Failed to write {filename} to sandbox: {results[0].error if results else 'unknown'}")

    def read_bytes(self, filename: str) -> bytes | None:
        path = self._file_path(filename)
        results = self.backend.download_files([path])
        if not results or results[0].error or results[0].content is None:
            return None
        return results[0].content

    def read_text(self, filename: str) -> str | None:
        raw = self.read_bytes(filename)
        if raw is None:
            return None
        return raw.decode("utf-8")

    def exists(self, filename: str) -> bool:
        path = self._file_path(filename)
        result = self.backend.execute(f"test -f {path} && echo yes || echo no")
        return result.output.strip() == "yes"

    def list_files(self) -> list[dict[str, Any]]:
        entries = self.backend.ls_info(self.container_path)
        files: list[dict[str, Any]] = []
        for entry in entries:
            name = entry.get("name", "")
            if name in (".", ".."):
                continue
            permissions = entry.get("permissions", "")
            if permissions.startswith("d"):
                continue
            try:
                size = int(entry.get("size", 0))
            except (TypeError, ValueError):
                size = 0
            mtime = entry.get("mtime")
            if isinstance(mtime, (int, float)):
                modified_at = format_file_mtime(mtime)
            else:
                modified_at = time.strftime("%b %d %H:%M")
            files.append(
                {
                    "name": name,
                    "size": size,
                    "modified_at": modified_at,
                }
            )
        return sorted(files, key=lambda item: item["name"])
