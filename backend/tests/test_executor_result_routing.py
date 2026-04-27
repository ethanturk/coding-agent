from types import SimpleNamespace

from app.models.enums import AgentRole, RunStatus, StepKind, StepStatus
from app.services import executor as executor_api


def test_no_change_result_with_blocking_issues_requires_human_review(monkeypatch):
    review_step = SimpleNamespace(id='step_review')
    run = SimpleNamespace(status=RunStatus.RUNNING, final_summary=None, id='run_1')
    events = []

    class DummyEvent:
        def __init__(self, **kwargs):
            events.append(kwargs)

    monkeypatch.setattr(executor_api, 'Event', DummyEvent)
    monkeypatch.setattr(executor_api, '_id', lambda prefix: f'{prefix}_1')

    agent_result = {
        'status': 'needs_human_review',
        'files_changed': [],
        'blocking_issues': ['approved scope missing real implementation files'],
        'review_decision': 'approve',
        'plan_summary': 'Could not safely proceed within approved scope.',
        'confidence': 0.85,
    }

    files_changed = executor_api.classify_changed_files(agent_result.get('files_changed', []))
    planned_files = executor_api.classify_changed_files([])
    scope_guard = executor_api.scope_guard_decision(
        planned_files=planned_files,
        changed_files=files_changed,
        scope_control={'max_files_changed': 3, 'allow_path_expansion': False},
    )
    auto_approve = executor_api._should_auto_approve({'autonomy': {'auto_approve_threshold': 0.8}}, agent_result, scope_guard=scope_guard)
    blocking_issues = agent_result.get('blocking_issues', [])
    requires_human_review = (
        agent_result.get('status') == 'needs_human_review'
        or bool(blocking_issues)
        or agent_result.get('review_decision') == 'request_changes'
    )

    assert auto_approve is False
    assert requires_human_review is True
