import threading

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.session import SessionLocal, get_db
from app.api.dependencies import get_latest_env
from app.models import Approval, Artifact, Event, Run
from app.models.enums import ApprovalStatus, ApprovalType, ArtifactType, RunStatus
from app.services.docker_runner import edit_file_in_container, exec_in_container
from app.services.executor import execute_run
from app.services.runs import _id

router = APIRouter(prefix="/approvals", tags=["approvals"])


def _resume_run_async(run_id: str):
    db = SessionLocal()
    try:
        execute_run(db, run_id)
    finally:
        db.close()


def _with_legacy_override_backfill(approval: Approval) -> dict:
    payload = dict(approval.requested_payload_json or {})
    if approval.status == ApprovalStatus.PENDING and not payload.get('override_block_allowed'):
        kind = payload.get('kind')
        if kind in {'plan', 'review'}:
            payload['override_block_allowed'] = True
    return {
        "id": approval.id,
        "run_id": approval.run_id,
        "step_id": approval.step_id,
        "title": approval.title,
        "approval_type": approval.approval_type,
        "status": approval.status,
        "requested_payload_json": payload,
        "created_at": approval.created_at,
    }


@router.get("/run/{run_id}")
def list_approvals(run_id: str, db: Session = Depends(get_db)):
    approvals = db.query(Approval).filter(Approval.run_id == run_id).all()
    mutated = False
    serialized = []
    for approval in approvals:
        payload = dict(approval.requested_payload_json or {})
        if approval.status == ApprovalStatus.PENDING and not payload.get('override_block_allowed'):
            kind = payload.get('kind')
            if kind in {'plan', 'review'}:
                payload['override_block_allowed'] = True
                approval.requested_payload_json = payload
                mutated = True
        serialized.append(_with_legacy_override_backfill(approval))
    if mutated:
        db.commit()
    return serialized


def _resume_run(run, db: Session, *, summary: str, event_type: str, payload: dict):
    run.status = RunStatus.QUEUED
    run.final_summary = summary
    db.add(Event(id=_id('evt'), run_id=run.id, step_id=run.current_step_id, event_type=event_type, payload_json=payload))
    db.commit()
    threading.Thread(target=_resume_run_async, args=(run.id,), daemon=True).start()


