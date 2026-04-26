from app.services.approval_flow import build_plan_approval_payload, get_scope_control


def test_plan_approval_payload_carries_thread_id_and_files():
    plan = {
        'summary': 'Update backend and tests',
        'targets': [
            {'path': 'backend/app.py'},
            {'path': 'backend/test_app.py'},
        ],
        'risks': [],
    }

    payload = build_plan_approval_payload(plan, get_scope_control({}), thread_id='thread-123')

    assert payload['kind'] == 'plan'
    assert payload['thread_id'] == 'thread-123'
    assert payload['files_changed'] == ['backend/app.py', 'backend/test_app.py']
