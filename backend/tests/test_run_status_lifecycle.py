from types import SimpleNamespace

from app.models.enums import PullRequestStatus, RunStatus, StepStatus
from app.services.run_operator_summary import _derive_stage


def test_completed_run_stays_complete():
    run = SimpleNamespace(status=RunStatus.COMPLETED, steps=[])
    pr_state = SimpleNamespace(status='open', branch_name='feature/test')
    assert _derive_stage(run, pr_state) == 'complete'


def test_waiting_run_with_branch_is_publish_stage():
    run = SimpleNamespace(status=RunStatus.WAITING_FOR_HUMAN, steps=[])
    pr_state = SimpleNamespace(status='not_created', branch_name='agent-platform/run_123')
    assert _derive_stage(run, pr_state) == 'publish'


def test_waiting_run_with_open_pr_is_approve_stage():
    run = SimpleNamespace(status=RunStatus.WAITING_FOR_HUMAN, steps=[])
    pr_state = SimpleNamespace(status='open', branch_name='agent-platform/run_123')
    assert _derive_stage(run, pr_state) == 'approve'


def test_waiting_run_without_branch_falls_back_to_plan():
    run = SimpleNamespace(status=RunStatus.WAITING_FOR_HUMAN, steps=[])
    pr_state = SimpleNamespace(status='not_created', branch_name=None)
    assert _derive_stage(run, pr_state) == 'plan'
