import logging
from urllib.parse import urlparse

import httpx
from sqlalchemy.orm import Session

from app.models import PullRequest, Run
from app.models.enums import PullRequestStatus
from app.services.docker_runner import get_github_token
from app.services.runs import _id

logger = logging.getLogger(__name__)

GITHUB_API = "https://api.github.com"


def repo_slug(repo_url: str) -> str:
    path = urlparse(repo_url).path.strip('/')
    return path.removesuffix('.git')


def _github_headers() -> dict[str, str]:
    token = get_github_token()
    headers = {"Accept": "application/vnd.github+json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


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


def create_pull_request(repo: str, branch: str, base: str, title: str, body: str) -> dict:
    """Create a pull request using the GitHub REST API."""
    headers = _github_headers()
    url = f"{GITHUB_API}/repos/{repo}/pulls"
    payload = {
        "title": title,
        "body": body,
        "head": branch,
        "base": base,
    }
    try:
        resp = httpx.post(url, json=payload, headers=headers, timeout=30)
        if resp.status_code in (200, 201):
            data = resp.json()
            return {
                'ok': True,
                'payload': {
                    'url': data.get('html_url'),
                    'number': data.get('number'),
                    'state': data.get('state', '').upper(),
                },
                'stderr': '',
            }
        else:
            error_msg = resp.text[:500]
            logger.warning("GitHub PR create failed (%d): %s", resp.status_code, error_msg)
            return {
                'ok': False,
                'stderr': f"GitHub API error ({resp.status_code}): {error_msg}",
                'payload': {},
            }
    except httpx.HTTPError as exc:
        return {
            'ok': False,
            'stderr': f"HTTP error: {exc}",
            'payload': {},
        }


def fetch_pull_request(repo: str, pr_number: int) -> dict:
    """Fetch pull request details using the GitHub REST API."""
    headers = _github_headers()
    url = f"{GITHUB_API}/repos/{repo}/pulls/{pr_number}"
    try:
        resp = httpx.get(url, headers=headers, timeout=30)
        if resp.status_code == 200:
            data = resp.json()
            merge_commit = None
            if data.get('merge_commit_sha'):
                merge_commit = {'oid': data['merge_commit_sha']}
            return {
                'ok': True,
                'payload': {
                    'number': data.get('number'),
                    'url': data.get('html_url'),
                    'state': data.get('state', '').upper(),
                    'title': data.get('title'),
                    'headRefName': data.get('head', {}).get('ref'),
                    'baseRefName': data.get('base', {}).get('ref'),
                    'mergeCommit': merge_commit,
                    'isDraft': data.get('draft', False),
                    'reviewDecision': None,  # Not directly available via REST
                },
                'stderr': '',
            }
        else:
            return {
                'ok': False,
                'stderr': f"GitHub API error ({resp.status_code}): {resp.text[:500]}",
                'payload': None,
            }
    except httpx.HTTPError as exc:
        return {
            'ok': False,
            'stderr': f"HTTP error: {exc}",
            'payload': None,
        }


def merge_pull_request(repo: str, pr_number: int) -> dict:
    """Merge a pull request using the GitHub REST API."""
    headers = _github_headers()
    url = f"{GITHUB_API}/repos/{repo}/pulls/{pr_number}/merge"
    try:
        resp = httpx.put(url, json={"merge_method": "merge"}, headers=headers, timeout=30)
        if resp.status_code == 200:
            return {'ok': True, 'stderr': ''}
        else:
            return {
                'ok': False,
                'stderr': f"GitHub API error ({resp.status_code}): {resp.text[:500]}",
            }
    except httpx.HTTPError as exc:
        return {
            'ok': False,
            'stderr': f"HTTP error: {exc}",
        }
