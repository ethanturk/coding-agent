from app.services.filesystem_planner import build_filesystem_cleanup_plan


def test_cleanup_plan_matches_wildcard_directory_patterns():
    repo_files = [
        '.idea/.idea.purist/.idea/workspace.xml',
        '.opencode/command/opsx-apply.md',
        'openspec/specs/cli/spec.md',
        'apps/web/.idea/workspace.xml',
        'packages/foo/.opencode/settings.json',
        'docs/openspec/guide.md',
        'src/main.py',
    ]

    plan = build_filesystem_cleanup_plan(
        'Please delete `**/.idea/`, `**/.opencode/`, and `**/openspec/` only.',
        repo_files,
    )

    assert plan['matched_paths'] == ['**/.idea/', '**/.opencode/', '**/openspec/']
    assert plan['unmatched_paths'] == []
    assert plan['operations'] == [
        {'type': 'delete_path', 'path': '**/.idea/', 'matches': ['.idea', '.idea/.idea.purist/.idea', 'apps/web/.idea']},
        {'type': 'delete_path', 'path': '**/.opencode/', 'matches': ['.opencode', 'packages/foo/.opencode']},
        {'type': 'delete_path', 'path': '**/openspec/', 'matches': ['docs/openspec', 'openspec']},
    ]
