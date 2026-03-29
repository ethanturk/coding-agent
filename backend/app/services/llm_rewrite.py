from app.services.llm_client import llm_chat_text, resolve_role_llm_config
from app.services.settings import get_settings


def _resolve_provider_config(settings: dict) -> tuple[str, str, dict]:
    config = resolve_role_llm_config(settings, 'orchestrator')
    return config['provider'], config['model'], {'base_url': config['api_base'], 'api_key': config['api_key']}


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
    result = llm_chat_text(
        db,
        role='orchestrator',
        messages=[
            {'role': 'system', 'content': system},
            {'role': 'user', 'content': text},
        ],
        temperature=0.2,
    )
    content = result['content'].strip()[:max_len]
    return {'provider': result['provider'], 'model': result['model'], 'content': content, 'max_prompt_length': max_len}
