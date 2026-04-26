from __future__ import annotations

from typing import Any

from app.models.enums import ApprovalType


DEFAULT_SCOPE_CONTROL = {
    'require_plan_approval': True,
    'interrupt_before_write': True,
    'max_files_changed': 3,
    'max_parallel_developer_tasks': 1,
    'allow_path_expansion': False,
}


def get_scope_control(settings: dict | None) -> dict:
    settings = settings or {}
    autonomy = settings.get('autonomy', {}) or {}
    scope = autonomy.get('scope_control', {}) or {}
    merged = {**DEFAULT_SCOPE_CONTROL, **scope}
    merged['max_files_changed'] = max(1, int(merged.get('max_files_changed', DEFAULT_SCOPE_CONTROL['max_files_changed']) or 1))
    merged['max_parallel_developer_tasks'] = max(1, int(merged.get('max_parallel_developer_tasks', DEFAULT_SCOPE_CONTROL['max_parallel_developer_tasks']) or 1))
    merged['require_plan_approval'] = bool(merged.get('require_plan_approval', True))
    merged['interrupt_before_write'] = bool(merged.get('interrupt_before_write', True))
    merged['allow_path_expansion'] = bool(merged.get('allow_path_expansion', False))
    return merged


def should_interrupt_before_write(settings: dict | None) -> bool:
    return bool(get_scope_control(settings).get('interrupt_before_write'))


def build_plan_approval_payload(plan: dict[str, Any], scope_control: dict[str, Any], *, thread_id: str | None = None) -> dict[str, Any]:
    targets = plan.get('targets') or []
    files = [target.get('path') for target in targets if target.get('path')]
    operations = plan.get('operations') or []
    is_cleanup = plan.get('mode') == 'filesystem_cleanup'
    cleanup_paths = [op.get('path') for op in operations if op.get('path')]
    return {
        'kind': 'plan',
        'summary': {
            'text': plan.get('summary') or 'Approve implementation plan',
            'files': cleanup_paths if is_cleanup else files,
            'target_count': len(cleanup_paths if is_cleanup else files),
            'risks': plan.get('risks') or [],
        },
        'plan': plan,
        'scope_control': scope_control,
        'files_changed': files,
        'thread_id': thread_id,
        'mode': plan.get('mode', 'code_edit'),
        'operations': operations,
        'override_block_allowed': True,
    }


def classify_changed_files(files_changed: list[Any]) -> list[str]:
    normalized: list[str] = []
    for item in files_changed or []:
        if isinstance(item, str):
            path = item
        elif isinstance(item, dict):
            path = item.get('path')
        else:
            path = None
        if path and path not in normalized:
            normalized.append(path)
    return normalized


def extract_approved_plan(approval_payload: dict[str, Any] | None) -> dict[str, Any] | None:
    payload = approval_payload or {}
    if payload.get('kind') != 'plan' and not payload.get('override_block'):
        return None
    plan = payload.get('plan')
    if not isinstance(plan, dict):
        return None
    return plan


def scope_guard_decision(*, planned_files: list[str], changed_files: list[str], scope_control: dict[str, Any]) -> dict[str, Any]:
    planned = [path for path in planned_files if path]
    changed = [path for path in changed_files if path]
    over_budget = len(changed) > scope_control['max_files_changed']
    extra_files = [path for path in changed if path not in planned]
    path_expansion = bool(extra_files) and not scope_control['allow_path_expansion']
    requires_review = over_budget or path_expansion
    reasons: list[str] = []
    if over_budget:
        reasons.append('file_budget_exceeded')
    if path_expansion:
        reasons.append('unplanned_files_changed')
    return {
        'requires_human_review': requires_review,
        'reasons': reasons,
        'extra_files': extra_files,
        'planned_files': planned,
        'changed_files': changed,
    }


def build_review_approval_payload(*, agent_result: dict[str, Any], diff: str, files_changed: list[str], scope_guard: dict[str, Any], scope_control: dict[str, Any]) -> dict[str, Any]:
    return {
        'kind': 'review',
        'agent_result': agent_result,
        'diff': diff[:50000],
        'files_changed': files_changed,
        'scope_guard': scope_guard,
        'scope_control': scope_control,
        'override_block_allowed': True,
        'summary': {
            'text': agent_result.get('review_summary') or 'Review DeepAgents changes',
            'files': files_changed,
            'reason': ', '.join(scope_guard.get('reasons') or []) or None,
        },
    }


def approval_type_for_payload(payload: dict[str, Any] | None) -> ApprovalType:
    kind = (payload or {}).get('kind')
    if kind in {'plan', 'review'}:
        return ApprovalType.GOVERNANCE
    return ApprovalType.EDIT_PROPOSAL
