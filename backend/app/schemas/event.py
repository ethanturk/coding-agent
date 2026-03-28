from datetime import datetime
from pydantic import BaseModel


class EventRead(BaseModel):
    id: str
    run_id: str
    step_id: str | None = None
    event_type: str
    payload_json: dict
    created_at: datetime

    model_config = {"from_attributes": True}
