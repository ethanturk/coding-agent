from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.project import ProjectCreate, ProjectRead
from app.services.projects import clone_project_repo, create_project, list_projects, update_project

router = APIRouter(prefix="/projects", tags=["projects"])


@router.post("", response_model=ProjectRead)
def create_project_route(payload: ProjectCreate, db: Session = Depends(get_db)):
    return create_project(db, payload)


@router.get("", response_model=list[ProjectRead])
def list_projects_route(db: Session = Depends(get_db)):
    return list_projects(db)


@router.put("/{project_id}", response_model=ProjectRead)
def update_project_route(project_id: str, payload: ProjectCreate, db: Session = Depends(get_db)):
    project = update_project(db, project_id, payload)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return project


@router.post("/{project_id}/clone", response_model=ProjectRead)
def clone_project_route(project_id: str, db: Session = Depends(get_db)):
    project = clone_project_repo(db, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return project
