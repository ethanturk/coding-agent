from pathlib import Path

BASE = Path('/home/ethanturk/.openclaw/workspace/agent-platform-mvp/runtime_worktrees')


def worktree_path(run_id: str) -> Path:
    return (BASE / run_id).resolve()
