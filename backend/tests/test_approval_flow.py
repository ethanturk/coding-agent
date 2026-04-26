from app.services.approval_flow import (
    DEFAULT_SCOPE_CONTROL,
    build_plan_approval_payload,
    build_review_approval_payload,
    classify_changed_files,
    extract_approved_plan,
    get_scope_control,
    scope_guard_decision,
    should_interrupt_before_write,
)


def test_get_scope_control_defaults_and_normalizes_values():
    settings = {
        'autonomy': {
            'scope_control': {
                'max_files_changed': 0,
                'max_parallel_developer_tasks': 0,
                'require_plan_approval': False,
            }
        }
    }

    scope = get_scope_control(settings)

    assert scope['max_files_changed'] == 1
    assert scope['max_parallel_developer_tasks'] == 1
    assert scope['require_plan_approval'] is False
    assert scope['interrupt_before_write'] is DEFAULT_SCOPE_CONTROL['interrupt_before_write']


def test_should_interrupt_before_write_uses_scope_control():
    assert should_interrupt_before_write({'autonomy': {'scope_control': {'interrupt_before_write': False}}}) is False
    assert should_interrupt_before_write({'autonomy': {'scope_control': {'interrupt_before_write': True}}}) is True


def test_classify_changed_files_normalizes_strings_and_dicts():
    files = classify_changed_files(['a.py', {'path': 'b.py'}, {'path': 'a.py'}, None])
    assert files == ['a.py', 'b.py']


def test_scope_guard_flags_budget_and_unplanned_files():
    scope_control = get_scope_control({'autonomy': {'scope_control': {'max_files_changed': 2, 'allow_path_expansion': False}}})

    guard = scope_guard_decision(
        planned_files=['backend/a.py', 'backend/b.py'],
        changed_files=['backend/a.py', 'backend/c.py', 'backend/d.py'],
        scope_control=scope_control,
    )

    assert guard['requires_human_review'] is True
    assert 'file_budget_exceeded' in guard['reasons']
    assert 'unplanned_files_changed' in guard['reasons']
    assert guard['extra_files'] == ['backend/c.py', 'backend/d.py']


def test_scope_guard_allows_planned_changes_within_budget():
    scope_control = get_scope_control({'autonomy': {'scope_control': {'max_files_changed': 3, 'allow_path_expansion': False}}})

    guard = scope_guard_decision(
        planned_files=['backend/a.py', 'backend/b.py'],
        changed_files=['backend/a.py', 'backend/b.py'],
        scope_control=scope_control,
    )

    assert guard['requires_human_review'] is False
    assert guard['reasons'] == []


def test_build_plan_approval_payload_includes_targets_and_scope_control():
    plan = {
        'summary': 'Update API and tests',
        'targets': [
            {'path': 'backend/api.py', 'action': 'modify', 'description': 'change endpoint'},
            {'path': 'backend/test_api.py', 'action': 'modify', 'description': 'adjust tests'},
        ],
        'risks': ['May require fixture updates'],
    }
    scope_control = get_scope_control({})

    payload = build_plan_approval_payload(plan, scope_control)

    assert payload['kind'] == 'plan'
    assert payload['summary']['files'] == ['backend/api.py', 'backend/test_api.py']
    assert payload['scope_control'] == scope_control
    assert payload['override_block_allowed'] is True


def test_build_plan_approval_payload_for_cleanup_uses_operations():
    plan = {
        'mode': 'filesystem_cleanup',
        'summary': 'Delete requested directories only',
        'operations': [
            {'type': 'delete_path', 'path': '.idea/'},
            {'type': 'delete_path', 'path': '.opencode/'},
        ],
        'verification': ['git status --short'],
        'commit': {'enabled': True, 'message': 'Remove IDE files'},
    }

    payload = build_plan_approval_payload(plan, get_scope_control({}))

    assert payload['mode'] == 'filesystem_cleanup'
    assert payload['summary']['files'] == ['.idea/', '.opencode/']
    assert payload['operations'] == plan['operations']


def test_build_review_approval_payload_includes_scope_guard_reason():
    payload = build_review_approval_payload(
        agent_result={'review_summary': 'Changed too many files'},
        diff='diff --git a',
        files_changed=['a.py', 'b.py'],
        scope_guard={'reasons': ['file_budget_exceeded']},
        scope_control=get_scope_control({}),
    )

    assert payload['kind'] == 'review'
    assert payload['summary']['reason'] == 'file_budget_exceeded'
    assert payload['files_changed'] == ['a.py', 'b.py']
    assert payload['override_block_allowed'] is True


def test_extract_approved_plan_returns_only_plan_payloads():
    plan_payload = build_plan_approval_payload(
        {'summary': 'Only touch api.py', 'targets': [{'path': 'api.py'}], 'risks': []},
        get_scope_control({}),
    )

    assert extract_approved_plan(plan_payload)['targets'][0]['path'] == 'api.py'
    assert extract_approved_plan({'kind': 'review'}) is None
