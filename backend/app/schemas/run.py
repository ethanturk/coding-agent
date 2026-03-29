from datetime import datetime
from pydantic import BaseModel

from app.models.enums import AgentRole, RunStatus, StepKind, StepStatus
from app.schemas.run_operator_summary import RunListOperatorSummary, RunOperatorSummary


class RunCreate(BaseModel):
    project_id: str
    title: str
    goal: str


class StepRead(BaseModel):
    id: str
    sequence_index: int
    kind: StepKind
    role: AgentRole
    title: str
    status: StepStatus
    input_json: dict | None = None
    output_json: dict | None = None
    error_summary: str | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class RunRead(BaseModel):
    id: str
    project_id: str
    title: str
    goal: str
    status: RunStatus
    current_step_id: str | None = None
    final_summary: str | None = None
    created_at: datetime
    updated_at: datetime
    steps: list[StepRead] = []
    operator_summary: RunOperatorSummary | None = None

    model_config = {"from_attributes": True}


class RunListRead(BaseModel):
    id: str
    project_id: str
    title: str
    goal: str
    status: RunStatus
    current_step_id: str | None = None
    final_summary: str | None = None
    created_at: datetime
    updated_at: datetime
    operator_summary: RunListOperatorSummary | None = None

    model_config = {"from_attributes": True}
