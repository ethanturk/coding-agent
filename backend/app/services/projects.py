import subprocess
import uuid
from pathlib import Path
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Project
from app.schemas.project import ProjectCreate


def _id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:20]}"


def _materialize_repo(repo_url: str | None, local_repo_path: str) -> None:
    path = Path(local_repo_path).expanduser()
    if path.exists() and any(path.iterdir()):
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    if repo_url:
        subprocess.run(['git', 'clone', repo_url, str(path)], check=True, capture_output=True, text=True)
    else:
        path.mkdir(parents=True, exist_ok=True)


def create_project(db: Session, data: ProjectCreate) -> Project:
    local_repo_path = data.local_repo_path or f"/home/ethanturk/repos/{data.slug}"
    project = Project(
        id=_id("proj"),
        name=data.name,
        slug=data.slug,
        repo_url=data.repo_url,
        local_repo_path=local_repo_path,
        default_branch=data.default_branch,
        inspect_command=data.inspect_command,
        test_command=data.test_command,
        build_command=data.build_command,
        lint_command=data.lint_command,
    )
    _materialize_repo(data.repo_url, local_repo_path)
    db.add(project)
    db.commit()
    db.refresh(project)
    return project


def update_project(db: Session, project_id: str, data: ProjectCreate) -> Project | None:
    project = db.get(Project, project_id)
    if not project:
        return None
    project.name = data.name
    project.slug = data.slug
    project.repo_url = data.repo_url
    project.local_repo_path = data.local_repo_path
    project.default_branch = data.default_branch
    project.inspect_command = data.inspect_command
    project.test_command = data.test_command
    project.build_command = data.build_command
    project.lint_command = data.lint_command
    _materialize_repo(data.repo_url, project.local_repo_path or f"/home/ethanturk/repos/{data.slug}")
    db.commit()
    db.refresh(project)
    return project


def clone_project_repo(db: Session, project_id: str) -> Project | None:
    project = db.get(Project, project_id)
    if not project:
        return None
    _materialize_repo(project.repo_url, project.local_repo_path or f"/home/ethanturk/repos/{project.slug}")
    db.commit()
    db.refresh(project)
    return project


def list_projects(db: Session) -> list[Project]:
    return list(db.scalars(select(Project).order_by(Project.created_at.desc())))
