import json
import urllib.request

from app.services.llm_rewrite import _resolve_provider_config
from app.services.settings import get_settings, resolve_role_model


def enrich_edit_plan(db, goal: str, search_context: dict, edit_plan: dict) -> dict:
    settings = get_settings(db).value_json
    provider, model, cfg = _resolve_provider_config(settings)
    model = (resolve_role_model(settings, 'planner') or {}).get('model') or model
    if not cfg.get('api_key') or not model:
        return {'used': False, 'reason': 'planner model not configured'}

    system = (
        'You are helping a coding agent plan a multi-file code change. '
        'Given a user goal, repo search context, and a deterministic draft plan, '
        'return compact JSON with keys summary, primary_targets, secondary_targets, risks, and notes. '
        'Only include files already present in the draft plan.'
    )
    body = {
        'model': model,
        'messages': [
            {'role': 'system', 'content': system},
            {'role': 'user', 'content': json.dumps({'goal': goal, 'search_context': search_context, 'draft_plan': edit_plan})},
        ],
        'temperature': 0.1,
        'response_format': {'type': 'json_object'},
    }
    req = urllib.request.Request(
        f"{cfg['base_url']}/chat/completions",
        data=json.dumps(body).encode('utf-8'),
        headers={
            'Content-Type': 'application/json',
            'Authorization': f"Bearer {cfg['api_key']}",
        },
        method='POST',
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        payload = json.loads(resp.read().decode('utf-8'))
    content = payload['choices'][0]['message']['content'].strip()
    parsed = json.loads(content)
    return {'used': True, 'provider': provider, 'model': model, 'content': parsed}
