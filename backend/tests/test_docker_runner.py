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