@router.post("/{approval_id}/approve")
def approve(approval_id: str, db: Session = Depends(get_db)):
    approval = db.get(Approval, approval_id)
    if not approval:
        raise HTTPException(status_code=404, detail="Approval not found")
    approval.status = ApprovalStatus.APPROVED
    run = db.get(Run, approval.run_id)
    env = get_latest_env(db, approval.run_id)

    proposals = (approval.requested_payload_json or {}).get('proposals') if approval.requested_payload_json else None
    single = approval.requested_payload_json if approval.requested_payload_json and 'path' in approval.requested_payload_json else None
    proposal_items = proposals or ([single] if single else [])

    payload = approval.requested_payload_json or {}

    if approval.approval_type == ApprovalType.PR_MERGE:
        return {"ok": True, "status": approval.status, "run_id": approval.run_id, "message": "PR merge approvals should be handled via the PR lifecycle action."}

    if payload.get('kind') == 'plan':
        if run:
            _resume_run(
                run,
                db,
                summary='Plan approved, implementation resumed',
                event_type='plan.approved',
                payload={'approval_id': approval.id, 'scope_control': payload.get('scope_control', {}), 'files': payload.get('files_changed', []), 'mode': payload.get('mode')},
            )
        else:
            db.commit()
            threading.Thread(target=_resume_run_async, args=(approval.run_id,), daemon=True).start()
        return {"ok": True, "status": approval.status, "run_id": approval.run_id, "resumed": True, "plan_approved": True, "files": payload.get('files_changed', [])}

    cleanup_ops = payload.get('operations') if payload else None
    cleanup_mode = payload.get('mode') if payload else None

    if cleanup_mode == 'filesystem_cleanup' and cleanup_ops and run and env and env.container_id:
        applied_paths = []
        deleted_matches = []
        for op in cleanup_ops:
            if op.get('type') != 'delete_path':
                continue
            matches = [match.rstrip('/') for match in (op.get('matches') or []) if match]
            if not matches:
                continue
            for rel_path in matches:
                result = exec_in_container(env, f"cd {env.repo_dir} && rm -rf -- '{rel_path}'")
                if not result['ok']:
                    raise HTTPException(status_code=400, detail=result.get('stderr') or f"Failed to delete approved path {rel_path}")
                deleted_matches.append(rel_path)
            applied_paths.append(op['path'])
            db.add(Event(id=_id('evt'), run_id=run.id, step_id=run.current_step_id, event_type='filesystem.path_deleted', payload_json={'path': op['path'], 'matches': matches}))
        db.add(Artifact(id=_id('art'), run_id=run.id, step_id=run.current_step_id, artifact_type=ArtifactType.LOG, name='filesystem-cleanup.log', storage_uri=f"container://{env.container_id}/{env.repo_dir}", summary='Applied approved filesystem cleanup'))
        _resume_run(run, db, summary='Approved filesystem cleanup resumed', event_type='run.resumed', payload={'reason': 'approved_filesystem_cleanup', 'paths': applied_paths, 'deleted_matches': deleted_matches})
        return {"ok": True, "status": approval.status, "run_id": approval.run_id, "resumed": True, "cleanup_applied": True, "paths": applied_paths, "deleted_matches": deleted_matches}

    if proposal_items and run and env and env.container_id:
        applied_paths = []
        for proposal in proposal_items:
            result = edit_file_in_container(env, f"{env.repo_dir}/{proposal['path']}", proposal['old_text'], proposal['new_text'])
            if not result['ok']:
                raise HTTPException(status_code=400, detail=result.get('stderr') or 'Failed to apply approved edit')
            applied_paths.append(proposal['path'])
            db.add(Artifact(id=_id('art'), run_id=run.id, step_id=run.current_step_id, artifact_type=ArtifactType.LOG, name=proposal['path'], storage_uri=f"container://{env.container_id}/{env.repo_dir}/{proposal['path']}", summary='Applied approved edit'))
            db.add(Event(id=_id('evt'), run_id=run.id, step_id=run.current_step_id, event_type='edit.applied', payload_json={'path': proposal['path']}))
        _resume_run(run, db, summary='Approved edit proposal resumed', event_type='run.resumed', payload={'reason': 'approved_edit_proposal', 'paths': applied_paths})
        return {"ok": True, "status": approval.status, "run_id": approval.run_id, "resumed": True, "edit_applied": True, "paths": applied_paths}

    if payload.get('hitl'):
        db.commit()
        return {"ok": True, "status": approval.status, "run_id": approval.run_id, "resumed": False, "message": "This approval came from a non-durable live edit interrupt and cannot be resumed safely. Retry the run after disabling live write interrupts for this flow."}

    if run:
        _resume_run(run, db, summary='Approval accepted, run resumed', event_type='run.resumed', payload={'reason': 'approval_accepted'})
    else:
        db.commit()
        threading.Thread(target=_resume_run_async, args=(approval.run_id,), daemon=True).start()
    return {"ok": True, "status": approval.status, "run_id": approval.run_id, "resumed": True}


@router.post("/{approval_id}/override")
def override_block(approval_id: str, db: Session = Depends(get_db)):
    approval = db.get(Approval, approval_id)
    if not approval:
        raise HTTPException(status_code=404, detail="Approval not found")
    payload = approval.requested_payload_json or {}
    if not payload.get('override_block_allowed'):
        raise HTTPException(status_code=400, detail="Override is not allowed for this approval")

    approval.status = ApprovalStatus.OVERRIDDEN
    approval.response_payload_json = {'override_block': True}
    run = db.get(Run, approval.run_id)
    if run:
        _resume_run(
            run,
            db,
            summary='Human override accepted, run resumed',
            event_type='approval.overridden',
            payload={'approval_id': approval.id, 'kind': payload.get('kind'), 'override_block': True},
        )
    else:
        db.commit()
        threading.Thread(target=_resume_run_async, args=(approval.run_id,), daemon=True).start()
    return {"ok": True, "status": approval.status, "run_id": approval.run_id, "resumed": True, "override_block": True}
