from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Event


def list_events_for_run(db: Session, run_id: str) -> list[Event]:
    return list(db.scalars(select(Event).where(Event.run_id == run_id).order_by(Event.created_at.asc())))
