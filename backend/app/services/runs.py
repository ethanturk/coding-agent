from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models import Event, Run, Step
from app.models.enums import AgentRole, RunStatus, StepKind, StepStatus
from app.schemas.run import RunCreate
from app.services.id_gen import generate_id as _id


def create_run(db: Session, data: RunCreate) -> Run:
    run = Run(
        id=_id("run"),
        project_id=data.project_id,
        title=data.title,
        goal=data.goal,
        status=RunStatus.QUEUED,
    )
    db.add(run)
    db.flush()

    step = Step(
        id=_id("step"),
        run_id=run.id,
        sequence_index=1,
        kind=StepKind.PLANNING,
        role=AgentRole.PLANNER,
        title="Create initial plan",
        status=StepStatus.QUEUED,
        input_json={"goal": data.goal},
    )
    db.add(step)
    db.flush()
    run.current_step_id = step.id
    db.add(Event(id=_id("evt"), run_id=run.id, step_id=step.id, event_type="run.created", payload_json={"title": run.title}))
    db.commit()
    db.refresh(run)
    return get_run(db, run.id)


def list_runs(db: Session) -> list[Run]:
    return list(db.scalars(select(Run).options(selectinload(Run.steps)).order_by(Run.created_at.desc())))


def get_run(db: Session, run_id: str) -> Run | None:
    stmt = select(Run).options(selectinload(Run.steps)).where(Run.id == run_id)
    return db.scalars(stmt).first()
