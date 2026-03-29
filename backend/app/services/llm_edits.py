import json
import urllib.request
from pathlib import Path

from app.services.llm_rewrite import _resolve_provider_config
from app.services.settings import get_settings, resolve_role_model


def _llm_edit_schema() -> dict:
    return {
        'strategy': 'replace_region | insert_before | insert_after | update_key_value | no_op',
        'replacement_text': 'string',
        'insert_before': 'string',
        'insert_after': 'string',
        'target_anchor': 'string',
        'confidence': 'number between 0 and 1',
        'notes': ['string'],
        'risks': ['string'],
    }


def build_language_prompt_context(file_path: str, semantic_patch: dict) -> dict:
    suffix = Path(file_path).suffix.lower()
    if suffix in {'.py'}:
        family = 'python'
    elif suffix in {'.ts', '.tsx', '.js', '.jsx'}:
        family = 'javascript_like'
    elif suffix in {'.json', '.yaml', '.yml'}:
        family = 'config'
    elif suffix in {'.md'}:
        family = 'markdown'
    else:
        family = 'generic'
    return {
        'language_family': family,
        'region_type': semantic_patch.get('target_region', {}).get('anchor', 'body'),
        'target_anchor': semantic_patch.get('target_region', {}).get('anchor', 'body'),
        'style_hint': 'prefer minimal targeted edits',
    }


