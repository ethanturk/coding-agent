from types import SimpleNamespace

from app.models.enums import EnvironmentStatus
from app.services import docker_runner


class EnvStub:
    repo_dir = '/workspace/repo'
    run_id = 'run_123'


def test_configure_repo_git_identity_uses_repo_local_git_config(monkeypatch):
    commands = []

    def fake_exec(env, command):
        commands.append(command)
        return {'ok': True}

    monkeypatch.setattr(docker_runner, 'exec_in_container', fake_exec)

    result = docker_runner.configure_repo_git_identity(EnvStub(), 'Agent Platform', 'agent-platform@local')

    assert result['ok'] is True
    assert commands == [
        "cd /workspace/repo && git config user.name 'Agent Platform' && git config user.email 'agent-platform@local'"
    ]


def test_bootstrap_repo_force_clean_removes_existing_repo_first(monkeypatch):
    commands = []

    def fake_exec(env, command):
        commands.append(command)
        if 'git clone' in command:
            return {'ok': True, 'stderr': '', 'stdout': ''}
        if 'git checkout -b' in command:
            return {'ok': True, 'stderr': '', 'stdout': ''}
        return {'ok': True, 'stderr': '', 'stdout': ''}

    monkeypatch.setattr(docker_runner, 'exec_in_container', fake_exec)

    env = SimpleNamespace(repo_dir='/workspace/repo', run_id='run_123', branch_name='agent-platform/run_123', status=EnvironmentStatus.CREATING)
    project = SimpleNamespace(repo_url='https://github.com/example/repo.git', default_branch='main')

    class FakeDb:
        def commit(self):
            pass

    result = docker_runner.bootstrap_repo_in_container(FakeDb(), env, project, force_clean=True)

    assert result['ok'] is True
    assert commands[1] == 'rm -rf /workspace/repo'
    assert result['force_clean'] is True
