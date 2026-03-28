import asyncio
import json

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.services.events import list_events_for_run

router = APIRouter(prefix="/runs", tags=["stream"])


@router.get("/{run_id}/stream")
def stream_run_events(run_id: str, db: Session = Depends(get_db)):
    async def event_generator():
        seen = set()
        while True:
            events = list_events_for_run(db, run_id)
            for event in events:
                if event.id in seen:
                    continue
                seen.add(event.id)
                payload = {
                    "id": event.id,
                    "event_type": event.event_type,
                    "payload_json": event.payload_json,
                    "created_at": event.created_at.isoformat(),
                }
                yield f"data: {json.dumps(payload)}\n\n"
            await asyncio.sleep(1)

    return StreamingResponse(event_generator(), media_type="text/event-stream")
