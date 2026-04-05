from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.api.dependencies import get_run_or_404, get_latest_env
from app.models import PullRequest

router = APIRouter(prefix="/runs", tags=["run-meta"])


@router.get("/{run_id}/environment/meta")
def get_run_environment(run_id: str, db: Session = Depends(get_db)):
    get_run_or_404(db, run_id)
    env = get_latest_env(db, run_id)
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
    get_run_or_404(db, run_id)
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
