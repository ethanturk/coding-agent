from __future__ import annotations

import subprocess
from pathlib import Path

from app.models import Project


def run_command(project: Project, command: str, cwd: str | None = None) -> dict:
    cwd = cwd or project.local_repo_path or "."
    cwd_path = Path(cwd)
    if not cwd_path.exists():
        return {"ok": False, "stdout": "", "stderr": f"Working directory not found: {cwd}", "returncode": 1}

    proc = subprocess.run(
        command,
        shell=True,
        cwd=str(cwd_path),
        text=True,
        capture_output=True,
    )
    return {
        "ok": proc.returncode == 0,
        "stdout": proc.stdout,
        "stderr": proc.stderr,
        "returncode": proc.returncode,
        "command": command,
        "cwd": str(cwd_path),
    }
