from app.services.planning import enrich_plan_if_possible


def test_filesystem_cleanup_plan_bypasses_edit_enrichment():
    draft_plan = {
        'mode': 'filesystem_cleanup',
        'summary': 'Delete matched directories only',
        'operations': [{'type': 'delete_path', 'path': '**/.idea/', 'matches': ['apps/web/.idea']}],
        'matched_paths': ['**/.idea/'],
    }

    result = enrich_plan_if_possible(db=None, goal='cleanup', repo_files=['apps/web/.idea/workspace.xml'], draft_plan=draft_plan)

    assert result['plan'] == draft_plan
    assert result['enrichment'] == {
        'used': False,
        'reason': 'filesystem_cleanup_bypasses_edit_enrichment',
    }
