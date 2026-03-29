from __future__ import annotations

from typing import Any

from litellm import completion, responses

from app.services.llm_json import parse_llm_json_text
from app.services.settings import get_settings, resolve_role_model


class LLMClientError(RuntimeError):
    def __init__(
        self,
        message: str,
        *,
        provider: str,
        model: str,
        role: str,
        mode: str,
        api_base: str | None = None,
        response_snippet: str | None = None,
        status_code: int | None = None,
    ):
        super().__init__(message)
        self.provider = provider
        self.model = model
        self.role = role
        self.mode = mode
        self.api_base = api_base
        self.response_snippet = response_snippet
        self.status_code = status_code


def _strip_provider_prefix(model: str) -> str:
    if '/' in model:
        return model.split('/', 1)[1]
    return model


def _compatible_model_name(api_base: str, model: str) -> str:
    raw_model = _strip_provider_prefix(model)
    lower_base = (api_base or '').lower()
    if 'lmstudio' in lower_base or '127.0.0.1:1234' in lower_base or '192.168.5.203:1234' in lower_base:
        return f'lm_studio/{raw_model}'
    return f'openai/{raw_model}'


def resolve_role_llm_config(settings: dict, role: str) -> dict:
    role_cfg = resolve_role_model(settings, role) or {}
    provider = role_cfg.get('provider') or settings.get('default', {}).get('provider') or 'openai'
    model = role_cfg.get('model') or settings.get('default', {}).get('model') or ''
    providers = settings.get('providers', {})

    if provider == 'openai':
        cfg = providers.get('openai', {})
        api_base = (cfg.get('base_url') or 'https://api.openai.com/v1').rstrip('/')
        api_key = cfg.get('api_key') or ''
        supports_native_json = True
        model_name = model
    elif provider == 'openai_compatible':
        cfg = providers.get('openai_compatible', {})
        api_base = (cfg.get('base_url') or '').rstrip('/')
        api_key = cfg.get('api_key') or ''
        raw_model = model or cfg.get('model') or ''
        model_name = _compatible_model_name(api_base, raw_model)
        supports_native_json = False
    elif provider == 'z_ai_coding':
        cfg = providers.get('z_ai_coding', {})
        api_base = (cfg.get('base_url') or 'https://api.z.ai/api/coding/paas/v4').rstrip('/')
        api_key = cfg.get('api_key') or ''
        raw_model = model or cfg.get('model') or ''
        model_name = _compatible_model_name(api_base, raw_model)
        supports_native_json = False
    else:
        raise ValueError(f'Unsupported provider: {provider}')

    return {
        'role': role,
        'provider': provider,
        'model': model_name,
        'api_key': api_key,
        'api_base': api_base,
        'organization': cfg.get('organization') if isinstance(cfg, dict) else None,
        'project': cfg.get('project') if isinstance(cfg, dict) else None,
        'supports_native_json': supports_native_json,
        'extra': {},
    }


def _litellm_args(config: dict, messages: list[dict], temperature: float, max_tokens: int | None, timeout: int) -> dict[str, Any]:
    args: dict[str, Any] = {
        'model': config['model'],
        'messages': messages,
        'temperature': temperature,
        'timeout': timeout,
        'api_key': config['api_key'],
    }
    if config.get('api_base'):
        args['api_base'] = config['api_base']
    if max_tokens is not None:
        args['max_tokens'] = max_tokens
    if config.get('organization'):
        args['organization'] = config['organization']
    if config.get('project'):
        args['project'] = config['project']
    return args


def _raw_dump(response: Any) -> dict:
    if hasattr(response, 'model_dump'):
        try:
            return response.model_dump()
        except Exception:
            return {}
    return {}


