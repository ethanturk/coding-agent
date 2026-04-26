from datetime import datetime, timezone
from types import SimpleNamespace

from fastapi import HTTPException

from app.api import approvals as approvals_api
from app.models.enums import ApprovalStatus, RunStatus


class FakeQuery:
    def __init__(self, approvals):
        self._approvals = approvals

    def filter(self, *args, **kwargs):
        return self

    def all(self):
        return list(self._approvals)


class FakeDb:
    def __init__(self, approval, run):
        self._approval = approval
        self._run = run
        self._approvals = [approval] if approval else []
        self.events = []
        self.committed = False

    def get(self, model, key):
        name = getattr(model, '__name__', '')
        if name == 'Approval':
            return self._approval
        if name == 'Run':
            return self._run
        return None

    def query(self, model):
        return FakeQuery(self._approvals)

    def add(self, obj):
        self.events.append(obj)

    def commit(self):
        self.committed = True


def test_override_block_marks_approval_overridden_and_resumes(monkeypatch):
    approval = SimpleNamespace(
        id='apr_1',
        run_id='run_1',
        requested_payload_json={'kind': 'plan', 'override_block_allowed': True},
        response_payload_json=None,
        status=ApprovalStatus.PENDING,
        created_at=datetime.now(timezone.utc),
    )
    run = SimpleNamespace(id='run_1', current_step_id='step_1', status=RunStatus.WAITING_FOR_HUMAN, final_summary='waiting')
    db = FakeDb(approval, run)

    started = []

    class FakeThread:
        def __init__(self, target=None, args=(), daemon=None):
            started.append({'target': target, 'args': args, 'daemon': daemon})

        def start(self):
            started[-1]['started'] = True

    monkeypatch.setattr(approvals_api.threading, 'Thread', FakeThread)

    result = approvals_api.override_block('apr_1', db)

    assert approval.status == ApprovalStatus.OVERRIDDEN
    assert approval.response_payload_json == {'override_block': True}
    assert run.status == RunStatus.QUEUED
    assert run.final_summary == 'Human override accepted, run resumed'
    assert db.committed is True
    assert result['override_block'] is True
    assert started and started[0]['args'] == ('run_1',)


def test_override_block_rejects_when_not_allowed():
    approval = SimpleNamespace(
        id='apr_2',
        run_id='run_2',
        requested_payload_json={'kind': 'other', 'override_block_allowed': False},
        response_payload_json=None,
        status=ApprovalStatus.PENDING,
        created_at=datetime.now(timezone.utc),
    )
    db = FakeDb(approval, None)

    try:
        approvals_api.override_block('apr_2', db)
    except HTTPException as exc:
        assert exc.status_code == 400
        assert exc.detail == 'Override is not allowed for this approval'
    else:
        raise AssertionError('Expected HTTPException for disallowed override')


def test_list_approvals_backfills_override_for_pending_plan_and_review():
    plan = SimpleNamespace(
        id='apr_plan',
        run_id='run_3',
        step_id='step_1',
        title='Approve implementation plan',
        approval_type='governance',
        status=ApprovalStatus.PENDING,
        requested_payload_json={'kind': 'plan'},
        created_at=datetime(2026, 4, 26, 15, 0, tzinfo=timezone.utc),
    )
    review = SimpleNamespace(
        id='apr_review',
        run_id='run_3',
        step_id='step_2',
        title='Review changes',
        approval_type='governance',
        status=ApprovalStatus.PENDING,
        requested_payload_json={'kind': 'review'},
        created_at=datetime(2026, 4, 26, 15, 5, tzinfo=timezone.utc),
    )
    db = FakeDb(plan, None)
    db._approvals = [plan, review]

    approvals = approvals_api.list_approvals('run_3', db)

    assert approvals[0]['requested_payload_json']['override_block_allowed'] is True
    assert approvals[1]['requested_payload_json']['override_block_allowed'] is True
    assert approvals[0]['created_at'] == plan.created_at
    assert approvals[1]['created_at'] == review.created_at
    assert plan.requested_payload_json['override_block_allowed'] is True
    assert review.requested_payload_json['override_block_allowed'] is True
    assert db.committed is True
