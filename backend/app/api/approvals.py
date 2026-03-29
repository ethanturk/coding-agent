import threading

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.session import SessionLocal, get_db
from app.models import Approval, Artifact, Event, ExecutionEnvironment, Run
from app.models.enums import ApprovalStatus, ApprovalType, ArtifactType, RunStatus
from app.services.docker_runner import edit_file_in_container
from app.services.executor import execute_run
from app.services.runs import _id

router = APIRouter(prefix="/approvals", tags=["approvals"])


def _resume_run_async(run_id: str):
    db = SessionLocal()
    try:
        execute_run(db, run_id)
    finally:
        db.close()


@router.get("/run/{run_id}")
def list_approvals(run_id: str, db: Session = Depends(get_db)):
    return [
        {
            "id": a.id,
            "run_id": a.run_id,
            "step_id": a.step_id,
            "title": a.title,
            "approval_type": a.approval_type,
            "status": a.status,
            "requested_payload_json": a.requested_payload_json,
        }
        for a in db.query(Approval).filter(Approval.run_id == run_id).all()
    ]


@router.post("/{approval_id}/approve")
def approve(approval_id: str, db: Session = Depends(get_db)):
    approval = db.get(Approval, approval_id)
    if not approval:
        raise HTTPException(status_code=404, detail="Approval not found")
    approval.status = ApprovalStatus.APPROVED
    run = db.get(Run, approval.run_id)
    env = db.query(ExecutionEnvironment).filter(ExecutionEnvironment.run_id == approval.run_id).order_by(ExecutionEnvironment.created_at.desc()).first()

    proposals = (approval.requested_payload_json or {}).get('proposals') if approval.requested_payload_json else None
    single = approval.requested_payload_json if approval.requested_payload_json and 'path' in approval.requested_payload_json else None
    proposal_items = proposals or ([single] if single else [])

    if approval.approval_type == ApprovalType.PR_MERGE:
        return {"ok": True, "status": approval.status, "run_id": approval.run_id, "message": "PR merge approvals should be handled via the PR lifecycle action."}

    if proposal_items and run and env and env.container_id:
        applied_paths = []
        for proposal in proposal_items:
            result = edit_file_in_container(env, f"{env.repo_dir}/{proposal['path']}", proposal['old_text'], proposal['new_text'])
            if not result['ok']:
                raise HTTPException(status_code=400, detail=result.get('stderr') or 'Failed to apply approved edit')
            applied_paths.append(proposal['path'])
            db.add(Artifact(id=_id('art'), run_id=run.id, step_id=run.current_step_id, artifact_type=ArtifactType.LOG, name=proposal['path'], storage_uri=f"container://{env.container_id}/{env.repo_dir}/{proposal['path']}", summary='Applied approved edit'))
            db.add(Event(id=_id('evt'), run_id=run.id, step_id=run.current_step_id, event_type='edit.applied', payload_json={'path': proposal['path']}))
        run.status = RunStatus.QUEUED
        db.add(Event(id=_id('evt'), run_id=run.id, step_id=run.current_step_id, event_type='run.resumed', payload_json={'reason': 'approved_edit_proposal', 'paths': applied_paths}))
        db.commit()
        threading.Thread(target=_resume_run_async, args=(approval.run_id,), daemon=True).start()
        return {"ok": True, "status": approval.status, "run_id": approval.run_id, "resumed": True, "edit_applied": True, "paths": applied_paths}

    if run:
        run.status = RunStatus.QUEUED
    db.commit()
    threading.Thread(target=_resume_run_async, args=(approval.run_id,), daemon=True).start()
    return {"ok": True, "status": approval.status, "run_id": approval.run_id, "resumed": True}