def _response_text(response: Any) -> str:
    choices = getattr(response, 'choices', None) or []
    if not choices:
        raw = _raw_dump(response)
        return str(raw.get('output_text') or '').strip()
    choice = choices[0]
    message = getattr(choice, 'message', None)
    if message is None and isinstance(choice, dict):
        message = choice.get('message')
    if message is not None:
        content = getattr(message, 'content', None)
        if content is None and isinstance(message, dict):
            content = message.get('content')
        if isinstance(content, list):
            texts = []
            for part in content:
                if isinstance(part, dict):
                    if part.get('text'):
                        texts.append(str(part['text']))
                    elif part.get('type') == 'text' and isinstance(part.get('text'), dict) and part['text'].get('value'):
                        texts.append(str(part['text']['value']))
                else:
                    texts.append(str(part))
            return ''.join(texts).strip()
        if content:
            return str(content).strip()
    text = getattr(choice, 'text', None)
    if text:
        return str(text).strip()
    if isinstance(choice, dict) and choice.get('text'):
        return str(choice['text']).strip()
    raw = _raw_dump(response)
    return str(raw.get('output_text') or '').strip()


def _usage_dict(response: Any) -> dict | None:
    usage = getattr(response, 'usage', None)
    if not usage:
        return None
    if hasattr(usage, 'model_dump'):
        return usage.model_dump()
    if isinstance(usage, dict):
        return usage
    return None


def _responses_input_from_messages(messages: list[dict]) -> list[dict]:
    items: list[dict] = []
    for message in messages:
        items.append(
            {
                'type': 'message',
                'role': message['role'],
                'content': [{'type': 'input_text', 'text': message['content']}],
            }
        )
    return items


def _response_text_from_responses_api(response: Any) -> str:
    raw = _raw_dump(response)
    if raw.get('output_text'):
        return str(raw['output_text']).strip()
    output = getattr(response, 'output', None) or raw.get('output') or []
    texts: list[str] = []
    for item in output:
        item_type = item.get('type') if isinstance(item, dict) else getattr(item, 'type', None)
        if item_type not in {'message', 'output_text', 'output_item.done'}:
            continue
        content = item.get('content') if isinstance(item, dict) else getattr(item, 'content', None)
        if isinstance(content, list):
            for part in content:
                if isinstance(part, dict):
                    text = part.get('text')
                    if isinstance(text, dict):
                        value = text.get('value')
                        if value:
                            texts.append(str(value))
                    elif text:
                        texts.append(str(text))
        text = item.get('text') if isinstance(item, dict) else getattr(item, 'text', None)
        if text:
            texts.append(str(text))
    return '\n'.join(t for t in texts if t).strip()


def _wrap_error(exc: Exception, *, config: dict, mode: str) -> LLMClientError:
    status_code = getattr(exc, 'status_code', None)
    response_snippet = None
    response = getattr(exc, 'response', None)
    if response is not None:
        body = getattr(response, 'text', None)
        if body:
            response_snippet = str(body)[:1200]
    endpoint = '/responses' if mode.startswith('responses') else '/chat/completions'
    message = f"{config['role']}/{config['provider']}/{config['model']} {mode} request failed"
    if status_code:
        message += f": HTTP {status_code}"
    if config.get('api_base'):
        message += f" at {config['api_base']}{endpoint}"
    if response_snippet:
        message += f" | response: {response_snippet}"
    elif str(exc):
        message += f" | error: {exc}"
    return LLMClientError(
        message,
        provider=config['provider'],
        model=config['model'],
        role=config['role'],
        mode=mode,
        api_base=config.get('api_base'),
        response_snippet=response_snippet,
        status_code=status_code,
    )


LITELLM_SAFE_ROLES = {'orchestrator', 'planner', 'tester', 'reporter'}
LITELLM_CODEX_MODELS = {'gpt-5.3-codex'}


def _is_codex_model(config: dict) -> bool:
    model = config.get('model') or ''
    raw = model.split('/', 1)[1] if model.startswith('openai/') else model
    return raw in LITELLM_CODEX_MODELS


def _ensure_litellm_safe_role(config: dict):
    if config['role'] in LITELLM_SAFE_ROLES:
        return
    if config['role'] in {'developer', 'reviewer'} and _is_codex_model(config):
        return
    raise ValueError(f"Role {config['role']} is not yet migrated to LiteLLM")


