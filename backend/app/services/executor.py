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
    get_scope_control,
    scope_guard_decision,
    should_interrupt_before_write,
)
from app.services.context_manager import resolve_langchain_model
from app.services.deepagents_fs import DockerSandbox
from app.services.planning import build_initial_plan, collect_repo_files, enrich_plan_if_possible
from app.services.docker_runner import (
    bootstrap_repo_in_container,
    create_container,
    ensure_docker_environment,
    exec_in_container,
)
from app.services.runs import _id
from app.services.settings import get_settings, resolve_role_model

logger = logging.getLogger(__name__)

ARTIFACT_BASE = Path("/home/ethanturk/.openclaw/workspace/coding-agent/runtime_artifacts")


def _find_pending_plan_approval(db: Session, run_id: str) -> Approval | None:
    return (
        db.query(Approval)
        .filter(Approval.run_id == run_id, Approval.status == ApprovalStatus.APPROVED)
        .order_by(Approval.created_at.desc())
        .first()
    )


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


def _bootstrap_sandbox(db: Session, run: Run, project: Project):
    """Create and initialize Docker sandbox for a run."""
    env = ensure_docker_environment(db, run, project)
    env = create_container(db, env)
    bootstrap = bootstrap_repo_in_container(db, env, project)
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


def _build_plan_for_run(db: Session, env, goal: str) -> tuple[dict, dict]:
    repo_result = exec_in_container(env, f"cd {env.repo_dir} && git ls-files")
    if not repo_result.get('ok'):
        raise ValueError(repo_result.get('stderr') or 'Failed to inspect repository files for planning')
    repo_files = collect_repo_files(repo_result.get('stdout') or '')
    draft_plan = build_initial_plan(goal, repo_files)
    enriched = enrich_plan_if_possible(db, goal, repo_files, draft_plan)
    return enriched['plan'], enriched.get('enrichment') or {'used': False, 'reason': 'not_available'}


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

    # --- Step 1: Bootstrap sandbox ---
    try:
        env = _bootstrap_sandbox(db, run, project)
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

    enable_hitl = should_interrupt_before_write(settings)

    try:
        agent, checkpointer, thread_id = build_deep_agent(
            orchestrator_model=orchestrator_model,
            planner_model=models.get("planner"),
            developer_model=models.get("developer"),
            reviewer_model=models.get("reviewer"),
            backend=sandbox,
            project_context="\n".join(project_context_parts),
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
        approved_plan = (
            db.query(Approval)
            .filter(
                Approval.run_id == run.id,
                Approval.approval_type == ApprovalType.GOVERNANCE,
                Approval.status == ApprovalStatus.APPROVED,
            )
            .order_by(Approval.created_at.desc())
            .first()
        )
        if approved_plan and (approved_plan.requested_payload_json or {}).get('kind') == 'plan':
            approved_plan = approved_plan.requested_payload_json.get('plan')
        else:
            approved_plan = None

        if not approved_plan:
            plan, plan_enrichment = _build_plan_for_run(db, env, run.goal)
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

    try:
        agent_result = invoke_deep_agent(
            agent,
            goal=run.goal,
            test_command=project.test_command,
            inspect_command=project.inspect_command,
            thread_id=thread_id if enable_hitl else None,
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
        # High confidence + reviewer approved → auto-complete
        run.status = RunStatus.COMPLETED
        run.final_summary = (
            f"Auto-approved: {len(files_changed)} file(s) changed "
            f"(confidence: {agent_result.get('confidence', 0.0):.0%})"
        )
        db.add(
            Event(
                id=_id("evt"),
                run_id=run.id,
                step_id=review_step.id,
                event_type="run.completed",
                payload_json={
                    "reason": "auto_approved",
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
