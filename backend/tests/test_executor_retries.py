from app.services import executor as executor_api


class TransientError(Exception):
    def __init__(self, message='Network error, please try again later', status_code=500):
        super().__init__(message)
        self.status_code = status_code


class PermanentError(Exception):
    pass


def test_invoke_deep_agent_retries_transient_failures(monkeypatch):
    attempts = []

    def fake_invoke(agent, goal, test_command=None, inspect_command=None, thread_id=None):
        attempts.append(goal)
        if len(attempts) < 3:
            raise TransientError()
        return {'status': 'completed'}

    sleeps = []
    monkeypatch.setattr(executor_api, 'invoke_deep_agent', fake_invoke)
    monkeypatch.setattr(executor_api.random, 'uniform', lambda low, high: 0.0)
    monkeypatch.setattr(executor_api.time, 'sleep', lambda seconds: sleeps.append(seconds))

    result = executor_api._invoke_deep_agent_with_retries(
        agent='agent',
        goal='do thing',
        test_command=None,
        inspect_command=None,
        thread_id=None,
    )

    assert result == {'status': 'completed'}
    assert len(attempts) == 3
    assert sleeps == [1.5, 3.0]


def test_invoke_deep_agent_caps_backoff_and_applies_jitter(monkeypatch):
    attempts = []

    def fake_invoke(agent, goal, test_command=None, inspect_command=None, thread_id=None):
        attempts.append(goal)
        if len(attempts) < 4:
            raise TransientError()
        return {'status': 'completed'}

    sleeps = []
    monkeypatch.setattr(executor_api, 'invoke_deep_agent', fake_invoke)
    monkeypatch.setattr(executor_api.random, 'uniform', lambda low, high: high)
    monkeypatch.setattr(executor_api.time, 'sleep', lambda seconds: sleeps.append(seconds))

    result = executor_api._invoke_deep_agent_with_retries(
        agent='agent',
        goal='do thing',
        test_command=None,
        inspect_command=None,
        thread_id=None,
        max_attempts=4,
        base_delay_seconds=2,
        max_delay_seconds=3,
        jitter_ratio=0.5,
    )

    assert result == {'status': 'completed'}
    assert len(attempts) == 4
    assert sleeps == [3.0, 4.5, 4.5]


def test_invoke_deep_agent_does_not_retry_permanent_failures(monkeypatch):
    def fake_invoke(agent, goal, test_command=None, inspect_command=None, thread_id=None):
        raise PermanentError('bad prompt')

    monkeypatch.setattr(executor_api, 'invoke_deep_agent', fake_invoke)
    monkeypatch.setattr(executor_api.time, 'sleep', lambda seconds: (_ for _ in ()).throw(AssertionError('sleep should not be called')))

    try:
        executor_api._invoke_deep_agent_with_retries(
            agent='agent',
            goal='do thing',
            test_command=None,
            inspect_command=None,
            thread_id=None,
        )
    except PermanentError as exc:
        assert str(exc) == 'bad prompt'
    else:
        raise AssertionError('Expected PermanentError')
