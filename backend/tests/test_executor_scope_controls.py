from app.services.executor import _should_auto_approve


def test_auto_approve_blocks_when_scope_guard_requires_review():
    settings = {'autonomy': {'auto_approve_threshold': 0.8}}
    agent_result = {'confidence': 0.95, 'review_decision': 'approve', 'blocking_issues': []}

    allowed = _should_auto_approve(
        settings,
        agent_result,
        scope_guard={'requires_human_review': True},
    )

    assert allowed is False


def test_auto_approve_allows_high_confidence_clean_review():
    settings = {'autonomy': {'auto_approve_threshold': 0.8}}
    agent_result = {'confidence': 0.95, 'review_decision': 'approve', 'blocking_issues': []}

    allowed = _should_auto_approve(
        settings,
        agent_result,
        scope_guard={'requires_human_review': False},
    )

    assert allowed is True


def test_auto_approve_rejects_request_changes_even_if_confident():
    settings = {'autonomy': {'auto_approve_threshold': 0.2}}
    agent_result = {'confidence': 0.99, 'review_decision': 'request_changes', 'blocking_issues': []}

    allowed = _should_auto_approve(
        settings,
        agent_result,
        scope_guard={'requires_human_review': False},
    )

    assert allowed is False
