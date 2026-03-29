from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models import Event, ExecutionEnvironment
from app.models.enums import EnvironmentStatus, RunStatus
from app.schemas.run import RunCreate, RunListRead, RunRead
from app.services.docker_runner import destroy_container
from app.services.executor import execute_run
from app.services.run_operator_summary import build_run_list_operator_summary, build_run_operator_summary
from app.services.runs import _id, create_run, get_run, list_runs

router = APIRouter(prefix="/runs", tags=["runs"])


def _serialize_run(db: Session, run):
    data = RunRead.model_validate(run).model_dump()
    data['operator_summary'] = build_run_operator_summary(db, run).model_dump()
    return data


def _serialize_run_list_item(db: Session, run):
    data = RunListRead.model_validate(run).model_dump()
    data['operator_summary'] = build_run_list_operator_summary(db, run).model_dump()
    return data


def _record_run_failure(db: Session, run, error: Exception | str):
    message = str(error)
    run.status = RunStatus.FAILED
    run.final_summary = message
    payload = {
        'error': message,
        'error_type': error.__class__.__name__ if isinstance(error, Exception) else 'Error',
    }
    for attr in ('provider', 'model', 'role', 'mode', 'api_base', 'status_code'):
        value = getattr(error, attr, None)
        if value is not None:
            payload[attr] = value
    db.add(
        Event(
            id=_id('evt'),
            run_id=run.id,
            step_id=run.current_step_id,
            event_type='run.failed',
            payload_json=payload,
        )
    )
    db.commit()
    db.refresh(run)


@router.post("", response_model=RunRead)
def create_run_route(payload: RunCreate, db: Session = Depends(get_db)):
    run = create_run(db, payload)
    return _serialize_run(db, run)


@router.get("", response_model=list[RunListRead])
def list_runs_route(db: Session = Depends(get_db)):
    runs = list_runs(db)
    return [_serialize_run_list_item(db, run) for run in runs]


@router.get("/{run_id}", response_model=RunRead)
def get_run_route(run_id: str, db: Session = Depends(get_db)):
    run = get_run(db, run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    return _serialize_run(db, run)


@router.post("/{run_id}/execute", response_model=RunRead)
def execute_run_route(run_id: str, db: Session = Depends(get_db)):
    run = get_run(db, run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    try:
        updated = execute_run(db, run_id)
    except ValueError as e:
        _record_run_failure(db, run, e)
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        _record_run_failure(db, run, e)
        raise HTTPException(status_code=500, detail=str(e)) from e
    if not updated:
        raise HTTPException(status_code=404, detail="Run not found")
    return _serialize_run(db, updated)


@router.post("/{run_id}/retry", response_model=RunRead)
def retry_run_route(run_id: str, db: Session = Depends(get_db)):
    run = get_run(db, run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    if run.status == RunStatus.RUNNING:
        raise HTTPException(status_code=400, detail="Cannot retry a running run")
    if run.status == RunStatus.COMPLETED:
        raise HTTPException(status_code=400, detail="Cannot retry a completed run")
    if run.status == RunStatus.CANCELLED:
        raise HTTPException(status_code=400, detail="Cannot retry a cancelled run")
    try:
        return _serialize_run(db, execute_run(db, run_id))
    except ValueError as e:
        _record_run_failure(db, run, e)
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        _record_run_failure(db, run, e)
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.post("/{run_id}/cancel", response_model=RunRead)
def cancel_run_route(run_id: str, db: Session = Depends(get_db)):
    run = get_run(db, run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    env = db.query(ExecutionEnvironment).filter(ExecutionEnvironment.run_id == run_id).order_by(ExecutionEnvironment.created_at.desc()).first()
    if env and env.status != EnvironmentStatus.DESTROYED:
        destroy_container(db, env)
    run.status = RunStatus.CANCELLED
    run.final_summary = 'Run cancelled by operator'
    db.add(Event(id=_id('evt'), run_id=run.id, step_id=run.current_step_id, event_type='run.cancelled', payload_json={'cleanup': bool(env)}))
    db.commit()
    db.refresh(run)
    return _serialize_run(db, run)


@router.delete("/{run_id}")
def delete_run_route(run_id: str, db: Session = Depends(get_db)):
    run = get_run(db, run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    if run.status in {RunStatus.RUNNING, RunStatus.COMPLETED}:
        raise HTTPException(status_code=400, detail="Cannot delete a running or completed run")
    env = db.query(ExecutionEnvironment).filter(ExecutionEnvironment.run_id == run_id).order_by(ExecutionEnvironment.created_at.desc()).first()
    if env and env.status != EnvironmentStatus.DESTROYED:
        destroy_container(db, env)
    db.delete(run)
    db.commit()
    return {"ok": True, "deleted": run_id}
