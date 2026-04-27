import json

from app.services.llm_client import llm_chat_json
from app.services.settings import get_settings, resolve_role_model


def enrich_edit_plan(db, goal: str, search_context: dict, edit_plan: dict) -> dict:
    settings = get_settings(db).value_json
    model = (resolve_role_model(settings, 'planner') or {}).get('model') or ''
    provider = (resolve_role_model(settings, 'planner') or {}).get('provider') or settings.get('default', {}).get('provider')
    if not model:
        return {'used': False, 'reason': 'planner model not configured'}

    system = (((settings.get('prompting') or {}).get('templates') or {}).get('planner_system') or (
        'You are helping a coding agent plan a multi-file code change. '
        'Given a user goal, repo search context, and a deterministic draft plan, '
        'return compact JSON with keys summary, primary_targets, secondary_targets, risks, and notes. '
        'Only include files already present in the draft plan. Respond with raw JSON only.'
    ))
    result = llm_chat_json(
        db,
        role='planner',
        messages=[
            {'role': 'system', 'content': system},
            {'role': 'user', 'content': json.dumps({'goal': goal, 'search_context': search_context, 'draft_plan': edit_plan})},
        ],
        temperature=0.1,
        strict_json=False,
    )
    return {'used': True, 'provider': provider, 'model': model, 'content': result['parsed']}
