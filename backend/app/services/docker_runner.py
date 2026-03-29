from __future__ import annotations

import os
import subprocess
import uuid
from pathlib import Path

from sqlalchemy.orm import Session

from app.models import ExecutionEnvironment, Project, Run
from app.models.enums import EnvironmentStatus
from app.services.runs import _id

BASE = Path('/home/ethanturk/.openclaw/workspace/coding-agent/runtime_containers')
DEFAULT_IMAGE = 'python:3.11.5-slim'


def _run(command: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, capture_output=True, text=True, check=True)


def get_github_token() -> str | None:
    token = os.environ.get('GITHUB_TOKEN')
    if token:
        return token
    cred = subprocess.run(
        ['git', 'credential', 'fill'],
        input='protocol=https\nhost=github.com\n\n',
        capture_output=True,
        text=True,
    )
    if cred.returncode == 0:
        for line in cred.stdout.splitlines():
            if line.startswith('password='):
                return line.split('=', 1)[1].strip() or None
    gh = subprocess.run(['gh', 'auth', 'token'], capture_output=True, text=True)
    if gh.returncode == 0 and gh.stdout.strip():
        return gh.stdout.strip()
    return None


def ensure_docker_environment(db: Session, run: Run, project: Project) -> ExecutionEnvironment:
    existing = db.query(ExecutionEnvironment).filter(ExecutionEnvironment.run_id == run.id).first()
    if existing:
        return existing

    env = ExecutionEnvironment(
        id=_id('env'),
        run_id=run.id,
        provider='docker',
        image=DEFAULT_IMAGE,
        status=EnvironmentStatus.CREATING,
        repo_dir='/workspace/repo',
        branch_name=f'agent-platform/{run.id}',
    )
    db.add(env)
    db.commit()
    db.refresh(env)
    return env


def create_container(db: Session, env: ExecutionEnvironment) -> ExecutionEnvironment:
    if env.container_id:
        inspect = subprocess.run(['docker', 'inspect', env.container_id], capture_output=True, text=True)
        if inspect.returncode == 0:
            return env
        env.container_id = None
    BASE.mkdir(parents=True, exist_ok=True)
    name = f'agent-platform-{uuid.uuid4().hex[:12]}'
    command = [
        'docker', 'run', '-d', '--rm', '--name', name,
        '-w', '/workspace',
    ]
    github_token = get_github_token()
    if github_token:
        command.extend(['-e', f'GITHUB_TOKEN={github_token}'])
    command.extend([
        env.image or DEFAULT_IMAGE,
        'sleep', 'infinity'
    ])
    result = _run(command)
    env.container_id = result.stdout.strip()
    env.status = EnvironmentStatus.READY
    db.commit()
    db.refresh(env)
    return env


def _sanitize(command: str) -> str:
    token = get_github_token()
    return command.replace(token, '***') if token else command


def exec_in_container(env: ExecutionEnvironment, command: str) -> dict:
    result = subprocess.run(['docker', 'exec', env.container_id, 'sh', '-lc', command], capture_output=True, text=True, timeout=300)
    return {
        'ok': result.returncode == 0,
        'stdout': result.stdout,
        'stderr': result.stderr,
        'returncode': result.returncode,
        'command': _sanitize(command),
    }


def read_file_in_container(env: ExecutionEnvironment, path: str) -> dict:
    return exec_in_container(env, f"cat {path}")


def write_file_in_container(env: ExecutionEnvironment, path: str, content: str) -> dict:
    escaped = content.replace('\\', '\\\\').replace('"', '\\"').replace('$', '\\$').replace('`', '\\`')
    return exec_in_container(env, f'cat <<"EOF" > {path}\n{escaped}\nEOF')


def edit_file_in_container(env: ExecutionEnvironment, path: str, old_text: str, new_text: str) -> dict:
    content = read_file_in_container(env, path)
    if not content['ok']:
        return content
    body = content['stdout']
    if old_text not in body:
        return {'ok': False, 'stderr': 'old_text not found in file', 'stdout': '', 'returncode': 1, 'command': 'edit'}
    updated = body.replace(old_text, new_text, 1)
    write = write_file_in_container(env, path, updated)
    if not write['ok']:
        return write
    return {'ok': True, 'stdout': updated, 'stderr': '', 'returncode': 0, 'command': 'edit'}


def list_files_in_container(env: ExecutionEnvironment, path: str | None = None) -> dict:
    repo_dir = path or env.repo_dir or '/workspace/repo'
    return exec_in_container(env, f"cd {repo_dir} && find . -type f | sed 's#^./##' | head -500")


def git_status_in_container(env: ExecutionEnvironment) -> dict:
    return exec_in_container(env, f"cd {env.repo_dir} && git status --short")


def git_diff_in_container(env: ExecutionEnvironment) -> dict:
    return exec_in_container(env, f"cd {env.repo_dir} && git diff -- .")


def bootstrap_repo_in_container(db: Session, env: ExecutionEnvironment, project: Project) -> dict:
    if not project.repo_url:
        return {'ok': False, 'stderr': 'Project has no repo_url configured'}
    exec_in_container(env, 'apt-get update >/dev/null 2>&1 && apt-get install -y git >/dev/null 2>&1')
    repo_url = project.repo_url
    if repo_url.startswith('https://github.com/'):
        repo_url = repo_url.replace('https://github.com/', 'https://x-access-token:$GITHUB_TOKEN@github.com/')
    clone_result = exec_in_container(env, f"git clone {repo_url} {env.repo_dir}")
    if not clone_result['ok'] and 'already exists' not in (clone_result['stderr'] or ''):
        env.status = EnvironmentStatus.FAILED
        db.commit()
        return clone_result
    branch = env.branch_name or f'agent-platform/{env.run_id}'
    checkout_result = exec_in_container(env, f"cd {env.repo_dir} && git checkout -b {branch} {project.default_branch or 'main'}")
    if not checkout_result['ok'] and 'already exists' not in (checkout_result['stderr'] or ''):
        env.status = EnvironmentStatus.FAILED
        db.commit()
        return checkout_result
    env.status = EnvironmentStatus.RUNNING
    db.commit()
    return {'ok': True, 'clone': clone_result, 'checkout': checkout_result, 'repo_dir': env.repo_dir, 'branch': branch}


def push_branch_from_container(env: ExecutionEnvironment, project: Project, message: str = 'agent-platform update') -> dict:
    repo_url = project.repo_url or ''
    if repo_url.startswith('https://github.com/'):
        repo_url = repo_url.replace('https://github.com/', 'https://x-access-token:$GITHUB_TOKEN@github.com/')
    commands = [
        f"cd {env.repo_dir}",
        "git config user.name 'Agent Platform'",
        "git config user.email 'agent-platform@local'",
        "git add .",
        f"git commit -m \"{message}\" || true",
        f"git remote set-url origin {repo_url}",
        f"git push -u origin {env.branch_name}"
    ]
    return exec_in_container(env, ' && '.join(commands))


def destroy_container(db: Session, env: ExecutionEnvironment) -> ExecutionEnvironment:
    if env.container_id:
        subprocess.run(['docker', 'rm', '-f', env.container_id], capture_output=True, text=True)
    env.container_id = None
    env.status = EnvironmentStatus.DESTROYED
    db.commit()
    db.refresh(env)
    return env