def suggest_bounded_edit(db, goal: str, file_path: str, current_content: str, semantic_patch: dict) -> dict:
    settings = get_settings(db).value_json
    provider, model, cfg = _resolve_provider_config(settings)
    model = (resolve_role_model(settings, 'developer') or {}).get('model') or model
    if not cfg.get('api_key') or not model:
        return {'used': False, 'reason': 'developer model not configured'}
    region = semantic_patch.get('target_region', {})
    lines = current_content.splitlines()
    start = max(1, region.get('start_line', 1))
    end = min(len(lines), region.get('end_line', len(lines)))
    window = '\n'.join(lines[max(0, start - 4):min(len(lines), end + 4)])
    system = (
        'You are generating a bounded code edit. '
        'Only respond with JSON matching the provided schema. '
        'Do not rewrite the whole file. Keep the response scoped to the targeted region.'
    )
    prompt_context = build_language_prompt_context(file_path, semantic_patch)
    body = {
        'model': model,
        'messages': [
            {'role': 'system', 'content': system},
            {'role': 'user', 'content': json.dumps({'goal': goal, 'file_path': file_path, 'semantic_patch': semantic_patch, 'region_context': window, 'prompt_context': prompt_context, 'schema': _llm_edit_schema()})},
        ],
        'temperature': 0.1,
        'response_format': {'type': 'json_object'},
    }
    req = urllib.request.Request(
        f"{cfg['base_url']}/chat/completions",
        data=json.dumps(body).encode('utf-8'),
        headers={'Content-Type': 'application/json', 'Authorization': f"Bearer {cfg['api_key']}"},
        method='POST',
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        payload = json.loads(resp.read().decode('utf-8'))
    content = json.loads(payload['choices'][0]['message']['content'].strip())
    return {'used': True, 'provider': provider, 'model': model, 'content': content}


def validate_llm_edit_response(llm_edit: dict) -> dict:
    if not llm_edit.get('used'):
        return {'ok': False, 'warnings': [llm_edit.get('reason', 'llm_not_used')]}
    content = llm_edit.get('content') or {}
    strategy = content.get('strategy')
    if strategy not in {'replace_region', 'insert_before', 'insert_after', 'update_key_value', 'no_op'}:
        return {'ok': False, 'warnings': ['invalid_strategy']}
    confidence = content.get('confidence', 0)
    try:
        confidence = float(confidence)
    except Exception:
        return {'ok': False, 'warnings': ['invalid_confidence']}
    if confidence < 0 or confidence > 1:
        return {'ok': False, 'warnings': ['confidence_out_of_range']}
    return {'ok': True, 'warnings': []}


def compile_llm_edit_candidate(file_path: str, current_content: str, semantic_patch: dict, llm_edit: dict) -> dict:
    validation = validate_llm_edit_response(llm_edit)
    if not validation['ok']:
        return {'ok': False, 'reason': ','.join(validation['warnings']), 'new_text': current_content, 'generator': 'llm_bounded'}
    content = llm_edit['content']
    strategy = content['strategy']
    region = semantic_patch.get('target_region', {})
    lines = current_content.splitlines()
    start = max(1, region.get('start_line', 1)) - 1
    end = max(start, region.get('end_line', max(1, len(lines))))
    if strategy == 'no_op':
        return {'ok': True, 'reason': 'llm_no_op', 'new_text': current_content, 'generator': 'llm_bounded', 'confidence': content.get('confidence', 0)}
    if strategy == 'replace_region':
        replacement = (content.get('replacement_text') or '').splitlines()
        new_lines = lines[:start] + replacement + lines[end:]
    elif strategy == 'insert_before':
        insertion = (content.get('insert_before') or '').splitlines()
        new_lines = lines[:start] + insertion + lines[start:]
    elif strategy == 'insert_after':
        insertion = (content.get('insert_after') or '').splitlines()
        new_lines = lines[:end] + insertion + lines[end:]
    elif strategy == 'update_key_value':
        replacement = content.get('replacement_text') or ''
        new_lines = lines[:start] + replacement.splitlines() + lines[end:]
    else:
        return {'ok': False, 'reason': 'unsupported_strategy', 'new_text': current_content, 'generator': 'llm_bounded'}
    new_text = '\n'.join(new_lines) + ('\n' if current_content.endswith('\n') else '')
    return {'ok': True, 'reason': strategy, 'new_text': new_text, 'generator': 'llm_bounded', 'confidence': float(content.get('confidence', 0))}


def validate_bounded_candidate(original: str, candidate: dict, semantic_patch: dict) -> dict:
    if not candidate.get('ok'):
        return {'ok': False, 'warnings': [candidate.get('reason', 'candidate_invalid')]}
    updated = candidate['new_text']
    region = semantic_patch.get('target_region', {})
    if updated == original and candidate.get('reason') != 'llm_no_op':
        return {'ok': False, 'warnings': ['candidate_no_effect']}
    if len(updated.splitlines()) - len(original.splitlines()) > max(40, region.get('end_line', 1) - region.get('start_line', 1) + 20):
        return {'ok': False, 'warnings': ['candidate_exceeds_bounded_region']}
    return {'ok': True, 'warnings': []}


def score_edit_candidate(generator: str, proposal: dict, llm_candidate: dict | None = None) -> float:
    score = 0.0
    if proposal.get('validation', {}).get('ok'):
        score += 0.35
    score += min(0.25, proposal.get('semantic_patch', {}).get('target_region', {}).get('end_line', 1) / 200)
    score += 0.2 if proposal.get('intent') in {'update_key_value', 'update_docs', 'update_test'} else 0.1
    score += 0.1 if proposal.get('dependency_group') else 0.0
    if generator == 'llm_bounded' and llm_candidate:
        score += min(0.25, float(llm_candidate.get('confidence', 0)) * 0.25)
    return round(score, 4)


def rollout_policy(settings: dict, semantic_patch: dict, deterministic_score: float, llm_score: float, llm_validation: dict | None) -> str:
    stage = settings.get('bounded_llm', {}).get('rollout_stage', 'stage_b')
    if stage == 'stage_a':
        return 'deterministic'
    if not llm_validation or not llm_validation.get('ok'):
        return 'deterministic'
    region = semantic_patch.get('target_region', {})
    region_size = max(1, region.get('end_line', 1) - region.get('start_line', 1) + 1)
    if stage == 'stage_b':
        if llm_score > deterministic_score and region_size <= 40:
            return 'llm_bounded'
        return 'deterministic'
    return 'llm_bounded' if llm_score > deterministic_score else 'deterministic'


def choose_edit_candidate(settings: dict, deterministic: dict, llm_candidate: dict | None, llm_validation: dict | None) -> dict:
    deterministic_score = score_edit_candidate('deterministic', deterministic)
    llm_score = -1.0
    if llm_candidate and llm_validation and llm_validation.get('ok'):
        llm_score = score_edit_candidate('llm_bounded', deterministic, llm_candidate)
    winner = rollout_policy(settings, deterministic.get('semantic_patch', {}), deterministic_score, llm_score, llm_validation)
    return {'winner': winner, 'deterministic_score': deterministic_score, 'llm_score': llm_score, 'rollout_stage': settings.get('bounded_llm', {}).get('rollout_stage', 'stage_b')}
