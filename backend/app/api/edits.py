from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.api.dependencies import get_run_or_404, get_active_env_or_400
from app.models import Artifact, Event
from app.models.enums import ArtifactType
from app.services.docker_runner import edit_file_in_container
from app.services.runs import _id

router = APIRouter(prefix="/runs", tags=["edits"])


@router.post("/{run_id}/edit")
def edit_run_file(run_id: str, payload: dict, db: Session = Depends(get_db)):
    run = get_run_or_404(db, run_id)
    env = get_active_env_or_400(db, run_id)
    path = payload.get('path')
    old_text = payload.get('old_text')
    new_text = payload.get('new_text')
    if not path or old_text is None or new_text is None:
        raise HTTPException(status_code=400, detail="Missing path/old_text/new_text")

    result = edit_file_in_container(env, f"{env.repo_dir}/{path}", old_text, new_text)
    if not result['ok']:
        raise HTTPException(status_code=400, detail=result.get('stderr') or 'Failed to edit file')

    artifact = Artifact(
        id=_id('art'),
        run_id=run.id,
        step_id=run.current_step_id,
        artifact_type=ArtifactType.LOG,
        name=path,
        storage_uri=f"container://{env.container_id}/{env.repo_dir}/{path}",
        summary='Edited file in container repo',
    )
    db.add(artifact)
    db.add(Event(id=_id('evt'), run_id=run.id, step_id=run.current_step_id, event_type='file.edited', payload_json={'path': path}))
    db.commit()
    return {'ok': True, 'path': path}
