from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models import Artifact, Run
from app.models.enums import ArtifactType
from app.services.gittools import git_diff
from app.services.run_context import worktree_path
from app.services.runs import _id
from app.services.sandbox import run_command

router = APIRouter(prefix="/runs", tags=["patches"])


@router.post("/{run_id}/apply")
def apply_patch(run_id: str, payload: dict, db: Session = Depends(get_db)):
    run = db.get(Run, run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    project = run.project
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    patch = payload.get('patch')
    if not patch:
        raise HTTPException(status_code=400, detail="Missing patch")
    root = worktree_path(run_id)
    patch_file = root / '.agent-platform.patch'
    patch_file.write_text(patch)
    result = run_command(project, f'git apply {patch_file.name}', cwd=str(root))
    diff_result = git_diff(project, cwd=str(root))
    artifact = Artifact(
        id=_id('art'),
        run_id=run.id,
        step_id=run.current_step_id,
        artifact_type=ArtifactType.DIFF,
        name='applied.diff',
        storage_uri=str(patch_file),
        summary='Applied patch file',
    )
    db.add(artifact)
    db.commit()
    return {'ok': result['ok'], 'apply': result, 'diff': diff_result}
