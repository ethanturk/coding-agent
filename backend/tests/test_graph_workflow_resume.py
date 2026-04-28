from app.graph import workflow as workflow_api
from langgraph.types import Command


class FakeInterrupt:
    def __init__(self, interrupt_id, value):
        self.id = interrupt_id
        self.value = value


class FakeState:
    def __init__(self, interrupts=None):
        self.interrupts = interrupts or ()
        self.values = {}
        self.next = ('resume',) if interrupts else ()


class FakeAgent:
    def __init__(self, interrupts=None):
        self.calls = []
        self._interrupts = interrupts or []

    def invoke(self, payload, config=None):
        self.calls.append((payload, config))
        return {'messages': [{'content': '{"status":"completed","confidence":0.9,"files_changed":[],"blocking_issues":[],"notes":[]}'}]}

    def get_state(self, config):
        return FakeState(self._interrupts)


def test_resume_deep_agent_uses_interrupt_id_map_for_approval():
    agent = FakeAgent([
        FakeInterrupt('int-1', {'action_requests': [{'name': 'edit_file'}, {'name': 'write_file'}]}),
        FakeInterrupt('int-2', {'action_requests': [{'name': 'edit_file'}]}),
    ])
    workflow_api.resume_deep_agent(agent, 'thread-123', approve=True)
    payload, config = agent.calls[0]
    assert isinstance(payload, Command)
    assert payload.resume == {
        'int-1': {'decisions': [{'type': 'approve'}, {'type': 'approve'}]},
        'int-2': {'decisions': [{'type': 'approve'}]},
    }
    assert config == {'configurable': {'thread_id': 'thread-123'}}


def test_resume_deep_agent_uses_interrupt_id_map_for_rejection():
    agent = FakeAgent([
        FakeInterrupt('int-1', {'action_requests': [{'name': 'edit_file'}, {'name': 'write_file'}]}),
        FakeInterrupt('int-2', {'action_requests': [{'name': 'edit_file'}]}),
    ])
    workflow_api.resume_deep_agent(agent, 'thread-123', approve=False)
    payload, config = agent.calls[0]
    assert isinstance(payload, Command)
    assert payload.resume.keys() == {'int-1', 'int-2'}
    assert payload.resume['int-1']['decisions'][0]['type'] == 'reject'
    assert payload.resume['int-1']['decisions'][1]['type'] == 'reject'
    assert payload.resume['int-2']['decisions'][0]['type'] == 'reject'
    assert all('rejected' in decision['message'].lower() for value in payload.resume.values() for decision in value['decisions'])
    assert config == {'configurable': {'thread_id': 'thread-123'}}
