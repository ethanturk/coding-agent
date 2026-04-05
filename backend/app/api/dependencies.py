from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models import ExecutionEnvironment, Project, Run


def get_run_or_404(db: Session, run_id: str) -> Run:
    run = db.get(Run, run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    return run


def get_project_or_404(db: Session, project_id: str) -> Project:
    project = db.get(Project, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return project


def get_run_with_project(db: Session, run_id: str) -> tuple[Run, Project]:
    run = get_run_or_404(db, run_id)
    project = db.get(Project, run.project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return run, project


def get_latest_env(db: Session, run_id: str) -> ExecutionEnvironment | None:
    return (
        db.query(ExecutionEnvironment)
        .filter(ExecutionEnvironment.run_id == run_id)
        .order_by(ExecutionEnvironment.created_at.desc())
        .first()
    )


def get_active_env_or_400(db: Session, run_id: str) -> ExecutionEnvironment:
    env = get_latest_env(db, run_id)
    if not env or not env.container_id:
        raise HTTPException(status_code=400, detail="Run has no active container environment")
    return env
