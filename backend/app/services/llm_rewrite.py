import json
import urllib.request

from app.services.settings import get_settings


def _resolve_provider_config(settings: dict) -> tuple[str, str, dict]:
    provider = settings.get('default', {}).get('provider') or 'openai'
    model = settings.get('default', {}).get('model') or ''
    providers = settings.get('providers', {})
    if provider == 'openai':
        cfg = providers.get('openai', {})
        base_url = (cfg.get('base_url') or 'https://api.openai.com/v1').rstrip('/')
        api_key = cfg.get('api_key') or ''
    elif provider == 'openai_compatible':
        cfg = providers.get('openai_compatible', {})
        base_url = (cfg.get('base_url') or '').rstrip('/')
        api_key = cfg.get('api_key') or ''
        model = model or cfg.get('model') or ''
    elif provider == 'z_ai_coding':
        cfg = providers.get('z_ai_coding', {})
        base_url = (cfg.get('base_url') or 'https://api.z.ai/api/coding/paas/v4').rstrip('/')
        api_key = cfg.get('api_key') or ''
        model = model or cfg.get('model') or ''
    else:
        raise ValueError(f'Unsupported provider: {provider}')
    return provider, model, {'base_url': base_url, 'api_key': api_key}


def rewrite_prompt(db, text: str) -> dict:
    settings = get_settings(db).value_json
    provider, model, cfg = _resolve_provider_config(settings)
    max_len = int(settings.get('prompting', {}).get('max_prompt_length') or 1000)
    if not cfg.get('api_key'):
        raise ValueError(f'Missing API key for provider {provider}')
    if not model:
        raise ValueError('Default model is not configured')

    system = (
        'Rewrite the user request into a clear, coding-agent-friendly run prompt. '
        'Preserve intent, remove ambiguity, and keep it actionable. '
        f'Respond with plain text only. Maximum length: {max_len} characters.'
    )
    body = {
        'model': model,
        'messages': [
            {'role': 'system', 'content': system},
            {'role': 'user', 'content': text},
        ],
        'temperature': 0.2,
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
    content = payload['choices'][0]['message']['content'].strip()[:max_len]
    return {'provider': provider, 'model': model, 'content': content, 'max_prompt_length': max_len}
