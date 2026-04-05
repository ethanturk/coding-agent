from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models import Event

router = APIRouter(prefix="/runs", tags=["events"])


@router.get("/{run_id}/events")
def list_run_events(run_id: str, db: Session = Depends(get_db)):
    events = list(db.scalars(select(Event).where(Event.run_id == run_id).order_by(Event.created_at.asc())))
    if not events:
        return []
    return [
        {
            "id": e.id,
            "run_id": e.run_id,
            "step_id": e.step_id,
            "event_type": e.event_type,
            "payload_json": e.payload_json,
            "created_at": e.created_at,
        }
        for e in events
    ]
