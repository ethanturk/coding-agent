from types import SimpleNamespace

from fastapi import HTTPException

from app.api import approvals as approvals_api
from app.models.enums import ApprovalStatus, RunStatus


class FakeDb:
    def __init__(self, approval, run):
        self._approval = approval
        self._run = run
        self.events = []
        self.committed = False

    def get(self, model, key):
        name = getattr(model, '__name__', '')
        if name == 'Approval':
            return self._approval
        if name == 'Run':
            return self._run
        return None

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
        requested_payload_json={'kind': 'review', 'override_block_allowed': False},
        response_payload_json=None,
        status=ApprovalStatus.PENDING,
    )
    db = FakeDb(approval, None)

    try:
        approvals_api.override_block('apr_2', db)
    except HTTPException as exc:
        assert exc.status_code == 400
        assert exc.detail == 'Override is not allowed for this approval'
    else:
        raise AssertionError('Expected HTTPException for disallowed override')
