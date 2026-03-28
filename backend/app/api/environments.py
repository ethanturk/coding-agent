from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models import Project, Run
from app.services.docker_runner import bootstrap_repo_in_container, create_container, destroy_container, ensure_docker_environment, exec_in_container

router = APIRouter(prefix="/runs", tags=["environments"])


@router.post("/{run_id}/environment")
def create_run_environment(run_id: str, db: Session = Depends(get_db)):
    run = db.get(Run, run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    project = db.get(Project, run.project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    env = ensure_docker_environment(db, run, project)
    env = create_container(db, env)
    return {
        'id': env.id,
        'container_id': env.container_id,
        'status': env.status,
        'image': env.image,
        'repo_dir': env.repo_dir,
    }


@router.post("/{run_id}/environment/bootstrap")
def bootstrap_run_environment(run_id: str, db: Session = Depends(get_db)):
    run = db.get(Run, run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    project = db.get(Project, run.project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    env = ensure_docker_environment(db, run, project)
    env = create_container(db, env)
    return bootstrap_repo_in_container(db, env, project)


@router.post("/{run_id}/environment/exec")
def exec_run_environment(run_id: str, payload: dict, db: Session = Depends(get_db)):
    run = db.get(Run, run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    project = db.get(Project, run.project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    env = ensure_docker_environment(db, run, project)
    env = create_container(db, env)
    return exec_in_container(env, payload.get('command', 'pwd'))


@router.delete("/{run_id}/environment")
def destroy_run_environment(run_id: str, db: Session = Depends(get_db)):
    run = db.get(Run, run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    project = db.get(Project, run.project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    env = ensure_docker_environment(db, run, project)
    env = destroy_container(db, env)
    return {'ok': True, 'status': env.status}
