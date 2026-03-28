from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import PlainTextResponse

router = APIRouter(prefix="/files", tags=["files"])

BASE = Path('/home/ethanturk/.openclaw/workspace/agent-platform-mvp/runtime_artifacts').resolve()


@router.get("/artifact")
def read_artifact(path: str):
    artifact_path = Path(path).resolve()
    if BASE not in artifact_path.parents and artifact_path != BASE:
        raise HTTPException(status_code=400, detail="Invalid artifact path")
    if not artifact_path.exists():
        raise HTTPException(status_code=404, detail="Artifact not found")
    return PlainTextResponse(artifact_path.read_text())
