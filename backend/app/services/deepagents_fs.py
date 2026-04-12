"""Docker-backed sandbox backend for DeepAgents.

Implements SandboxBackendProtocol as a self-contained DeepAgents native sandbox.
Manages its own Docker container lifecycle and routes all operations
(execute, ls, read, write, edit, grep, glob) through the container.
"""

from __future__ import annotations

import logging
import os
import subprocess
import tempfile
import uuid
from pathlib import Path

from deepagents.backends.protocol import (
    ExecuteResponse,
    FileDownloadResponse,
    FileUploadResponse,
)
from deepagents.backends.sandbox import BaseSandbox

logger = logging.getLogger(__name__)

DEFAULT_IMAGE = "python:3.11.5-slim"
DEFAULT_TIMEOUT = 300


class DockerSandbox(BaseSandbox):
    """Self-contained DeepAgents sandbox backed by a Docker container.

    Creates, manages, and destroys its own Docker container. Can be initialized
    either from an existing container_id (for integration with the platform's
    ExecutionEnvironment) or by creating a fresh container.

    All file operations (ls, read, write, edit, grep, glob) are inherited from
    BaseSandbox and route through execute(). Only execute(), upload_files(),
    and download_files() are implemented directly.
    """

    def __init__(
        self,
        *,
        container_id: str | None = None,
        image: str = DEFAULT_IMAGE,
        repo_url: str | None = None,
        repo_dir: str = "/workspace/repo",
        branch_name: str | None = None,
        env_vars: dict[str, str] | None = None,
    ) -> None:
        """Initialize the Docker sandbox.

        Args:
            container_id: Existing container ID to connect to. If None,
                a new container is created.
            image: Docker image to use for new containers.
            repo_url: Git repository URL to clone into the container.
            repo_dir: Path inside the container for the repository.
            branch_name: Git branch to create/checkout after cloning.
            env_vars: Additional environment variables for the container.
        """
        self._image = image
        self._repo_dir = repo_dir
        self._branch_name = branch_name
        self._env_vars = env_vars or {}
        self._owned = container_id is None  # Track if we created the container

        if container_id:
            self._container_id = container_id
        else:
            self._container_id = self._create_container()

        if repo_url:
            self._bootstrap_repo(repo_url)

    @classmethod
    def from_env(cls, env) -> DockerSandbox:
        """Create a DockerSandbox from an ExecutionEnvironment record.

        This bridges the platform's existing Docker lifecycle with the
        DeepAgents sandbox interface.
        """
        if not env.container_id:
            raise ValueError("ExecutionEnvironment has no container_id")
        return cls(
            container_id=env.container_id,
            repo_dir=env.repo_dir or "/workspace/repo",
            branch_name=env.branch_name,
        )

    def _create_container(self) -> str:
        """Create a new Docker container and return its ID."""
        name = f"deepagents-{uuid.uuid4().hex[:12]}"
        command = [
            "docker", "run", "-d", "--rm", "--name", name,
            "-w", "/workspace",
        ]
        # Inject environment variables
        github_token = self._env_vars.get("GITHUB_TOKEN") or os.environ.get("GITHUB_TOKEN")
        if github_token:
            command.extend(["-e", f"GITHUB_TOKEN={github_token}"])
        for key, value in self._env_vars.items():
            if key != "GITHUB_TOKEN":
                command.extend(["-e", f"{key}={value}"])

        command.extend([self._image, "sleep", "infinity"])

        result = subprocess.run(command, capture_output=True, text=True, check=True, timeout=60)
        container_id = result.stdout.strip()
        logger.info("Created Docker container %s (%s)", name, container_id[:12])
        return container_id

    def _bootstrap_repo(self, repo_url: str) -> None:
        """Clone a repository into the container and set up a branch."""
        # Install git
        self.execute("apt-get update >/dev/null 2>&1 && apt-get install -y git >/dev/null 2>&1")

        # Substitute GitHub token for authenticated cloning
        clone_url = repo_url
        if clone_url.startswith("https://github.com/"):
            clone_url = clone_url.replace(
                "https://github.com/",
                "https://x-access-token:$GITHUB_TOKEN@github.com/",
            )

        clone_result = self.execute(f"git clone {clone_url} {self._repo_dir}")
        if clone_result.exit_code != 0 and "already exists" not in (clone_result.output or ""):
            raise ValueError(f"Failed to clone repo: {clone_result.output[:300]}")

        if self._branch_name:
            self.execute(f"cd {self._repo_dir} && git checkout -b {self._branch_name} || true")

    @property
    def id(self) -> str:
        return self._container_id

    @property
    def repo_dir(self) -> str:
        return self._repo_dir

    def execute(
        self,
        command: str,
        *,
        timeout: int | None = None,
    ) -> ExecuteResponse:
        effective_timeout = timeout if timeout is not None else DEFAULT_TIMEOUT
        try:
            result = subprocess.run(
                ["docker", "exec", self._container_id, "sh", "-lc", command],
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
                parent = str(Path(dest_path).parent)
                subprocess.run(
                    ["docker", "exec", self._container_id, "mkdir", "-p", parent],
                    capture_output=True, text=True, timeout=30,
                )
                result = subprocess.run(
                    ["docker", "cp", tmp_path, f"{self._container_id}:{dest_path}"],
                    capture_output=True, text=True, timeout=60,
                )
                Path(tmp_path).unlink(missing_ok=True)
                if result.returncode != 0:
                    responses.append(FileUploadResponse(path=dest_path, error="permission_denied"))
                else:
                    responses.append(FileUploadResponse(path=dest_path))
            except Exception as exc:
                responses.append(FileUploadResponse(path=dest_path, error=str(exc)[:200]))
        return responses

    def download_files(self, paths: list[str]) -> list[FileDownloadResponse]:
        responses: list[FileDownloadResponse] = []
        for src_path in paths:
            try:
                with tempfile.NamedTemporaryFile(delete=False) as tmp:
                    tmp_path = tmp.name
                result = subprocess.run(
                    ["docker", "cp", f"{self._container_id}:{src_path}", tmp_path],
                    capture_output=True, text=True, timeout=60,
                )
                if result.returncode != 0:
                    Path(tmp_path).unlink(missing_ok=True)
                    responses.append(FileDownloadResponse(path=src_path, error="file_not_found"))
                else:
                    content = Path(tmp_path).read_bytes()
                    Path(tmp_path).unlink(missing_ok=True)
                    responses.append(FileDownloadResponse(path=src_path, content=content))
            except Exception as exc:
                responses.append(FileDownloadResponse(path=src_path, error=str(exc)[:200]))
        return responses

    def destroy(self) -> None:
        """Destroy the container if we created it."""
        if self._owned and self._container_id:
            subprocess.run(
                ["docker", "rm", "-f", self._container_id],
                capture_output=True, text=True,
            )
            logger.info("Destroyed Docker container %s", self._container_id[:12])
            self._container_id = ""

    def git_diff(self) -> str:
        """Get the current git diff in the repository."""
        result = self.execute(f"cd {self._repo_dir} && git diff -- .")
        return result.output if result.exit_code == 0 else ""

    def git_push(self, message: str = "agent-platform update") -> ExecuteResponse:
        """Commit and push changes in the repository."""
        commands = [
            f"cd {self._repo_dir}",
            "git config user.name 'Agent Platform'",
            "git config user.email 'agent-platform@local'",
            "git add .",
            f'git commit -m "{message}" || true',
            f"git push -u origin {self._branch_name}" if self._branch_name else "true",
        ]
        return self.execute(" && ".join(commands))
