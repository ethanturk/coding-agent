from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models import ExecutionEnvironment, Run
from app.services.docker_runner import git_diff_in_container, git_status_in_container

router = APIRouter(prefix="/runs", tags=["run-diff"])


@router.get("/{run_id}/diff")
def run_diff(run_id: str, db: Session = Depends(get_db)):
    if not db.get(Run, run_id):
        raise HTTPException(status_code=404, detail="Run not found")
    env = db.query(ExecutionEnvironment).filter(ExecutionEnvironment.run_id == run_id).order_by(ExecutionEnvironment.created_at.desc()).first()
    if not env or not env.container_id:
        raise HTTPException(status_code=400, detail="Run has no active container environment")
    status = git_status_in_container(env)
    diff = git_diff_in_container(env)
    changed_files = [line.strip() for line in (status.get('stdout') or '').splitlines() if line.strip()]
    return {'changed_files': changed_files, 'diff': diff}
