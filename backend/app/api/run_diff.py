from pathlib import Path

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.api.dependencies import get_run_or_404, get_latest_env
from app.models import Artifact
from app.services.docker_runner import git_diff_in_container, git_status_in_container

router = APIRouter(prefix="/runs", tags=["run-diff"])


def _artifact_text(db: Session, run_id: str, name: str) -> str | None:
    artifact = db.scalars(
        select(Artifact).where(Artifact.run_id == run_id, Artifact.name == name).order_by(Artifact.created_at.desc())
    ).first()
    if not artifact or not artifact.storage_uri:
        return None
    path = Path(artifact.storage_uri)
    if not path.exists() or not path.is_file():
        return None
    try:
        return path.read_text(encoding='utf-8')
    except Exception:
        return None


@router.get("/{run_id}/diff")
def run_diff(run_id: str, db: Session = Depends(get_db)):
    get_run_or_404(db, run_id)
    env = get_latest_env(db, run_id)
    if env and env.container_id:
        status = git_status_in_container(env)
        diff = git_diff_in_container(env)
        changed_files = [line.strip() for line in (status.get('stdout') or '').splitlines() if line.strip()]
        return {'changed_files': changed_files, 'diff': diff, 'source': 'live_container'}

    artifact_diff = _artifact_text(db, run_id, 'git.diff')
    artifact_summary = _artifact_text(db, run_id, 'developer-proposal-summary.txt')
    changed_files = []
    if artifact_summary:
        changed_files = [line.strip() for line in artifact_summary.splitlines() if line.strip().startswith('- ')]
    if artifact_diff:
        return {
            'changed_files': changed_files,
            'diff': {'stdout': artifact_diff, 'stderr': ''},
            'source': 'artifact',
        }
    return {
        'changed_files': changed_files,
        'diff': {'stdout': '', 'stderr': 'No diff is available for this run.'},
        'source': 'unavailable',
    }
