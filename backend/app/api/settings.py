from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.services.settings import get_settings, resolve_role_model

router = APIRouter(prefix="/settings", tags=["settings"])


@router.get("")
def get_settings_route(db: Session = Depends(get_db)):
    row = get_settings(db)
    value = row.value_json
    value['resolved_roles'] = {role: resolve_role_model(value, role) for role in ['orchestrator', 'planner', 'developer', 'tester', 'reviewer', 'reporter']}
    return value


@router.put("")
def put_settings_route(payload: dict, db: Session = Depends(get_db)):
    row = get_settings(db)
    row.value_json = payload
    db.commit()
    db.refresh(row)
    return row.value_json
