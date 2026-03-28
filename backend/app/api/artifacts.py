from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models import Artifact

router = APIRouter(prefix="/runs", tags=["artifacts"])


@router.get("/{run_id}/artifacts")
def list_run_artifacts(run_id: str, db: Session = Depends(get_db)):
    artifacts = list(db.scalars(select(Artifact).where(Artifact.run_id == run_id).order_by(Artifact.created_at.asc())))
    return [
        {
            "id": a.id,
            "run_id": a.run_id,
            "step_id": a.step_id,
            "artifact_type": a.artifact_type,
            "name": a.name,
            "storage_uri": a.storage_uri,
            "summary": a.summary,
            "created_at": a.created_at,
        }
        for a in artifacts
    ]
