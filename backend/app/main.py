from fastapi import FastAPI

from app.api.approvals import router as approvals_router
from app.api.artifacts import router as artifacts_router
from app.api.diff import router as diff_router
from app.api.edits import router as edits_router
from app.api.environments import router as environments_router
from app.api.events import router as events_router
from app.api.files import router as files_router
from app.api.patches import router as patches_router
from app.api.projects import router as projects_router
from app.api.proposals import router as proposals_router
from app.api.pull_requests import router as pull_requests_router
from app.api.repo import router as repo_router
from app.api.run_meta import router as run_meta_router
from app.api.run_diff import router as run_diff_router
from app.api.run_repo import router as run_repo_router
from app.api.runs import router as runs_router
from app.api.settings import router as settings_router
from app.api.stream import router as stream_router

app = FastAPI(title="Agent Platform MVP")
app.include_router(projects_router, prefix="/api")
app.include_router(repo_router, prefix="/api")
app.include_router(diff_router, prefix="/api")
app.include_router(runs_router, prefix="/api")
app.include_router(environments_router, prefix="/api")
app.include_router(run_meta_router, prefix="/api")
app.include_router(run_repo_router, prefix="/api")
app.include_router(run_diff_router, prefix="/api")
app.include_router(edits_router, prefix="/api")
app.include_router(proposals_router, prefix="/api")
app.include_router(pull_requests_router, prefix="/api")
app.include_router(patches_router, prefix="/api")
app.include_router(settings_router, prefix="/api")
app.include_router(events_router, prefix="/api")
app.include_router(artifacts_router, prefix="/api")
app.include_router(stream_router, prefix="/api")
app.include_router(approvals_router, prefix="/api")
app.include_router(files_router, prefix="/api")


@app.get("/health")
def health():
    return {"ok": True}
