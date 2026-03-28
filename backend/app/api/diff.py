from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models import Project
from app.services.gittools import git_diff

router = APIRouter(prefix="/projects", tags=["diff"])


@router.get("/{project_id}/diff")
def project_diff(project_id: str, db: Session = Depends(get_db)):
    project = db.get(Project, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return git_diff(project)
