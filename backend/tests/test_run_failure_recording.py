from types import SimpleNamespace

from app.api import runs as runs_api
from app.models.enums import RunStatus


class FakeDb:
    def __init__(self, run):
        self._run = run
        self.added = []
        self.rollback_called = False
        self.commit_called = False
        self.refresh_called = False

    def rollback(self):
        self.rollback_called = True

    def add(self, obj):
        self.added.append(obj)

    def commit(self):
        self.commit_called = True

    def refresh(self, run):
        self.refresh_called = True


def test_record_run_failure_rolls_back_then_records(monkeypatch):
    run = SimpleNamespace(id='run_1', current_step_id='step_1', status=RunStatus.RUNNING, final_summary=None)
    db = FakeDb(run)

    monkeypatch.setattr(runs_api, 'get_run', lambda db_obj, run_id: run)

    runs_api._record_run_failure(db, run, RuntimeError('boom'))

    assert db.rollback_called is True
    assert db.commit_called is True
    assert db.refresh_called is True
    assert run.status == RunStatus.FAILED
    assert run.final_summary == 'boom'
    assert len(db.added) == 1
    assert db.added[0].event_type == 'run.failed'
