"""Run execution via DeepAgents orchestration.

Bootstraps a Docker sandbox, builds a DeepAgents orchestrator with
role-specific models and the Docker-backed filesystem, invokes it
with the user's goal, and persists results as Steps/Events/Artifacts.
Applies configurable autonomy to decide whether changes auto-apply
or require human approval.
"""

from __future__ import annotations

import json
import logging
import random
import time
from pathlib import Path

from sqlalchemy.orm import Session

from app.models import Approval, Artifact, Event, Project, Run, Step
from app.models.enums import (
    AgentRole,
    ApprovalStatus,
    ApprovalType,
    ArtifactType,
    RunStatus,
    StepKind,
    StepStatus,
)
from app.graph.workflow import build_deep_agent, invoke_deep_agent, resume_deep_agent
from app.services.approval_flow import (
    build_plan_approval_payload,
    build_review_approval_payload,
    classify_changed_files,
    extract_approved_plan,
    get_scope_control,
    scope_guard_decision,
    should_interrupt_before_write,
)
from app.services.context_manager import resolve_langchain_model
from app.services.deepagents_fs import DockerSandbox
from app.services.planning import build_initial_plan, collect_repo_files, enrich_plan_if_possible, serialize_plan
from app.services.docker_runner import (
    bootstrap_repo_in_container,
    create_container,
    ensure_docker_environment,
    exec_in_container,
)
from app.services.runs import _id
from app.services.settings import get_settings, resolve_role_model