def llm_chat_text(
    db,
    *,
    role: str,
    messages: list[dict],
    temperature: float = 0.2,
    max_tokens: int | None = None,
    timeout: int = 600,
) -> dict:
    settings = get_settings(db).value_json
    config = resolve_role_llm_config(settings, role)
    _ensure_litellm_safe_role(config)
    if not config.get('api_key'):
        raise ValueError(f"Missing API key for provider {config['provider']}")
    if not config.get('model'):
        raise ValueError(f"Model not configured for role {role}")
    try:
        response = completion(**_litellm_args(config, messages, temperature, max_tokens, timeout))
    except Exception as exc:
        raise _wrap_error(exc, config=config, mode='text') from exc
    content = _response_text(response).strip()
    raw = _raw_dump(response)
    if not content:
        raise LLMClientError(
            f"{config['role']}/{config['provider']}/{config['model']} text request returned empty content",
            provider=config['provider'],
            model=config['model'],
            role=config['role'],
            mode='text',
            api_base=config.get('api_base'),
            response_snippet=str(raw)[:1200],
            status_code=None,
        )
    return {
        'provider': config['provider'],
        'model': config['model'],
        'content': content,
        'raw': raw,
        'usage': _usage_dict(response),
    }


def llm_chat_json(
    db,
    *,
    role: str,
    messages: list[dict],
    temperature: float = 0.1,
    schema_hint: dict | None = None,
    strict_json: bool = False,
    timeout: int = 600,
) -> dict:
    settings = get_settings(db).value_json
    config = resolve_role_llm_config(settings, role)
    _ensure_litellm_safe_role(config)
    if not config.get('api_key'):
        raise ValueError(f"Missing API key for provider {config['provider']}")
    if not config.get('model'):
        raise ValueError(f"Model not configured for role {role}")

    json_mode = 'prompted_text'
    if _is_codex_model(config):
        try:
            response = responses(
                model=config['model'],
                input=_responses_input_from_messages(messages),
                api_key=config['api_key'],
                api_base=config.get('api_base'),
                timeout=timeout,
            )
        except Exception as exc:
            raise _wrap_error(exc, config=config, mode='responses_json') from exc
        content = _response_text_from_responses_api(response)
        raw = _raw_dump(response)
        if not content:
            raise LLMClientError(
                f"{config['role']}/{config['provider']}/{config['model']} responses_json request returned empty content",
                provider=config['provider'],
                model=config['model'],
                role=config['role'],
                mode='responses_json',
                api_base=config.get('api_base'),
                response_snippet=str(raw)[:1200],
                status_code=None,
            )
        parsed = parse_llm_json_text(content)
        return {
            'provider': config['provider'],
            'model': config['model'],
            'content': content,
            'parsed': parsed,
            'raw': raw,
            'usage': _usage_dict(response),
            'json_mode': 'responses_prompted_text',
            'schema_hint': schema_hint,
        }

    args = _litellm_args(config, messages, temperature, None, timeout)
    if strict_json and config.get('supports_native_json'):
        args['response_format'] = {'type': 'json_object'}
        json_mode = 'native'

    try:
        response = completion(**args)
    except Exception as exc:
        raise _wrap_error(exc, config=config, mode='json') from exc

    content = _response_text(response).strip()
    raw = _raw_dump(response)
    if not content:
        raise LLMClientError(
            f"{config['role']}/{config['provider']}/{config['model']} json request returned empty content",
            provider=config['provider'],
            model=config['model'],
            role=config['role'],
            mode='json',
            api_base=config.get('api_base'),
            response_snippet=str(raw)[:1200],
            status_code=None,
        )
    parsed = parse_llm_json_text(content)
    return {
        'provider': config['provider'],
        'model': config['model'],
        'content': content,
        'parsed': parsed,
        'raw': raw,
        'usage': _usage_dict(response),
        'json_mode': json_mode,
        'schema_hint': schema_hint,
    }
