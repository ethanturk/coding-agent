from __future__ import annotations

import subprocess
from pathlib import Path

from app.models import Project

BASE = Path('/home/ethanturk/.openclaw/workspace/agent-platform-mvp/runtime_worktrees')


def ensure_worktree(project: Project, run_id: str) -> Path:
    if not project.local_repo_path:
        raise ValueError('Project has no local_repo_path')
    repo_root = Path(project.local_repo_path).resolve()
    if not repo_root.exists():
        repo_root.mkdir(parents=True, exist_ok=True)
        subprocess.run(['git', 'init', '-b', project.default_branch or 'main'], cwd=str(repo_root), check=True, capture_output=True, text=True)

    worktree_path = BASE / run_id
    worktree_path.parent.mkdir(parents=True, exist_ok=True)
    if worktree_path.exists() and worktree_path.is_dir():
        return worktree_path

    branch = f'agent-platform/{run_id}'
    cmd_primary = ['git', 'worktree', 'add', '-b', branch, str(worktree_path), project.default_branch or 'main']
    result = subprocess.run(cmd_primary, cwd=str(repo_root), capture_output=True, text=True)

    if result.returncode != 0:
        cmd_fallback = ['git', 'worktree', 'add', '--force', str(worktree_path), project.default_branch or 'main']
        result = subprocess.run(cmd_fallback, cwd=str(repo_root), capture_output=True, text=True)

    if result.returncode != 0 or not worktree_path.exists():
        raise ValueError(f"Failed to create worktree at {worktree_path}: {(result.stderr or result.stdout).strip()}")

    return worktree_path
