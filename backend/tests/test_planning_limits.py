from app.services import planning as planning_api
from app.services.planning import build_initial_plan, resolve_plan_limit


def test_resolve_plan_limit_uses_default_and_clamps_invalid_values():
    assert resolve_plan_limit(None) == 12
    assert resolve_plan_limit({}) == 12
    assert resolve_plan_limit({'autonomy': {'plan_target_cap': 25}}) == 25
    assert resolve_plan_limit({'autonomy': {'plan_target_cap': 0}}) == 1
    assert resolve_plan_limit({'autonomy': {'plan_target_cap': 'bad'}}) == 12


def test_build_initial_plan_uses_configured_target_cap(monkeypatch):
    repo_files = [f'file_{idx}.py' for idx in range(30)]
    monkeypatch.setattr(planning_api, 'infer_targets_from_repo', lambda goal, files: files)
    plan = build_initial_plan(
        'Update the repository to improve several modules',
        repo_files,
        settings={'autonomy': {'plan_target_cap': 5}},
    )

    assert len(plan['targets']) == 5
    assert any('target cap (5)' in risk for risk in plan['risks'])
