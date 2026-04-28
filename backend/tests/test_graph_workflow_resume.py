from app.graph import workflow as workflow_api
from langgraph.types import Command


class FakeAgent:
    def __init__(self):
        self.calls = []

    def invoke(self, payload, config=None):
        self.calls.append((payload, config))
        return {'messages': [{'content': '{"status":"completed","confidence":0.9,"files_changed":[],"blocking_issues":[],"notes":[]}'}]}

    def get_state(self, config):
        return None


def test_resume_deep_agent_uses_command_resume_for_approval():
    agent = FakeAgent()
    workflow_api.resume_deep_agent(agent, 'thread-123', approve=True)
    payload, config = agent.calls[0]
    assert isinstance(payload, Command)
    assert payload.resume is True
    assert config == {'configurable': {'thread_id': 'thread-123'}}


def test_resume_deep_agent_uses_command_resume_for_rejection():
    agent = FakeAgent()
    workflow_api.resume_deep_agent(agent, 'thread-123', approve=False)
    payload, config = agent.calls[0]
    assert isinstance(payload, Command)
    assert isinstance(payload.resume, str)
    assert 'rejected' in payload.resume.lower()
    assert config == {'configurable': {'thread_id': 'thread-123'}}
