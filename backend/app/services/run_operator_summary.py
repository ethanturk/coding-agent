import json
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Artifact, ExecutionEnvironment, Project, PullRequest, Run
from app.models.enums import PullRequestStatus, RunStatus, StepStatus
from app.schemas.run_operator_summary import (
    DiffStats,
    FileActionValidation,
    PlannedActionCounts,
    PlannedActionSummary,
    RunFileAction,
    RunListOperatorSummary,
    RunOperatorSummary,
    RunPrState,
    RunPrStateSummary,
    RunValidationStateSummary,
    RunValidationSummary,
    ValidationCheckSummary,
)


_VALIDATION_STEP_MAP = {
    'Run smoke test command': 'test',
    'Run build command': 'build',
    'Run lint command': 'lint',
}


def build_run_operator_summary(db: Session, run: Run) -> RunOperatorSummary:
    project = db.get(Project, run.project_id)
    artifacts = list(
        db.scalars(
            select(Artifact).where(Artifact.run_id == run.id).order_by(Artifact.created_at.asc())
        )
    )
    env = (
        db.query(ExecutionEnvironment)
        .filter(ExecutionEnvironment.run_id == run.id)
        .order_by(ExecutionEnvironment.created_at.desc())
        .first()
    )
    pr = (
        db.query(PullRequest)
        .filter(PullRequest.run_id == run.id)
        .order_by(PullRequest.created_at.desc())
        .first()
    )

    file_actions = _derive_file_actions(artifacts)
    validation = _derive_validation(run)
    pr_state = _derive_pr_state(project, env, pr, run)
    stage = _derive_stage(run, pr_state)

    return RunOperatorSummary(
        stage=stage,
        file_actions=file_actions,
        validation=validation,
        pr=pr_state,
    )


def build_run_list_operator_summary(db: Session, run: Run) -> RunListOperatorSummary:
    detail = build_run_operator_summary(db, run)
    counts = PlannedActionCounts()
    for action in detail.file_actions:
        key = action.action.replace('-', '_')
        if hasattr(counts, key):
            setattr(counts, key, getattr(counts, key) + 1)

    highlights = [action.path for action in detail.file_actions[:2]]

    return RunListOperatorSummary(
        stage=detail.stage,
        planned_action_summary=PlannedActionSummary(
            total_files=len(detail.file_actions),
            counts=counts,
            highlights=highlights,
        ),
        validation_summary=RunValidationStateSummary(
            test=detail.validation.test.state,
            build=detail.validation.build.state,
            lint=detail.validation.lint.state,
        ),
        pr_summary=RunPrStateSummary(
            status=detail.pr.status,
            pr_number=detail.pr.pr_number,
            pr_url=detail.pr.pr_url,
        ),
    )


def _read_json_artifact(artifacts: list[Artifact], name: str) -> Any | None:
    artifact = next((item for item in artifacts if item.name == name), None)
    if not artifact or not artifact.storage_uri:
        return None
    path = Path(artifact.storage_uri)
    if not path.exists() or not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding='utf-8'))
    except Exception:
        return None


