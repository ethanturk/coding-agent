from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models import Artifact, Event, ExecutionEnvironment, Run
from app.models.enums import ArtifactType
from app.services.docker_runner import edit_file_in_container
from app.services.runs import _id

router = APIRouter(prefix="/runs", tags=["edits"])


@router.post("/{run_id}/edit")
def edit_run_file(run_id: str, payload: dict, db: Session = Depends(get_db)):
    run = db.get(Run, run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    env = db.query(ExecutionEnvironment).filter(ExecutionEnvironment.run_id == run_id).order_by(ExecutionEnvironment.created_at.desc()).first()
    if not env or not env.container_id:
        raise HTTPException(status_code=400, detail="Run has no active container environment")
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
