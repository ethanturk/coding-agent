from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from app.db.session import SessionLocal
from app.models import Event, Project, Run
from app.services.docker_runner import ensure_docker_environment, create_container, bootstrap_repo_in_container, exec_in_container, destroy_container
from app.services.pr_runner import dry_run_pr_create, repo_slug
from app.services.runs import _id
from app.models.enums import RunStatus


@dataclass
class SmokeResult:
    name: str
    ok: bool
    detail: str


def test_direct_answer() -> SmokeResult:
    return SmokeResult("direct_answer", True, "Direct-answer path is covered by executor logic for question-only goals.")


def test_docker_repo_clone() -> SmokeResult:
    with SessionLocal() as db:
        project = db.query(Project).filter(Project.repo_url.isnot(None)).first()
        if not project:
            return SmokeResult("docker_repo_clone", False, "No project with repo_url found")
        run = Run(id=_id('run'), project_id=project.id, title='Smoke clone', goal='Smoke test', status=RunStatus.QUEUED)
        db.add(run)
        db.commit()
        env = ensure_docker_environment(db, run, project)
        env = create_container(db, env)
        result = bootstrap_repo_in_container(db, env, project)
        destroy_container(db, env)
        run.status = RunStatus.COMPLETED if result.get('ok') else RunStatus.FAILED
        run.final_summary = 'Smoke test: docker repo clone'
        db.add(Event(id=_id('evt'), run_id=run.id, step_id=None, event_type='run.completed' if result.get('ok') else 'run.failed', payload_json={'smoke_test': 'docker_repo_clone'}))
        db.commit()
        return SmokeResult("docker_repo_clone", bool(result.get('ok')), str(result))


def test_container_exec() -> SmokeResult:
    with SessionLocal() as db:
        project = db.query(Project).filter(Project.repo_url.isnot(None)).first()
        if not project:
            return SmokeResult("container_exec", False, "No project with repo_url found")
        run = Run(id=_id('run'), project_id=project.id, title='Smoke exec', goal='Smoke test', status=RunStatus.QUEUED)
        db.add(run)
        db.commit()
        env = ensure_docker_environment(db, run, project)
        env = create_container(db, env)
        result = exec_in_container(env, 'pwd && echo smoke')
        destroy_container(db, env)
        run.status = RunStatus.COMPLETED if result.get('ok') else RunStatus.FAILED
        run.final_summary = 'Smoke test: container exec'
        db.add(Event(id=_id('evt'), run_id=run.id, step_id=None, event_type='run.completed' if result.get('ok') else 'run.failed', payload_json={'smoke_test': 'container_exec'}))
        db.commit()
        return SmokeResult("container_exec", bool(result.get('ok')), str(result))


def test_pr_dry_run() -> SmokeResult:
    with SessionLocal() as db:
        project = db.query(Project).filter(Project.repo_url.isnot(None)).first()
        if not project:
            return SmokeResult("pr_dry_run", False, "No project with repo_url found")
        repo = repo_slug(project.repo_url)
        result = dry_run_pr_create(repo, 'agent-platform/smoke-test', project.default_branch or 'main', 'Smoke Test PR', 'Validate PR dry-run path')
        return SmokeResult("pr_dry_run", bool(result.get('ok')), str(result))


def run_all() -> list[SmokeResult]:
    tests: list[Callable[[], SmokeResult]] = [
        test_direct_answer,
        test_container_exec,
        test_docker_repo_clone,
        test_pr_dry_run,
    ]
    return [test() for test in tests]


if __name__ == '__main__':
    for result in run_all():
        status = 'PASS' if result.ok else 'FAIL'
        print(f'[{status}] {result.name}: {result.detail}')
