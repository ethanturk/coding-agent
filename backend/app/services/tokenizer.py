from __future__ import annotations

import tiktoken


MODEL_ENCODING_HINTS = [
    ('gpt-4.1', 'o200k_base'),
    ('gpt-4o', 'o200k_base'),
    ('gpt-5', 'o200k_base'),
    ('o1', 'o200k_base'),
    ('o3', 'o200k_base'),
]


def _normalize_model_name(model_name: str | None) -> str:
    if not model_name:
        return ''
    model = str(model_name)
    if '/' in model:
        model = model.split('/', 1)[1]
    return model.strip().lower()


def get_token_encoding(model_name: str | None):
    normalized = _normalize_model_name(model_name)
    if not normalized:
        return tiktoken.get_encoding('o200k_base')
    try:
        return tiktoken.encoding_for_model(normalized)
    except Exception:
        for prefix, encoding_name in MODEL_ENCODING_HINTS:
            if normalized.startswith(prefix):
                return tiktoken.get_encoding(encoding_name)
    return tiktoken.get_encoding('o200k_base')


def count_tokens(text: str, model_name: str | None = None) -> int:
    if not text:
        return 0
    encoding = get_token_encoding(model_name)
    return len(encoding.encode(text))


def truncate_to_token_limit(text: str, token_limit: int, model_name: str | None = None) -> str:
    if not text:
        return ''
    token_limit = max(1, int(token_limit))
    encoding = get_token_encoding(model_name)
    tokens = encoding.encode(text)
    if len(tokens) <= token_limit:
        return text
    return encoding.decode(tokens[:token_limit])
