from app.services.executor import _approved_plan_requires_continuation


def test_cleanup_plan_continuation_still_true_with_mixed_case_db_strategy():
    assert _approved_plan_requires_continuation({'mode': 'filesystem_cleanup'}) is True