def _derive_file_actions(artifacts: list[Artifact]) -> list[RunFileAction]:
    edit_plan = _read_json_artifact(artifacts, 'developer-edit-plan.json') or {}
    edit_candidates = _read_json_artifact(artifacts, 'developer-edit-candidates.json') or []
    proposals = _read_json_artifact(artifacts, 'developer-proposals.json') or []

    candidates_by_path = {
        item.get('path'): item
        for item in edit_candidates
        if isinstance(item, dict) and item.get('path')
    }

    proposals_by_path = {
        item.get('path'): item
        for item in proposals
        if isinstance(item, dict) and item.get('path')
    }

    actions: list[RunFileAction] = []
    seen: set[str] = set()

    for entry in edit_plan.get('targets', []) or []:
        if not isinstance(entry, dict):
            continue
        path = entry.get('path')
        if not path:
            continue
        candidate = candidates_by_path.get(path) or {}
        proposal = proposals_by_path.get(path) or {}
        diff_stats = _extract_diff_stats(candidate)
        validation = _extract_validation(candidate)
        action_status = 'applied' if proposal.get('changed') else 'pending'
        actions.append(
            RunFileAction(
                path=path,
                action=_normalize_action(entry.get('change_type')),
                phase='edited' if proposal.get('changed') else 'planned',
                status=action_status,
                intent=entry.get('intent') or _fallback_intent(entry.get('change_type')),
                rationale=entry.get('rationale'),
                confidence=_score_to_confidence(candidate),
                source='edit_plan',
                diff_stats=diff_stats,
                validation=validation,
            )
        )
        seen.add(path)

    for path, candidate in candidates_by_path.items():
        if not path or path in seen:
            continue
        compiled = ((candidate.get('llm_candidate') or {}).get('compiled') or {})
        deterministic = candidate.get('deterministic_candidate') or {}
        template_candidate = candidate.get('template_candidate') or {}
        intent = (
            compiled.get('intent')
            or deterministic.get('intent')
            or template_candidate.get('intent')
            or 'review file relevance and potential changes'
        )
        rationale = (
            compiled.get('reason')
            or deterministic.get('reason')
            or template_candidate.get('reason')
        )
        actions.append(
            RunFileAction(
                path=path,
                action=_normalize_action(compiled.get('change_type') or deterministic.get('change_type') or template_candidate.get('change_type')),
                phase='planned',
                status='pending',
                intent=intent,
                rationale=rationale,
                confidence=_score_to_confidence(candidate),
                source='edit_candidates',
                diff_stats=_extract_diff_stats(candidate),
                validation=_extract_validation(candidate),
            )
        )

    for path, proposal in proposals_by_path.items():
        if path in seen:
            continue
        actions.append(
            RunFileAction(
                path=path,
                action=_normalize_action(proposal.get('change_type')),
                phase='edited' if proposal.get('changed') else 'planned',
                status='applied' if proposal.get('changed') else 'pending',
                intent=proposal.get('intent') or _fallback_intent(proposal.get('change_type')),
                rationale=proposal.get('reason'),
                confidence=None,
                source='derived',
                diff_stats=_derive_diff_stats_from_patch(str(proposal.get('diff_preview') or '')),
                validation=None,
            )
        )

    return sorted(actions, key=lambda item: item.path)


def _extract_diff_stats(candidate: dict[str, Any]) -> DiffStats | None:
    stats = candidate.get('diff_stats')
    if not isinstance(stats, dict):
        proposal_diff = candidate.get('diff_preview') or candidate.get('diff')
        if isinstance(proposal_diff, str) and proposal_diff.strip():
            return _derive_diff_stats_from_patch(proposal_diff)
        return None
    additions = int(stats.get('additions') or 0)
    deletions = int(stats.get('deletions') or 0)
    return DiffStats(additions=additions, deletions=deletions)


def _derive_diff_stats_from_patch(diff_text: str) -> DiffStats | None:
    additions = 0
    deletions = 0
    for line in diff_text.splitlines():
        if line.startswith('+++') or line.startswith('---'):
            continue
        if line.startswith('+'):
            additions += 1
        elif line.startswith('-'):
            deletions += 1
    if additions == 0 and deletions == 0:
        return None
    return DiffStats(additions=additions, deletions=deletions)


def _extract_validation(candidate: dict[str, Any]) -> FileActionValidation | None:
    validation = candidate.get('validation')
    if not isinstance(validation, dict):
        return None
    return FileActionValidation(
        touched_by_test=bool(validation.get('touched_by_test')),
        touched_by_build=bool(validation.get('touched_by_build')),
        touched_by_lint=bool(validation.get('touched_by_lint')),
    )


def _score_to_confidence(candidate: dict[str, Any]) -> str | None:
    scores = candidate.get('scores') or {}
    numeric_scores = [value for value in scores.values() if isinstance(value, (int, float))]
    if not numeric_scores:
        return None
    score = max(numeric_scores)
    if score >= 0.8:
        return 'high'
    if score >= 0.5:
        return 'medium'
    return 'low'


def _fallback_intent(change_type: str | None) -> str:
    action = _normalize_action(change_type)
    return {
        'create': 'create a new file needed for the solution',
        'delete': 'remove a file that is no longer needed',
        'rename': 'rename or move the file as part of the change',
        'review-only': 'review file relevance without direct edits',
    }.get(action, 'modify the file to support the requested change')


