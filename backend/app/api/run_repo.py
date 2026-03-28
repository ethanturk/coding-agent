from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models import ExecutionEnvironment, Run
from app.services.docker_runner import list_files_in_container, read_file_in_container, write_file_in_container

router = APIRouter(prefix="/runs", tags=["run-repo"])


def _env_for_run(db: Session, run_id: str) -> ExecutionEnvironment:
    env = db.query(ExecutionEnvironment).filter(ExecutionEnvironment.run_id == run_id).order_by(ExecutionEnvironment.created_at.desc()).first()
    if not env or not env.container_id:
        raise HTTPException(status_code=400, detail="Run has no active container environment")
    return env


@router.get("/{run_id}/files")
def list_run_files(run_id: str, db: Session = Depends(get_db)):
    if not db.get(Run, run_id):
        raise HTTPException(status_code=404, detail="Run not found")
    env = _env_for_run(db, run_id)
    result = list_files_in_container(env, env.repo_dir)
    if not result['ok']:
        raise HTTPException(status_code=400, detail=result['stderr'] or 'Failed to list files')
    return {"files": [line for line in result['stdout'].splitlines() if line.strip()], "root": env.repo_dir}


@router.get("/{run_id}/file")
def read_run_file(run_id: str, path: str, db: Session = Depends(get_db)):
    if not db.get(Run, run_id):
        raise HTTPException(status_code=404, detail="Run not found")
    env = _env_for_run(db, run_id)
    result = read_file_in_container(env, f"{env.repo_dir}/{path}")
    if not result['ok']:
        raise HTTPException(status_code=400, detail=result['stderr'] or 'Failed to read file')
    return {"path": path, "content": result['stdout']}


@router.post("/{run_id}/file")
def write_run_file(run_id: str, payload: dict, db: Session = Depends(get_db)):
    if not db.get(Run, run_id):
        raise HTTPException(status_code=404, detail="Run not found")
    env = _env_for_run(db, run_id)
    path = payload.get('path')
    content = payload.get('content', '')
    if not path:
        raise HTTPException(status_code=400, detail="Missing path")
    result = write_file_in_container(env, f"{env.repo_dir}/{path}", content)
    if not result['ok']:
        raise HTTPException(status_code=400, detail=result['stderr'] or 'Failed to write file')
    return {"ok": True, "path": path}
