from app.services.settings import DEFAULT_SETTINGS
from app.services import executor as executor_api


def test_default_settings_include_model_retry_controls():
    retries = DEFAULT_SETTINGS['autonomy']['model_retries']
    assert retries['max_attempts'] == 3
    assert retries['base_delay_seconds'] == 1.5
    assert retries['max_delay_seconds'] == 10.0
    assert retries['jitter_ratio'] == 0.25


def test_retry_wrapper_clamps_invalid_values(monkeypatch):
    attempts = []

    def fake_invoke(agent, goal, test_command=None, inspect_command=None, thread_id=None):
        attempts.append(goal)
        return {'status': 'completed'}

    sleeps = []
    monkeypatch.setattr(executor_api, 'invoke_deep_agent', fake_invoke)
    monkeypatch.setattr(executor_api.time, 'sleep', lambda seconds: sleeps.append(seconds))

    result = executor_api._invoke_deep_agent_with_retries(
        agent='agent',
        goal='do thing',
        test_command=None,
        inspect_command=None,
        thread_id=None,
        max_attempts=0,
        base_delay_seconds=-5,
    )

    assert result == {'status': 'completed'}
    assert len(attempts) == 1
    assert sleeps == []
