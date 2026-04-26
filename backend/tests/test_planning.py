from app.services.planning import build_initial_plan, collect_repo_files


def test_collect_repo_files_ignores_blank_lines():
    files = collect_repo_files('a.py\n\nbackend/app.py\n')
    assert files == ['a.py', 'backend/app.py']


def test_build_initial_plan_creates_ranked_targets():
    repo_files = [
        'backend/app/api/settings.py',
        'frontend/components/settings-editor.tsx',
        'README.md',
        'backend/tests/test_settings.py',
    ]

    plan = build_initial_plan('Tighten settings UI and backend settings handling', repo_files)

    assert plan['targets']
    assert plan['targets'][0]['priority'] == 1
    assert all(target['action'] == 'modify' for target in plan['targets'])
    assert 'Inspect' in plan['summary']


def test_build_initial_plan_warns_when_limit_reached():
    repo_files = [f'backend/file_{idx}.py' for idx in range(20)]
    plan = build_initial_plan('backend', repo_files)
    assert any('target cap' in risk for risk in plan['risks'])


def test_build_initial_plan_routes_directory_deletes_to_filesystem_cleanup():
    repo_files = [
        '.opencode/skills/openspec-apply-change/SKILL.md',
        'openspec/changes/archive/2026-03-04-chunk-large-files-for-review/specs/file-chunking/spec.md',
        '.idea/workspace.xml',
        'src/app.py',
    ]

    plan = build_initial_plan(
        'Please delete the following directories from the repository (recursively, at any depth) and ensure only these are removed: - .idea/ - .opencode/ - openspec/ After deletion, stage all changes and create a commit with the message: "Remove IDE and temporary configuration folders". Verify that no other files or directories were affected. If the repository uses Git, confirm the removal by running git status before committing.',
        repo_files,
    )

    assert plan['mode'] == 'filesystem_cleanup'
    assert [op['path'] for op in plan['operations']] == ['.idea/', '.opencode/', 'openspec/']
    assert plan['commit']['enabled'] is True
    assert plan['commit']['message'] == 'Remove IDE and temporary configuration folders'
    assert plan['verification'] == ['git status --short']
