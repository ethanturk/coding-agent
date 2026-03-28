from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models import Event, ExecutionEnvironment
from app.models.enums import EnvironmentStatus, RunStatus
from app.schemas.run import RunCreate, RunRead
from app.services.docker_runner import destroy_container
from app.services.executor import execute_run
from app.services.runs import _id, create_run, get_run, list_runs

router = APIRouter(prefix="/runs", tags=["runs"])


@router.post("", response_model=RunRead)
def create_run_route(payload: RunCreate, db: Session = Depends(get_db)):
    return create_run(db, payload)


@router.get("", response_model=list[RunRead])
def list_runs_route(db: Session = Depends(get_db)):
    return list_runs(db)


@router.get("/{run_id}", response_model=RunRead)
def get_run_route(run_id: str, db: Session = Depends(get_db)):
    run = get_run(db, run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    return run


@router.post("/{run_id}/execute", response_model=RunRead)
def execute_run_route(run_id: str, db: Session = Depends(get_db)):
    run = get_run(db, run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    try:
        updated = execute_run(db, run_id)
    except ValueError as e:
        run.status = RunStatus.FAILED
        run.final_summary = str(e)
        db.add(Event(id=_id('evt'), run_id=run.id, step_id=run.current_step_id, event_type='run.failed', payload_json={'error': str(e)}))
        db.commit()
        db.refresh(run)
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        run.status = RunStatus.FAILED
        run.final_summary = str(e)
        db.add(Event(id=_id('evt'), run_id=run.id, step_id=run.current_step_id, event_type='run.failed', payload_json={'error': str(e)}))
        db.commit()
        db.refresh(run)
        raise HTTPException(status_code=500, detail=str(e)) from e
    if not updated:
        raise HTTPException(status_code=404, detail="Run not found")
    return updated


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
        return execute_run(db, run_id)
    except ValueError as e:
        run.status = RunStatus.FAILED
        run.final_summary = str(e)
        db.add(Event(id=_id('evt'), run_id=run.id, step_id=run.current_step_id, event_type='run.failed', payload_json={'error': str(e)}))
        db.commit()
        db.refresh(run)
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        run.status = RunStatus.FAILED
        run.final_summary = str(e)
        db.add(Event(id=_id('evt'), run_id=run.id, step_id=run.current_step_id, event_type='run.failed', payload_json={'error': str(e)}))
        db.commit()
        db.refresh(run)
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
    return run


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
