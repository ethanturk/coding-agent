from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models import ExecutionEnvironment, PullRequest, Run

router = APIRouter(prefix="/runs", tags=["run-meta"])


@router.get("/{run_id}/environment/meta")
def get_run_environment(run_id: str, db: Session = Depends(get_db)):
    if not db.get(Run, run_id):
        raise HTTPException(status_code=404, detail="Run not found")
    env = db.query(ExecutionEnvironment).filter(ExecutionEnvironment.run_id == run_id).order_by(ExecutionEnvironment.created_at.desc()).first()
    if not env:
        return None
    return {
        'id': env.id,
        'provider': env.provider,
        'image': env.image,
        'container_id': env.container_id,
        'status': env.status,
        'repo_dir': env.repo_dir,
        'branch_name': env.branch_name,
    }


@router.get("/{run_id}/pull-request/meta")
def get_run_pull_request(run_id: str, db: Session = Depends(get_db)):
    if not db.get(Run, run_id):
        raise HTTPException(status_code=404, detail="Run not found")
    pr = db.query(PullRequest).filter(PullRequest.run_id == run_id).order_by(PullRequest.created_at.desc()).first()
    if not pr:
        return None
    return {
        'id': pr.id,
        'repo': pr.repo,
        'branch_name': pr.branch_name,
        'pr_number': pr.pr_number,
        'pr_url': pr.pr_url,
        'status': pr.status,
        'merge_commit_sha': pr.merge_commit_sha,
    }
