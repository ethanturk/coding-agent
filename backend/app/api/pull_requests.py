from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models import Event, ExecutionEnvironment, Project, PullRequest, Run
from app.models.enums import PullRequestStatus, RunStatus
from app.services.docker_runner import bootstrap_repo_in_container, create_container, destroy_container, ensure_docker_environment, push_branch_from_container
from app.services.pr_runner import create_pull_request, create_pull_request_record, fetch_pull_request, merge_pull_request, repo_slug
from app.services.runs import _id

router = APIRouter(prefix="/runs", tags=["pull-requests"])


@router.post("/{run_id}/pull-request")
def open_pull_request(run_id: str, db: Session = Depends(get_db)):
    run = db.get(Run, run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    project = db.get(Project, run.project_id)
    if not project or not project.repo_url:
        raise HTTPException(status_code=400, detail="Project repo_url is required")

    env = ensure_docker_environment(db, run, project)
    env = create_container(db, env)
    bootstrap = bootstrap_repo_in_container(db, env, project)
    if not bootstrap.get('ok'):
        raise HTTPException(status_code=400, detail=bootstrap.get('stderr') or 'Failed to bootstrap repo')

    push = push_branch_from_container(env, project)
    if not push.get('ok'):
        raise HTTPException(status_code=400, detail=push.get('stderr') or 'Failed to push branch')

    repo = repo_slug(project.repo_url)
    title = f"Agent Platform: {run.title}"
    body = run.goal
    created = create_pull_request(repo, env.branch_name or f'agent-platform/{run.id}', project.default_branch or 'main', title, body)
    if not created.get('ok'):
        raise HTTPException(status_code=400, detail=created.get('stderr') or 'Failed to create PR')

    pr = create_pull_request_record(db, run, repo, env.branch_name or f'agent-platform/{run.id}')
    payload = created.get('payload', {})
    pr.pr_number = payload.get('number')
    pr.pr_url = payload.get('url')
    pr.status = PullRequestStatus.OPEN
    db.add(Event(id=_id('evt'), run_id=run.id, step_id=run.current_step_id, event_type='pull_request.opened', payload_json={
        'pr_id': pr.id,
        'pr_number': pr.pr_number,
        'pr_url': pr.pr_url,
        'branch_name': pr.branch_name,
        'repo': pr.repo,
    }))
    db.commit()
    db.refresh(pr)
    return {'id': pr.id, 'number': pr.pr_number, 'url': pr.pr_url, 'status': pr.status}


@router.post("/{run_id}/pull-request/refresh")
def refresh_run_pull_request(run_id: str, db: Session = Depends(get_db)):
    run = db.get(Run, run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    pr = db.query(PullRequest).filter(PullRequest.run_id == run_id).order_by(PullRequest.created_at.desc()).first()
    if not pr or not pr.pr_number or not pr.repo:
        raise HTTPException(status_code=404, detail="Pull request not found")

    fetched = fetch_pull_request(pr.repo, pr.pr_number)
    if not fetched.get('ok'):
        raise HTTPException(status_code=400, detail=fetched.get('stderr') or 'Failed to refresh pull request')

    payload = fetched.get('payload') or {}
    pr.pr_url = payload.get('url') or pr.pr_url
    pr.branch_name = payload.get('headRefName') or pr.branch_name
    state = str(payload.get('state') or '').upper()
    if state == 'MERGED':
        pr.status = PullRequestStatus.MERGED
    elif state == 'CLOSED':
        pr.status = PullRequestStatus.CLOSED
    else:
        pr.status = PullRequestStatus.OPEN

    merge_commit = payload.get('mergeCommit') or {}
    pr.merge_commit_sha = merge_commit.get('oid') or pr.merge_commit_sha
    db.add(Event(id=_id('evt'), run_id=run.id, step_id=run.current_step_id, event_type='pull_request.refreshed', payload_json={
        'pr_id': pr.id,
        'pr_number': pr.pr_number,
        'pr_url': pr.pr_url,
        'status': pr.status.value if hasattr(pr.status, 'value') else pr.status,
        'title': payload.get('title'),
        'review_decision': payload.get('reviewDecision'),
        'is_draft': payload.get('isDraft'),
        'base_ref_name': payload.get('baseRefName'),
        'head_ref_name': payload.get('headRefName'),
        'merge_commit_sha': pr.merge_commit_sha,
    }))
    db.commit()
    db.refresh(pr)
    return {
        'id': pr.id,
        'number': pr.pr_number,
        'url': pr.pr_url,
        'status': pr.status,
        'provider': pr.provider,
        'title': payload.get('title'),
        'reviewDecision': payload.get('reviewDecision'),
        'isDraft': payload.get('isDraft'),
        'baseRefName': payload.get('baseRefName'),
        'headRefName': payload.get('headRefName'),
        'mergeCommit': merge_commit,
    }


@router.post("/{run_id}/pull-request/merge")
def merge_run_pull_request(run_id: str, db: Session = Depends(get_db)):
    run = db.get(Run, run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    pr = db.query(PullRequest).filter(PullRequest.run_id == run_id).order_by(PullRequest.created_at.desc()).first()
    if not pr or not pr.pr_number or not pr.repo:
        raise HTTPException(status_code=404, detail="Pull request not found")
    if pr.status != PullRequestStatus.OPEN:
        raise HTTPException(status_code=400, detail="Only open pull requests can be merged")
    merged = merge_pull_request(pr.repo, pr.pr_number)
    if not merged.get('ok'):
        raise HTTPException(status_code=400, detail=merged.get('stderr') or 'Failed to merge PR')
    pr.status = PullRequestStatus.MERGED
    run.status = RunStatus.COMPLETED
    run.final_summary = f'Merged PR #{pr.pr_number}'
    env = db.query(ExecutionEnvironment).filter_by(run_id=run_id).first()
    if env:
        destroy_container(db, env)
    db.add(Event(id=_id('evt'), run_id=run.id, step_id=run.current_step_id, event_type='pull_request.merged', payload_json={
        'pr_id': pr.id,
        'pr_number': pr.pr_number,
        'pr_url': pr.pr_url,
        'summary': run.final_summary,
        'merge_commit_sha': pr.merge_commit_sha,
    }))
    db.add(Event(id=_id('evt'), run_id=run.id, step_id=run.current_step_id, event_type='run.completed', payload_json={'summary': run.final_summary, 'pr_url': pr.pr_url}))
    db.commit()
    return {'ok': True, 'status': pr.status, 'summary': run.final_summary}
