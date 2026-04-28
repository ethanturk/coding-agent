from types import SimpleNamespace

from app.models.enums import RunStatus, StepKind, StepStatus
from app.services import executor as executor_api


class FakeQuery:
    def __init__(self, result=None):
        self._result = result

    def filter(self, *args, **kwargs):
        return self

    def first(self):
        return self._result


class FakeDb:
    def __init__(self, run, planning_step):
        self.run = run
        self.planning_step = planning_step
        self.added = []
        self._steps = []

    def add(self, obj):
        self.added.append(obj)
        if getattr(obj, 'kind', None):
            self._steps.append(obj)

    def flush(self):
        return None

    def commit(self):
        return None

    def refresh(self, obj):
        return None

    def query(self, model):
        return FakeQuery(None)


def test_run_has_completed_implementation_treats_failed_attempt_as_resume_trigger(monkeypatch):
    failed_step = SimpleNamespace()

    class ResumeDb:
        def query(self, model):
            return FakeQuery(failed_step)

    assert executor_api._run_has_completed_implementation(ResumeDb(), 'run_1') is True




def test_complete_filesystem_cleanup_runs_without_deepagents(monkeypatch):
    run = SimpleNamespace(id='run_1', goal='cleanup', status=RunStatus.RUNNING, current_step_id='step_plan', final_summary=None)
    planning_step = SimpleNamespace(id='step_plan', status=StepStatus.RUNNING)
    db = FakeDb(run, planning_step)
    env = SimpleNamespace(repo_dir='/workspace/repo')
    approved_plan = {
        'mode': 'filesystem_cleanup',
        'operations': [
            {'type': 'delete_path', 'path': '**/.opencode/', 'matches': ['.opencode']},
            {'type': 'delete_path', 'path': '**/openspec/', 'matches': ['openspec']},
        ],
        'constraints': {'stage_changes': True},
        'commit': {'enabled': True, 'message': 'Remove IDE and temporary configuration folders'},
    }

    commands = []

    def fake_exec_in_container(env_obj, command):
        commands.append(command)
        if 'git status --short' in command:
            return {'ok': True, 'stdout': ' D .opencode/file\n D openspec/spec.md\n'}
        return {'ok': True, 'stdout': 'ok'}

    monkeypatch.setattr(executor_api, 'exec_in_container', fake_exec_in_container)
    monkeypatch.setattr(executor_api, '_id', lambda prefix: f'{prefix}_1')

    result = executor_api._complete_filesystem_cleanup(db, run, planning_step, env, approved_plan)

    assert result.status == RunStatus.COMPLETED
    assert planning_step.status == StepStatus.COMPLETED
    assert any(getattr(step, 'kind', None) == StepKind.IMPLEMENTATION and step.status == StepStatus.COMPLETED for step in db._steps)
    assert commands == [
        "cd /workspace/repo && rm -rf -- '.opencode'",
        "cd /workspace/repo && rm -rf -- 'openspec'",
        "cd /workspace/repo && git status --short",
        "cd /workspace/repo && git add -A",
        "cd /workspace/repo && git config user.name 'OpenClaw Agent'",
        "cd /workspace/repo && git config user.email 'openclaw-agent@local'",
        "cd /workspace/repo && git commit -m 'Remove IDE and temporary configuration folders'",
    ]
