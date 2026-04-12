"""Docker-backed sandbox backend for DeepAgents.

Implements SandboxBackendProtocol by delegating execute() to docker exec,
and upload_files()/download_files() to docker cp. All other operations
(ls, read, write, edit, grep, glob) are inherited from BaseSandbox which
routes them through execute().
"""

from __future__ import annotations

import subprocess
import tempfile
from pathlib import Path

from deepagents.backends.protocol import (
    ExecuteResponse,
    FileDownloadResponse,
    FileUploadResponse,
)
from deepagents.backends.sandbox import BaseSandbox

from app.models import ExecutionEnvironment


class DockerSandbox(BaseSandbox):
    """DeepAgents sandbox backend backed by a running Docker container.

    Wraps an existing ExecutionEnvironment record from the platform's
    docker_runner module. The container must already be created and running.
    """

    def __init__(self, env: ExecutionEnvironment) -> None:
        self._env = env
        if not env.container_id:
            raise ValueError("ExecutionEnvironment has no container_id — container not created")

    @property
    def id(self) -> str:
        return self._env.container_id

    def execute(
        self,
        command: str,
        *,
        timeout: int | None = None,
    ) -> ExecuteResponse:
        effective_timeout = timeout if timeout is not None else 300
        try:
            result = subprocess.run(
                ["docker", "exec", self._env.container_id, "sh", "-lc", command],
                capture_output=True,
                text=True,
                timeout=effective_timeout,
            )
        except subprocess.TimeoutExpired:
            return ExecuteResponse(
                output=f"Command timed out after {effective_timeout}s",
                exit_code=124,
                truncated=True,
            )
        output = result.stdout
        if result.stderr:
            output = output + "\n" + result.stderr if output else result.stderr
        return ExecuteResponse(
            output=output,
            exit_code=result.returncode,
        )

    def upload_files(self, files: list[tuple[str, bytes]]) -> list[FileUploadResponse]:
        responses: list[FileUploadResponse] = []
        for dest_path, content in files:
            try:
                with tempfile.NamedTemporaryFile(delete=False, suffix=Path(dest_path).suffix) as tmp:
                    tmp.write(content)
                    tmp_path = tmp.name
                # Ensure parent directory exists in container
                parent = str(Path(dest_path).parent)
                subprocess.run(
                    ["docker", "exec", self._env.container_id, "mkdir", "-p", parent],
                    capture_output=True,
                    text=True,
                    timeout=30,
                )
                # Copy file into container
                result = subprocess.run(
                    ["docker", "cp", tmp_path, f"{self._env.container_id}:{dest_path}"],
                    capture_output=True,
                    text=True,
                    timeout=60,
                )
                Path(tmp_path).unlink(missing_ok=True)
                if result.returncode != 0:
                    responses.append(FileUploadResponse(
                        path=dest_path,
                        error=f"permission_denied",
                    ))
                else:
                    responses.append(FileUploadResponse(path=dest_path))
            except Exception as exc:
                responses.append(FileUploadResponse(
                    path=dest_path,
                    error=str(exc)[:200],
                ))
        return responses

    def download_files(self, paths: list[str]) -> list[FileDownloadResponse]:
        responses: list[FileDownloadResponse] = []
        for src_path in paths:
            try:
                with tempfile.NamedTemporaryFile(delete=False) as tmp:
                    tmp_path = tmp.name
                result = subprocess.run(
                    ["docker", "cp", f"{self._env.container_id}:{src_path}", tmp_path],
                    capture_output=True,
                    text=True,
                    timeout=60,
                )
                if result.returncode != 0:
                    Path(tmp_path).unlink(missing_ok=True)
                    responses.append(FileDownloadResponse(
                        path=src_path,
                        error="file_not_found",
                    ))
                else:
                    content = Path(tmp_path).read_bytes()
                    Path(tmp_path).unlink(missing_ok=True)
                    responses.append(FileDownloadResponse(
                        path=src_path,
                        content=content,
                    ))
            except Exception as exc:
                responses.append(FileDownloadResponse(
                    path=src_path,
                    error=str(exc)[:200],
                ))
        return responses