def _complete_filesystem_cleanup(db: Session, run: Run, planning_step: Step, env, approved_plan: dict) -> Run:
    operations = approved_plan.get('operations') or []
    deleted_matches: list[str] = []
    deleted_patterns: list[str] = []

    implementation_step = Step(
        id=_id('step'),
        run_id=run.id,
        sequence_index=2,
        kind=StepKind.IMPLEMENTATION,
        role=AgentRole.DEVELOPER,
        title='Filesystem cleanup implementation',
        status=StepStatus.RUNNING,
        input_json={
            'approved_plan': approved_plan,
            'goal': run.goal,
        },
    )
    db.add(implementation_step)
    db.flush()
    db.add(Event(id=_id('evt'), run_id=run.id, step_id=implementation_step.id, event_type='step.started', payload_json={'title': implementation_step.title}))

    for op in operations:
        if op.get('type') != 'delete_path':
            continue
        matches = [match.rstrip('/') for match in (op.get('matches') or []) if match]
        if not matches:
            continue
        for rel_path in matches:
            result = exec_in_container(env, f"cd {env.repo_dir} && rm -rf -- '{rel_path}'")
            if not result.get('ok'):
                implementation_step.status = StepStatus.FAILED
                implementation_step.error_summary = result.get('stderr') or f'Failed to delete approved path {rel_path}'
                run.status = RunStatus.FAILED
                run.final_summary = implementation_step.error_summary
                db.add(Event(id=_id('evt'), run_id=run.id, step_id=implementation_step.id, event_type='run.failed', payload_json={'error': implementation_step.error_summary, 'phase': 'filesystem_cleanup'}))
                db.commit()
                db.refresh(run)
                return run
            deleted_matches.append(rel_path)
        deleted_patterns.append(op.get('path'))
        db.add(Event(id=_id('evt'), run_id=run.id, step_id=implementation_step.id, event_type='filesystem.path_deleted', payload_json={'path': op.get('path'), 'matches': matches}))

    status_result = exec_in_container(env, f"cd {env.repo_dir} && git status --short")
    status_output = (status_result.get('stdout') or '').strip()
    if not status_result.get('ok'):
        implementation_step.status = StepStatus.FAILED
        implementation_step.error_summary = status_result.get('stderr') or 'Failed to verify git status'
        run.status = RunStatus.FAILED
        run.final_summary = implementation_step.error_summary
        db.add(Event(id=_id('evt'), run_id=run.id, step_id=implementation_step.id, event_type='run.failed', payload_json={'error': implementation_step.error_summary, 'phase': 'git_status'}))
        db.commit()
        db.refresh(run)
        return run

    constraints = approved_plan.get('constraints') or {}
    commit_cfg = approved_plan.get('commit') or {}
    if constraints.get('stage_changes'):
        stage_result = exec_in_container(env, f"cd {env.repo_dir} && git add -A")
        if not stage_result.get('ok'):
            implementation_step.status = StepStatus.FAILED
            implementation_step.error_summary = stage_result.get('stderr') or 'Failed to stage cleanup changes'
            run.status = RunStatus.FAILED
            run.final_summary = implementation_step.error_summary
            db.add(Event(id=_id('evt'), run_id=run.id, step_id=implementation_step.id, event_type='run.failed', payload_json={'error': implementation_step.error_summary, 'phase': 'git_add'}))
            db.commit()
            db.refresh(run)
            return run

    commit_output = None
    if commit_cfg.get('enabled') and deleted_matches:
        exec_in_container(env, f"cd {env.repo_dir} && git config user.name 'OpenClaw Agent'")
        exec_in_container(env, f"cd {env.repo_dir} && git config user.email 'openclaw-agent@local'")
        message = (commit_cfg.get('message') or '').replace("'", "'\\''")
        commit_result = exec_in_container(env, f"cd {env.repo_dir} && git commit -m '{message}'")
        if not commit_result.get('ok'):
            implementation_step.status = StepStatus.FAILED
            implementation_step.error_summary = (commit_result.get('stderr') or commit_result.get('stdout') or 'Failed to create cleanup commit')[:500]
            run.status = RunStatus.FAILED
            run.final_summary = implementation_step.error_summary
            db.add(Event(id=_id('evt'), run_id=run.id, step_id=implementation_step.id, event_type='run.failed', payload_json={'error': implementation_step.error_summary, 'phase': 'git_commit'}))
            db.commit()
            db.refresh(run)
            return run
        commit_output = (commit_result.get('stdout') or '').strip()

    implementation_step.status = StepStatus.COMPLETED
    implementation_step.output_json = {
        'deleted_matches': deleted_matches,
        'deleted_patterns': deleted_patterns,
        'git_status': status_output,
        'commit_output': commit_output,
    }
    planning_step.status = StepStatus.COMPLETED
    review_step = Step(
        id=_id('step'),
        run_id=run.id,
        sequence_index=3,
        kind=StepKind.REVIEW,
        role=AgentRole.REVIEWER,
        title='Filesystem cleanup review',
        status=StepStatus.COMPLETED,
        input_json={'deleted_matches': deleted_matches},
        output_json={'decision': 'approved', 'summary': 'Filesystem cleanup executed deterministically from approved plan.'},
    )
    db.add(review_step)
    db.flush()
    run.status = RunStatus.COMPLETED
    run.current_step_id = review_step.id
    run.final_summary = f"Cleanup completed: removed {len(deleted_matches)} matched path(s)"
    db.add(Event(id=_id('evt'), run_id=run.id, step_id=review_step.id, event_type='run.completed', payload_json={'reason': 'filesystem_cleanup_completed', 'deleted_matches': deleted_matches, 'git_status': status_output, 'commit_output': commit_output}))
    db.commit()
    db.refresh(run)
    return run

logger = logging.getLogger(__name__)

ARTIFACT_BASE = Path("/home/ethanturk/.openclaw/workspace/coding-agent/runtime_artifacts")


def _write_artifact_file(run_id: str, name: str, content: str) -> str:
    base = ARTIFACT_BASE / run_id
    base.mkdir(parents=True, exist_ok=True)
    path = base / name
    path.write_text(content)
    return str(path)


