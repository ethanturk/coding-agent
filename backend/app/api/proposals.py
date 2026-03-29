from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models import Approval, Artifact, Event, ExecutionEnvironment, Run
from app.models.enums import ApprovalStatus, ApprovalType, ArtifactType
from app.services.runs import _id

router = APIRouter(prefix="/runs", tags=["proposals"])


@router.post("/{run_id}/propose-edit")
def propose_edit(run_id: str, payload: dict, db: Session = Depends(get_db)):
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

    proposal_payload = {
        'path': path,
        'old_text': old_text,
        'new_text': new_text,
    }

    artifact = Artifact(
        id=_id('art'),
        run_id=run.id,
        step_id=run.current_step_id,
        artifact_type=ArtifactType.LOG,
        name=f'proposal-{path.replace('/', '_')}.json',
        storage_uri=f"container://{env.container_id}/{env.repo_dir}/{path}",
        summary='Proposed edit awaiting approval',
    )
    approval = Approval(
        id=_id('apr'),
        run_id=run.id,
        step_id=run.current_step_id,
        title=f'Approve edit for {path}',
        approval_type=ApprovalType.EDIT_PROPOSAL,
        status=ApprovalStatus.PENDING,
        requested_payload_json=proposal_payload,
    )
    db.add(artifact)
    db.add(approval)
    db.add(Event(id=_id('evt'), run_id=run.id, step_id=run.current_step_id, event_type='edit.proposed', payload_json={'path': path, 'approval_id': approval.id}))
    db.commit()
    return {'ok': True, 'approval_id': approval.id}