def _normalize_action(change_type: str | None) -> str:
    value = (change_type or 'modify').strip().lower().replace('_', '-').replace(' ', '-')
    if value in {'new', 'add'}:
        return 'create'
    if value in {'remove'}:
        return 'delete'
    if value in {'move'}:
        return 'rename'
    if value in {'review', 'reviewonly', 'review-only'}:
        return 'review-only'
    if value not in {'create', 'modify', 'delete', 'rename', 'review-only'}:
        return 'modify'
    return value


def _derive_validation(run: Run) -> RunValidationSummary:
    checks = {
        'test': ValidationCheckSummary(state='not_run', summary=None),
        'build': ValidationCheckSummary(state='not_run', summary=None),
        'lint': ValidationCheckSummary(state='not_run', summary=None),
    }

    for step in run.steps:
        bucket = _VALIDATION_STEP_MAP.get(step.title)
        if not bucket:
            continue
        checks[bucket] = ValidationCheckSummary(
            state=_step_status_to_validation_state(step.status, step.error_summary, step.output_json),
            summary=_step_summary(step.output_json, step.error_summary),
        )

    return RunValidationSummary(**checks)


def _step_status_to_validation_state(status: StepStatus, error_summary: str | None, output_json: dict | None) -> str:
    if status == StepStatus.FAILED or error_summary:
        return 'failed'
    if status == StepStatus.COMPLETED:
        if isinstance(output_json, dict):
            stderr = str(output_json.get('stderr') or '').strip()
            stdout = str(output_json.get('stdout') or '').strip()
            if stderr and not stdout:
                return 'warning'
        return 'passed'
    if status in {StepStatus.RUNNING, StepStatus.QUEUED}:
        return 'not_run'
    return 'warning'


def _step_summary(output_json: dict | None, error_summary: str | None) -> str | None:
    if error_summary:
        return error_summary
    if not isinstance(output_json, dict):
        return None
    for key in ('summary', 'stderr', 'stdout'):
        value = output_json.get(key)
        if value:
            return str(value)
    return None


def _derive_pr_state(project: Project | None, env: ExecutionEnvironment | None, pr: PullRequest | None, run: Run) -> RunPrState:
    if pr:
        pr_title = None
        if pr.pr_number:
            pr_title = f'PR #{pr.pr_number}'
        status = _normalize_pr_status(pr.status)
        review_state = 'approved' if status == 'merged' else 'pending'
        return RunPrState(
            branch_name=pr.branch_name or getattr(env, 'branch_name', None),
            branch_url=None,
            base_branch=project.default_branch if project else None,
            head_sha=None,
            pr_number=pr.pr_number,
            pr_title=pr_title,
            pr_url=pr.pr_url,
            status=status,
            review_state=review_state,
            mergeable=True if status == 'open' else None,
            merge_commit_sha=pr.merge_commit_sha,
            provider=pr.provider,
        )

    if env and env.branch_name:
        return RunPrState(
            branch_name=env.branch_name,
            branch_url=None,
            base_branch=project.default_branch if project else None,
            head_sha=None,
            pr_number=None,
            pr_title=None,
            pr_url=None,
            status='not_created',
            review_state='pending' if run.status == RunStatus.WAITING_FOR_HUMAN else 'unknown',
            mergeable=None,
            merge_commit_sha=None,
            provider='github',
        )

    return RunPrState(status='not_created', provider='github')


def _normalize_pr_status(status: PullRequestStatus | str | None) -> str:
    if status == PullRequestStatus.MERGED or status == 'merged':
        return 'merged'
    if status == PullRequestStatus.CLOSED or status == 'closed':
        return 'closed'
    return 'open'


def _derive_stage(run: Run, pr_state: RunPrState) -> str:
    if run.status == RunStatus.COMPLETED:
        return 'complete'
    if run.status == RunStatus.FAILED:
        return 'failed'
    if run.status == RunStatus.CANCELLED:
        return 'cancelled'
    if pr_state.status == 'merged':
        return 'complete'
    if pr_state.status == 'open':
        return 'approve'
    if pr_state.branch_name:
        return 'publish'
    if any(step.title in _VALIDATION_STEP_MAP for step in run.steps):
        return 'validate'
    if any(step.status in {StepStatus.RUNNING, StepStatus.COMPLETED, StepStatus.WAITING_FOR_HUMAN} for step in run.steps if step.title not in _VALIDATION_STEP_MAP):
        return 'edit'
    return 'plan'