def _add_artifact(
    db: Session,
    run: Run,
    step: Step,
    artifact_type: ArtifactType,
    name: str,
    uri: str,
    summary: str,
) -> Artifact:
    artifact = Artifact(
        id=_id("art"),
        run_id=run.id,
        step_id=step.id,
        artifact_type=artifact_type,
        name=name,
        storage_uri=uri,
        summary=summary,
    )
    db.add(artifact)
    db.add(
        Event(
            id=_id("evt"),
            run_id=run.id,
            step_id=step.id,
            event_type="artifact.created",
            payload_json={"artifact_id": artifact.id, "name": artifact.name},
        )
    )
    return artifact


def _bootstrap_sandbox(db: Session, run: Run, project: Project, *, force_clean_repo: bool = False):
    """Create and initialize Docker sandbox for a run."""
    env = ensure_docker_environment(db, run, project)
    env = create_container(db, env)
    bootstrap = bootstrap_repo_in_container(db, env, project, force_clean=force_clean_repo)
    if not bootstrap.get("ok"):
        raise ValueError(bootstrap.get("stderr") or "Failed to bootstrap repo in container")
    db.add(
        Event(
            id=_id("evt"),
            run_id=run.id,
            step_id=run.current_step_id,
            event_type="sandbox.ready",
            payload_json={
                "container_id": env.container_id,
                "repo_dir": env.repo_dir,
                "branch": env.branch_name,
            },
        )
    )
    db.commit()
    return env


def _resolve_models(settings: dict) -> dict:
    """Resolve LangChain model instances for each agent role."""
    models = {}
    for role in ("orchestrator", "planner", "developer", "reviewer"):
        try:
            models[role] = resolve_langchain_model(settings, role)
        except Exception as exc:
            logger.warning("Failed to resolve model for role %s: %s", role, exc)
            models[role] = None
    return models


def _is_transient_model_error(exc: Exception) -> bool:
    status_code = getattr(exc, 'status_code', None)
    if isinstance(status_code, int) and status_code in {408, 409, 429, 500, 502, 503, 504}:
        return True
    message = str(exc).lower()
    transient_markers = [
        'rate limit',
        'timeout',
        'temporarily unavailable',
        'try again later',
        'network error',
        'connection reset',
        'connection error',
        'internal server error',
        'server error',
        'bad gateway',
        'gateway timeout',
        'service unavailable',
    ]
    return any(marker in message for marker in transient_markers)



def _invoke_deep_agent_with_retries(*, agent, goal: str, test_command: str | None, inspect_command: str | None, thread_id: str | None, max_attempts: int = 3, base_delay_seconds: float = 1.5, max_delay_seconds: float = 10.0, jitter_ratio: float = 0.25) -> dict:
    max_attempts = max(1, int(max_attempts))
    base_delay_seconds = max(0.0, float(base_delay_seconds))
    max_delay_seconds = max(0.0, float(max_delay_seconds))
    jitter_ratio = max(0.0, float(jitter_ratio))
    last_exc: Exception | None = None
    for attempt in range(1, max_attempts + 1):
        try:
            return invoke_deep_agent(
                agent,
                goal=goal,
                test_command=test_command,
                inspect_command=inspect_command,
                thread_id=thread_id,
            )
        except Exception as exc:
            last_exc = exc
            if attempt >= max_attempts or not _is_transient_model_error(exc):
                raise
            raw_delay = base_delay_seconds * (2 ** (attempt - 1))
            capped_delay = min(raw_delay, max_delay_seconds)
            jitter_span = capped_delay * jitter_ratio
            delay = capped_delay + (random.uniform(-jitter_span, jitter_span) if jitter_span else 0.0)
            delay = max(0.0, delay)
            logger.warning('Transient model invocation failure on attempt %s/%s, retrying in %.2fs (raw=%.2fs, cap=%.2fs, jitter_ratio=%.2f): %s', attempt, max_attempts, delay, raw_delay, max_delay_seconds, jitter_ratio, exc)
            time.sleep(delay)
    if last_exc:
        raise last_exc
    raise RuntimeError('Deep agent invocation failed without an exception')



