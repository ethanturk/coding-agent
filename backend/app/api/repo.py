from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models import Project

router = APIRouter(prefix="/projects", tags=["repo"])


def _project_root(project: Project) -> Path:
    if not project.local_repo_path:
        raise HTTPException(status_code=400, detail="Project has no local_repo_path")
    root = Path(project.local_repo_path).resolve()
    if not root.exists():
        raise HTTPException(status_code=404, detail="Project path does not exist")
    return root


@router.get("/{project_id}/files")
def list_files(project_id: str, db: Session = Depends(get_db)):
    project = db.get(Project, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    root = _project_root(project)
    files = [str(p.relative_to(root)) for p in root.rglob('*') if p.is_file()][:500]
    return {"files": files}


@router.get("/{project_id}/file")
def read_file(project_id: str, path: str, db: Session = Depends(get_db)):
    project = db.get(Project, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    root = _project_root(project)
    target = (root / path).resolve()
    if root not in target.parents and target != root:
        raise HTTPException(status_code=400, detail="Invalid path")
    if not target.exists():
        raise HTTPException(status_code=404, detail="File not found")
    return {"path": path, "content": target.read_text()}


@router.post("/{project_id}/file")
def write_file(project_id: str, payload: dict, db: Session = Depends(get_db)):
    project = db.get(Project, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    path = payload.get('path')
    content = payload.get('content', '')
    if not path:
        raise HTTPException(status_code=400, detail="Missing path")
    root = _project_root(project)
    target = (root / path).resolve()
    if root not in target.parents and target != root:
        raise HTTPException(status_code=400, detail="Invalid path")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content)
    return {"ok": True, "path": path}
