"""Docker sandbox backend for DeepAgents spider execution."""

from __future__ import annotations

import io
import tarfile
import time
from typing import Optional

from deepagents.backends.protocol import (
    ExecuteResponse,
    FileDownloadResponse,
    FileUploadResponse,
)
from deepagents.backends.sandbox import BaseSandbox

from app.spider.services.file_mtime import parse_ls_line

try:
    import docker
    from docker.errors import NotFound
except ImportError:  # pragma: no cover - optional dependency
    docker = None


class DockerBackend(BaseSandbox):
    """Docker sandbox backend implementation for DeepAgents."""

    def __init__(
        self,
        image: str = "python:3.11-slim",
        container_id: Optional[str] = None,
        auto_remove: bool = True,
        cpu_quota: int = 50000,
        memory_limit: str = "512m",
        network_disabled: bool = False,
        working_dir: str = "/workspace",
        volumes: dict[str, dict[str, str]] | None = None,
        labels: dict[str, str] | None = None,
    ) -> None:
        if docker is None:
            raise ImportError(
                "docker package is not installed. "
                "Please install it with `pip install docker`."
            )

        self.client = docker.from_env()
        self.image = image
        self.auto_remove = auto_remove
        self.working_dir = working_dir
        self.volumes = volumes or {}
        self.labels = labels or {}
        self._container = None

        try:
            if container_id:
                try:
                    self._container = self.client.containers.get(container_id)
                    if self._container.status != "running":
                        self._container.start()
                except NotFound as exc:
                    raise RuntimeError(f"Container {container_id} not found.") from exc
            else:
                try:
                    self.client.images.get(image)
                except NotFound:
                    self.client.images.pull(image)

                self._container = self.client.containers.run(
                    image,
                    command="tail -f /dev/null",
                    detach=True,
                    tty=True,
                    cpu_quota=cpu_quota,
                    mem_limit=memory_limit,
                    network_disabled=network_disabled,
                    working_dir=working_dir,
                    volumes=self.volumes,
                    labels=self.labels,
                )

            self.execute(f"mkdir -p {working_dir}", workdir="/")
        except Exception as exc:
            raise RuntimeError(f"Failed to start/attach Docker container: {exc}") from exc

    @property
    def id(self) -> str:
        return self._container.id if self._container else "unknown"

    def execute(self, command: str, workdir: Optional[str] = None) -> ExecuteResponse:
        if not self._container:
            return ExecuteResponse(output="Container not running", exit_code=1, truncated=False)

        try:
            execution_workdir = workdir if workdir is not None else self.working_dir
            exec_result = self._container.exec_run(
                cmd=["bash", "-c", command],
                workdir=execution_workdir,
                demux=False,
            )
            exit_code, output = exec_result

            if not isinstance(exit_code, int):
                output_str = output.decode("utf-8", errors="replace") if isinstance(output, bytes) else str(output)
                return ExecuteResponse(
                    output=f"Docker exec failed internally. Exit code: {exit_code}\nOutput: {output_str}",
                    exit_code=1,
                    truncated=False,
                )

            return ExecuteResponse(
                output=output.decode("utf-8", errors="replace"),
                exit_code=exit_code,
                truncated=False,
            )
        except Exception as exc:
            return ExecuteResponse(
                output=f"Error executing command: {str(exc)}",
                exit_code=1,
                truncated=False,
            )

    def upload_files(self, files: list[tuple[str, bytes]]) -> list[FileUploadResponse]:
        if not self._container:
            return [FileUploadResponse(path=path, error="permission_denied") for path, _ in files]

        tar_stream = io.BytesIO()
        with tarfile.open(fileobj=tar_stream, mode="w") as tar:
            for path, content in files:
                arcname = path.lstrip("/") if path.startswith("/") else path
                info = tarfile.TarInfo(name=arcname)
                info.size = len(content)
                info.mtime = time.time()
                tar.addfile(info, io.BytesIO(content))

        tar_stream.seek(0)
        try:
            self._container.put_archive(path="/", data=tar_stream)
            return [FileUploadResponse(path=path, error=None) for path, _ in files]
        except Exception:
            return [FileUploadResponse(path=path, error="permission_denied") for path, _ in files]

    def download_files(self, paths: list[str]) -> list[FileDownloadResponse]:
        if not self._container:
            return [FileDownloadResponse(path=path, error="permission_denied") for path in paths]

        responses: list[FileDownloadResponse] = []
        for path in paths:
            try:
                bits, _stat = self._container.get_archive(path)
                file_content = io.BytesIO()
                for chunk in bits:
                    file_content.write(chunk)
                file_content.seek(0)

                with tarfile.open(fileobj=file_content, mode="r") as tar:
                    member = tar.next()
                    if member is None or member.isdir():
                        responses.append(FileDownloadResponse(path=path, error="is_directory"))
                        continue
                    extracted = tar.extractfile(member)
                    if extracted:
                        responses.append(
                            FileDownloadResponse(path=path, content=extracted.read(), error=None)
                        )
                    else:
                        responses.append(FileDownloadResponse(path=path, error="file_not_found"))
            except NotFound:
                responses.append(FileDownloadResponse(path=path, error="file_not_found"))
            except Exception as exc:
                error_msg = str(exc).lower()
                error = "permission_denied" if "permission" in error_msg else "invalid_path"
                responses.append(FileDownloadResponse(path=path, content=None, error=error))
        return responses

    def ls_info(self, path: str) -> list[dict]:
        if not self._container:
            return []

        # Epoch mtime — container TZ is usually UTC; format in Asia/Shanghai later.
        result = self.execute(f"ls -la --time-style=+%s {path}")
        if result.exit_code != 0:
            return []

        entries: list[dict] = []
        for line in result.output.strip().split("\n"):
            entry = parse_ls_line(line)
            if entry is not None:
                entries.append(entry)
        return entries

    def close(self) -> None:
        if self._container:
            try:
                if self.auto_remove:
                    self._container.remove(force=True)
                else:
                    self._container.stop()
            except Exception:
                pass
            self._container = None