def _should_auto_approve(settings: dict, agent_result: dict, *, scope_guard: dict | None = None) -> bool:
    """Check if the run result meets the auto-approval threshold."""
    autonomy = settings.get("autonomy", {})
    threshold = float(autonomy.get("auto_approve_threshold", 0.8))
    confidence = float(agent_result.get("confidence", 0.0))
    review_decision = agent_result.get("review_decision")
    blocking_issues = agent_result.get("blocking_issues", [])

    if blocking_issues:
        return False
    if review_decision == "request_changes":
        return False
    if (scope_guard or {}).get("requires_human_review"):
        return False
    return confidence >= threshold


def _build_plan_for_run(db: Session, env, goal: str, settings: dict) -> tuple[dict, dict]:
    repo_result = exec_in_container(env, f"cd {env.repo_dir} && git ls-files")
    if not repo_result.get('ok'):
        raise ValueError(repo_result.get('stderr') or 'Failed to inspect repository files for planning')
    repo_files = collect_repo_files(repo_result.get('stdout') or '')
    draft_plan = build_initial_plan(goal, repo_files, settings=settings)
    enriched = enrich_plan_if_possible(db, goal, repo_files, draft_plan)
    return enriched['plan'], enriched.get('enrichment') or {'used': False, 'reason': 'not_available'}


def _implementation_project_context(project: Project, env, scope_control: dict, approved_plan: dict | None) -> str:
    project_context_parts = []
    if project.test_command:
        project_context_parts.append(f"Test command: `{project.test_command}`")
    if project.inspect_command:
        project_context_parts.append(f"Inspect command: `{project.inspect_command}`")
    if env.repo_dir:
        project_context_parts.append(f"Repository is cloned at: {env.repo_dir}")
    if env.branch_name:
        project_context_parts.append(f"Working branch: {env.branch_name}")
    project_context_parts.append(
        "Scope controls: "
        f"require_plan_approval={scope_control['require_plan_approval']}, "
        f"interrupt_before_write={scope_control['interrupt_before_write']}, "
        f"max_files_changed={scope_control['max_files_changed']}, "
        f"max_parallel_developer_tasks={scope_control['max_parallel_developer_tasks']}, "
        f"allow_path_expansion={scope_control['allow_path_expansion']}"
    )
    if approved_plan:
        project_context_parts.append("Approved plan JSON:\n" + serialize_plan(approved_plan))
        approved_targets = [target.get('path') for target in approved_plan.get('targets', []) if target.get('path')]
        if approved_targets:
            project_context_parts.append('Approved target files: ' + ', '.join(approved_targets))
    return "\n".join(project_context_parts)


def _run_has_completed_implementation(db: Session, run_id: str) -> bool:
    return (
        db.query(Step)
        .filter(
            Step.run_id == run_id,
            Step.kind == StepKind.IMPLEMENTATION,
            Step.status.in_([StepStatus.COMPLETED, StepStatus.FAILED]),
        )
        .first()
        is not None
    )


def _approved_plan_requires_continuation(approved_plan: dict | None) -> bool:
    if not approved_plan:
        return False
    if approved_plan.get('mode') == 'filesystem_cleanup':
        return True
    return bool(approved_plan.get('operations'))


