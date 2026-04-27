from __future__ import annotations

import json

from app.services.developer_agent import infer_targets_from_repo, search_terms_from_goal
from app.services.filesystem_planner import build_filesystem_cleanup_plan, classify_goal_mode
from app.services.llm_planner import enrich_edit_plan


PLAN_LIMIT = 12


def collect_repo_files(repo_listing: str) -> list[str]:
    return [line.strip() for line in (repo_listing or '').splitlines() if line.strip()]


def build_initial_plan(goal: str, repo_files: list[str], search_context: dict | None = None) -> dict:
    goal_mode = classify_goal_mode(goal)
    if goal_mode.get('mode') == 'filesystem_cleanup':
        return build_filesystem_cleanup_plan(goal, repo_files)

    targets = infer_targets_from_repo(goal, repo_files)[:PLAN_LIMIT]
    search_terms = search_terms_from_goal(goal)
    search_context = search_context or {}
    plan_targets = []
    for idx, path in enumerate(targets, start=1):
        plan_targets.append(
            {
                'path': path,
                'action': 'modify',
                'description': f'Inspect and update {path} to satisfy the requested goal.',
                'rationale': 'Selected as a likely relevant file based on repository heuristics and goal terms.',
                'dependencies': [],
                'risk': 'medium' if idx > 3 else 'low',
                'priority': idx,
            }
        )
    summary = (
        f'Inspect {len(plan_targets)} planned file(s) for the goal. '
        f'Search terms: {", ".join(search_terms[:5]) or "none"}.'
    )
    risks = []
    if not plan_targets:
        risks.append('No relevant files were inferred from the repository listing.')
    if len(plan_targets) >= PLAN_LIMIT:
        risks.append('Plan reached the target cap; relevant files may have been truncated.')
    if search_context.get('related_files'):
        risks.append('Related files exist outside the primary target set and may require explicit approval if scope expands.')
    return {
        'summary': summary,
        'targets': plan_targets,
        'risks': risks,
        'notes': [
            'Targets are heuristically inferred and should be reviewed before implementation.',
            'Unplanned file changes should trigger a human review gate.',
        ],
    }


def enrich_plan_if_possible(db, goal: str, repo_files: list[str], draft_plan: dict) -> dict:
    if draft_plan.get('mode') == 'filesystem_cleanup':
        return {
            'plan': draft_plan,
            'enrichment': {
                'used': False,
                'reason': 'filesystem_cleanup_bypasses_edit_enrichment',
            },
        }

    search_context = {
        'file_count': len(repo_files),
        'related_files': [target.get('path') for target in draft_plan.get('targets', [])],
    }
    try:
        enriched = enrich_edit_plan(db, goal, search_context, draft_plan)
    except Exception as exc:
        return {'plan': draft_plan, 'enrichment': {'used': False, 'reason': str(exc)}}
    if not enriched.get('used'):
        return {'plan': draft_plan, 'enrichment': enriched}

    content = enriched.get('content') or {}
    primary_targets = content.get('primary_targets') or []
    secondary_targets = content.get('secondary_targets') or []
    ordered_paths = []
    for path in [*primary_targets, *secondary_targets]:
        if path and path not in ordered_paths:
            ordered_paths.append(path)

    current_targets = {target['path']: target for target in draft_plan.get('targets', []) if target.get('path')}
    reordered = []
    for idx, path in enumerate(ordered_paths, start=1):
        if path not in current_targets:
            continue
        target = {**current_targets[path], 'priority': idx}
        reordered.append(target)
    for path, target in current_targets.items():
        if path not in {item['path'] for item in reordered}:
            reordered.append({**target, 'priority': len(reordered) + 1})

    plan = {
        'summary': content.get('summary') or draft_plan.get('summary'),
        'targets': reordered or draft_plan.get('targets', []),
        'risks': content.get('risks') or draft_plan.get('risks', []),
        'notes': content.get('notes') or draft_plan.get('notes', []),
    }
    return {'plan': plan, 'enrichment': enriched}


def serialize_plan(plan: dict) -> str:
    return json.dumps(plan, indent=2, sort_keys=True)
