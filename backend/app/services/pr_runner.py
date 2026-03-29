import json
import subprocess
from urllib.parse import urlparse

from sqlalchemy.orm import Session

from app.models import PullRequest, Run
from app.models.enums import PullRequestStatus
from app.services.runs import _id


def repo_slug(repo_url: str) -> str:
    path = urlparse(repo_url).path.strip('/')
    return path.removesuffix('.git')


def create_pull_request_record(db: Session, run: Run, repo: str, branch: str) -> PullRequest:
    pr = PullRequest(
        id=_id('pr'),
        run_id=run.id,
        provider='github',
        repo=repo,
        branch_name=branch,
        status=PullRequestStatus.OPEN,
    )
    db.add(pr)
    db.commit()
    db.refresh(pr)
    return pr


def dry_run_pr_create(repo: str, branch: str, base: str, title: str, body: str) -> dict:
    result = subprocess.run([
        'gh', 'pr', 'create', '--repo', repo, '--head', branch, '--base', base,
        '--title', title, '--body', body, '--dry-run'
    ], capture_output=True, text=True)
    return {
        'ok': result.returncode == 0,
        'stdout': result.stdout,
        'stderr': result.stderr,
        'returncode': result.returncode,
    }


def create_pull_request(repo: str, branch: str, base: str, title: str, body: str) -> dict:
    result = subprocess.run([
        'gh', 'pr', 'create', '--repo', repo, '--head', branch, '--base', base,
        '--title', title, '--body', body
    ], capture_output=True, text=True)
    url = result.stdout.strip().splitlines()[-1] if result.returncode == 0 and result.stdout.strip() else None
    pr_number = None
    if url and '/pull/' in url:
        try:
            pr_number = int(url.rstrip('/').split('/pull/')[-1])
        except Exception:
            pr_number = None
    payload = {'url': url, 'number': pr_number, 'state': 'OPEN' if url else None}
    return {
        'ok': result.returncode == 0,
        'stdout': result.stdout,
        'stderr': result.stderr,
        'returncode': result.returncode,
        'payload': payload,
    }


def fetch_pull_request(repo: str, pr_number: int) -> dict:
    result = subprocess.run([
        'gh', 'pr', 'view', str(pr_number), '--repo', repo,
        '--json', 'number,url,state,title,headRefName,baseRefName,mergeCommit,reviewDecision,isDraft'
    ], capture_output=True, text=True)
    payload = None
    if result.returncode == 0 and result.stdout.strip():
        try:
            payload = json.loads(result.stdout)
        except Exception:
            payload = None
    return {
        'ok': result.returncode == 0,
        'stdout': result.stdout,
        'stderr': result.stderr,
        'returncode': result.returncode,
        'payload': payload,
    }


def merge_pull_request(repo: str, pr_number: int) -> dict:
    result = subprocess.run([
        'gh', 'pr', 'merge', str(pr_number), '--repo', repo, '--merge', '--delete-branch'
    ], capture_output=True, text=True)
    return {
        'ok': result.returncode == 0,
        'stdout': result.stdout,
        'stderr': result.stderr,
        'returncode': result.returncode,
    }