def execute_run(db: Session, run_id: str) -> Run | None:
    """Execute a run using the DeepAgents orchestrator.

    Flow:
        1. Bootstrap Docker sandbox
        2. Resolve role-specific LangChain models from settings
        3. Build DeepAgents orchestrator with Docker sandbox backend
        4. Invoke orchestrator with the user's goal
        5. Persist results as Steps/Events/Artifacts
        6. Apply autonomy logic (auto-approve or create approval)
    """
    run = db.get(Run, run_id)
    if not run:
        return None
    project = db.get(Project, run.project_id)
    if not project:
        return None

    settings = get_settings(db).value_json
    role_model_configs = {
        role: resolve_role_model(settings, role)
        for role in ("orchestrator", "planner", "developer", "reviewer", "tester", "reporter")
    }
    scope_control = get_scope_control(settings)
    approved_plan = None

    run.status = RunStatus.RUNNING
    db.add(
        Event(
            id=_id("evt"),
            run_id=run.id,
            step_id=run.current_step_id,
            event_type="run.started",
            payload_json={
                "goal": run.goal,
                "role_models": role_model_configs,
                "engine": "deepagents",
            },
        )
    )
    db.commit()

    approved_plan_row = None
    if scope_control.get("require_plan_approval"):
        approved_plan_row = (
            db.query(Approval)
            .filter(
                Approval.run_id == run.id,
                Approval.approval_type == ApprovalType.GOVERNANCE,
                Approval.status.in_([ApprovalStatus.APPROVED, ApprovalStatus.OVERRIDDEN]),
            )
            .order_by(Approval.created_at.desc())
            .first()
        )
        approved_plan = extract_approved_plan(approved_plan_row.requested_payload_json if approved_plan_row else None)

    force_clean_repo = _run_has_completed_implementation(db, run.id) and _approved_plan_requires_continuation(approved_plan)

    # --- Step 1: Bootstrap sandbox ---
    try:
        env = _bootstrap_sandbox(db, run, project, force_clean_repo=force_clean_repo)
    except Exception as exc:
        run.status = RunStatus.FAILED
        run.final_summary = f"Sandbox bootstrap failed: {exc}"
        db.add(
            Event(
                id=_id("evt"),
                run_id=run.id,
                step_id=run.current_step_id,
                event_type="run.failed",
                payload_json={"error": str(exc), "phase": "sandbox_bootstrap"},
            )
        )
        db.commit()
        db.refresh(run)
        return run

    # --- Step 2: Resolve models ---
    models = _resolve_models(settings)
    orchestrator_model = models.get("orchestrator")
    if not orchestrator_model:
        run.status = RunStatus.FAILED
        run.final_summary = "No orchestrator model configured"
        db.commit()
        db.refresh(run)
        return run

    # --- Step 3: Create planning step and build agent ---
    planning_step = db.get(Step, run.current_step_id)
    if planning_step:
        planning_step.status = StepStatus.RUNNING
        planning_step.title = "DeepAgents orchestration"
        db.add(
            Event(
                id=_id("evt"),
                run_id=run.id,
                step_id=planning_step.id,
                event_type="step.started",
                payload_json={"title": "DeepAgents orchestration", "engine": "deepagents"},
            )
        )
        db.commit()

    sandbox = DockerSandbox.from_env(env)
    enable_hitl = should_interrupt_before_write(settings)

    try:
        agent, checkpointer, thread_id = build_deep_agent(
            orchestrator_model=orchestrator_model,
            planner_model=models.get("planner"),
            developer_model=models.get("developer"),
            reviewer_model=models.get("reviewer"),
            backend=sandbox,
            project_context=_implementation_project_context(project, env, scope_control, approved_plan),
            enable_hitl=enable_hitl,
        )
    except Exception as exc:
        run.status = RunStatus.FAILED
        run.final_summary = f"Failed to build DeepAgents orchestrator: {exc}"
        db.add(
            Event(
                id=_id("evt"),
                run_id=run.id,
                step_id=run.current_step_id,
                event_type="run.failed",
                payload_json={"error": str(exc), "phase": "agent_build"},
            )
        )
        db.commit()
        db.refresh(run)
        return run

    pending_plan_approval = None
    if scope_control.get("require_plan_approval"):
        pending_plan_approval = (
            db.query(Approval)
            .filter(
                Approval.run_id == run.id,
                Approval.approval_type == ApprovalType.GOVERNANCE,
                Approval.status == ApprovalStatus.PENDING,
            )
            .order_by(Approval.created_at.desc())
            .first()
        )

        if not approved_plan:
            plan, plan_enrichment = _build_plan_for_run(db, env, run.goal, settings)
            planning_step.output_json = {
                **plan,
                'enrichment': plan_enrichment,
            }
            planning_step.status = StepStatus.BLOCKED
            plan_path = _write_artifact_file(
                run.id,
                'implementation-plan.json',
                json.dumps(planning_step.output_json, indent=2, default=str),
            )
            _add_artifact(
                db,
                run,
                planning_step,
                ArtifactType.SUMMARY,
                'implementation-plan.json',
                plan_path,
                'Planner output awaiting approval',
            )
            if pending_plan_approval is None:
                approval = Approval(
                    id=_id("apr"),
                    run_id=run.id,
                    step_id=planning_step.id,
                    title="Approve implementation plan",
                    approval_type=ApprovalType.GOVERNANCE,
                    status=ApprovalStatus.PENDING,
                    requested_payload_json=build_plan_approval_payload(plan, scope_control, thread_id=thread_id if enable_hitl else None),
                )
                db.add(approval)
                approval_id = approval.id
            else:
                pending_plan_approval.requested_payload_json = build_plan_approval_payload(plan, scope_control, thread_id=thread_id if enable_hitl else None)
                approval_id = pending_plan_approval.id
            run.status = RunStatus.WAITING_FOR_HUMAN
            run.current_step_id = planning_step.id
            run.final_summary = "Awaiting plan approval before implementation"
            db.add(
                Event(
                    id=_id("evt"),
                    run_id=run.id,
                    step_id=planning_step.id,
                    event_type="run.blocked",
                    payload_json={
                        "reason": "plan_approval_required",
                        "approval_id": approval_id,
                        "scope_control": scope_control,
                        "planned_files": [target.get('path') for target in plan.get('targets', []) if target.get('path')],
                    },
                )
            )
            db.commit()
            db.refresh(run)
            return run

        if force_clean_repo:
            db.add(
                Event(
                    id=_id("evt"),
                    run_id=run.id,
                    step_id=planning_step.id,
                    event_type="sandbox.repo_reset",
                    payload_json={
                        "reason": "resume_from_approved_plan",
                        "approved_plan_mode": approved_plan.get('mode') if approved_plan else None,
                    },
                )
            )
            db.commit()

    if approved_plan and approved_plan.get('mode') == 'filesystem_cleanup':
        return _complete_filesystem_cleanup(db, run, planning_step, env, approved_plan)

    # --- Step 4: Invoke orchestrator ---
    implementation_step = Step(
        id=_id("step"),
        run_id=run.id,
        sequence_index=2,
        kind=StepKind.IMPLEMENTATION,
        role=AgentRole.DEVELOPER,
        title="DeepAgents implementation",
        status=StepStatus.RUNNING,
        input_json={
            "goal": run.goal,
            "models": {k: str(v) for k, v in role_model_configs.items()},
            "planned_files": [target.get('path') for target in (approved_plan or {}).get('targets', []) if target.get('path')],
            "approved_plan": approved_plan,
            "scope_control": scope_control,
        },
    )
    db.add(implementation_step)
    db.flush()
    db.add(
        Event(
            id=_id("evt"),
            run_id=run.id,
            step_id=implementation_step.id,
            event_type="step.started",
            payload_json={"title": "DeepAgents implementation"},
        )
    )
    db.commit()

    implementation_goal = run.goal
    if approved_plan and approved_plan.get('targets'):
        approved_targets = [target for target in approved_plan.get('targets', []) if target.get('path')]
        implementation_goal = (
            f"{run.goal}\n\n"
            "Only implement the approved plan below. Do not modify files outside these targets unless a human explicitly approves it.\n"
            f"Approved plan:\n{serialize_plan({'summary': approved_plan.get('summary'), 'targets': approved_targets, 'risks': approved_plan.get('risks', []), 'notes': approved_plan.get('notes', [])})}"
        )

    try:
        retry_settings = ((settings.get('autonomy') or {}).get('model_retries') or {})
        agent_result = _invoke_deep_agent_with_retries(
            agent=agent,
            goal=implementation_goal,
            test_command=project.test_command,
            inspect_command=project.inspect_command,
            thread_id=thread_id if enable_hitl else None,
            max_attempts=retry_settings.get('max_attempts', 3),
            base_delay_seconds=retry_settings.get('base_delay_seconds', 1.5),
            max_delay_seconds=retry_settings.get('max_delay_seconds', 10.0),
            jitter_ratio=retry_settings.get('jitter_ratio', 0.25),
        )
    except Exception as exc:
        logger.exception("DeepAgents invocation failed for run %s", run_id)
        implementation_step.status = StepStatus.FAILED
        implementation_step.error_summary = str(exc)[:500]
        run.status = RunStatus.FAILED
        run.final_summary = f"DeepAgents execution failed: {str(exc)[:300]}"
        db.add(
            Event(
                id=_id("evt"),
                run_id=run.id,
                step_id=implementation_step.id,
                event_type="run.failed",
                payload_json={"error": str(exc)[:500], "phase": "agent_invocation"},
            )
        )
        db.commit()
        db.refresh(run)
        return run

    # --- Step 4b: Handle HITL interrupt ---
    if agent_result.get("status") == "interrupted":
        pending = agent_result.get("pending_tool_calls", [])
        implementation_step.status = StepStatus.BLOCKED
        implementation_step.output_json = {
            "interrupted": True,
            "pending_tool_calls": pending,
            "thread_id": thread_id,
        }
        approval = Approval(
            id=_id("apr"),
            run_id=run.id,
            step_id=implementation_step.id,
            title=f"Approve file operations ({len(pending)} pending)",
            approval_type=ApprovalType.EDIT_PROPOSAL,
            status=ApprovalStatus.PENDING,
            requested_payload_json={
                "pending_tool_calls": pending,
                "thread_id": thread_id,
                "hitl": True,
            },
        )
        db.add(approval)
        run.status = RunStatus.WAITING_FOR_HUMAN
        run.current_step_id = implementation_step.id
        run.final_summary = f"Awaiting approval for {len(pending)} file operation(s)"
        db.add(
            Event(
                id=_id("evt"),
                run_id=run.id,
                step_id=implementation_step.id,
                event_type="run.blocked",
                payload_json={
                    "reason": "hitl_interrupt",
                    "pending_tool_calls": pending,
                    "approval_id": approval.id,
                },
            )
        )
        db.commit()
        db.refresh(run)
        return run

    # --- Step 5: Persist results ---
    implementation_step.output_json = agent_result
    implementation_step.status = (
        StepStatus.COMPLETED
        if agent_result.get("status") != "failed"
        else StepStatus.FAILED
    )
    implementation_step.error_summary = (
        "; ".join(agent_result.get("blocking_issues", []))[:500]
        if agent_result.get("blocking_issues")
        else None
    )

    # Save orchestrator result as artifact
    result_path = _write_artifact_file(
        run.id,
        "deepagents-result.json",
        json.dumps(agent_result, indent=2, default=str),
    )
    _add_artifact(
        db,
        run,
        implementation_step,
        ArtifactType.SUMMARY,
        "deepagents-result.json",
        result_path,
        f"DeepAgents orchestration result (confidence: {agent_result.get('confidence', 'N/A')})",
    )

    # Save git diff as artifact
    diff_result = exec_in_container(env, f"cd {env.repo_dir} && git diff -- .")
    diff_content = diff_result.get("stdout") or diff_result.get("stderr") or ""
    if diff_content.strip():
        diff_path = _write_artifact_file(run.id, "git.diff", diff_content)
        _add_artifact(
            db, run, implementation_step, ArtifactType.DIFF, "git.diff", diff_path,
            "Repository diff after DeepAgents execution",
        )

    # Save plan summary if available
    if agent_result.get("plan_summary"):
        plan_path = _write_artifact_file(
            run.id, "plan-summary.txt", agent_result["plan_summary"]
        )
        _add_artifact(
            db, run, implementation_step, ArtifactType.SUMMARY, "plan-summary.txt",
            plan_path, "Plan summary from DeepAgents orchestrator",
        )

    # --- Step 6: Review step ---
    review_step = Step(
        id=_id("step"),
        run_id=run.id,
        sequence_index=3,
        kind=StepKind.REVIEW,
        role=AgentRole.REVIEWER,
        title="DeepAgents review",
        status=StepStatus.COMPLETED,
        input_json={"agent_result_status": agent_result.get("status")},
        output_json={
            "decision": agent_result.get("review_decision", "none"),
            "confidence": agent_result.get("confidence", 0.0),
            "summary": agent_result.get("review_summary", ""),
            "blocking_issues": agent_result.get("blocking_issues", []),
        },
    )
    db.add(review_step)
    db.flush()

    # --- Step 7: Autonomy routing ---
    files_changed = classify_changed_files(agent_result.get("files_changed", []))
    planned_files = classify_changed_files((implementation_step.input_json or {}).get("planned_files", []))
    scope_guard = scope_guard_decision(
        planned_files=planned_files,
        changed_files=files_changed,
        scope_control=scope_control,
    )
    auto_approve = _should_auto_approve(settings, agent_result, scope_guard=scope_guard)

    if agent_result.get("status") == "failed":
        # Agent reported failure
        run.status = RunStatus.FAILED
        run.final_summary = agent_result.get("review_summary") or "DeepAgents execution failed"
        db.add(
            Event(
                id=_id("evt"),
                run_id=run.id,
                step_id=review_step.id,
                event_type="run.failed",
                payload_json={"reason": "agent_failure", "result": agent_result},
            )
        )
    elif not files_changed and not diff_content.strip():
        # No changes made
        run.status = RunStatus.COMPLETED
        run.final_summary = agent_result.get("plan_summary") or "No file changes needed"
        db.add(
            Event(
                id=_id("evt"),
                run_id=run.id,
                step_id=review_step.id,
                event_type="run.completed",
                payload_json={"reason": "no_changes", "result": agent_result},
            )
        )
    elif auto_approve:
        # High confidence + reviewer approved → implementation complete, awaiting publish/PR
        run.status = RunStatus.WAITING_FOR_HUMAN
        run.final_summary = (
            f"Ready to publish: {len(files_changed)} file(s) changed "
            f"(confidence: {agent_result.get('confidence', 0.0):.0%})"
        )
        db.add(
            Event(
                id=_id("evt"),
                run_id=run.id,
                step_id=review_step.id,
                event_type="run.awaiting_pull_request",
                payload_json={
                    "reason": "auto_approved_waiting_for_pr",
                    "confidence": agent_result.get("confidence"),
                    "files_changed": files_changed,
                    "scope_guard": scope_guard,
                },
            )
        )
    else:
        # Below threshold or reviewer requested changes → human approval
        approval = Approval(
            id=_id("apr"),
            run_id=run.id,
            step_id=review_step.id,
            title=f"Review DeepAgents changes ({len(files_changed)} file(s))",
            approval_type=ApprovalType.GOVERNANCE,
            status=ApprovalStatus.PENDING,
            requested_payload_json=build_review_approval_payload(
                agent_result=agent_result,
                diff=diff_content,
                files_changed=files_changed,
                scope_guard=scope_guard,
                scope_control=scope_control,
            ),
        )
        db.add(approval)
        run.status = RunStatus.WAITING_FOR_HUMAN
        run.final_summary = (
            f"Awaiting human review: {len(files_changed)} file(s) changed "
            f"(confidence: {agent_result.get('confidence', 0.0):.0%})"
        )
        db.add(
            Event(
                id=_id("evt"),
                run_id=run.id,
                step_id=review_step.id,
                event_type="run.blocked",
                payload_json={
                    "reason": "human_review_required",
                    "confidence": agent_result.get("confidence"),
                    "blocking_issues": agent_result.get("blocking_issues", []),
                    "approval_id": approval.id,
                    "scope_guard": scope_guard,
                },
            )
        )

    run.current_step_id = review_step.id
    db.commit()
    db.refresh(run)
    return run
