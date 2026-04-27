from app.services import tokenizer as tokenizer_api


def test_count_tokens_uses_default_encoding_for_unknown_models():
    count = tokenizer_api.count_tokens('abcdefgh', 'unknown-model-family')
    assert isinstance(count, int)
    assert count > 0


def test_truncate_to_token_limit_uses_default_encoding_for_unknown_models():
    text = 'abcdefghijklmnopqrstuvwxyz' * 10
    truncated = tokenizer_api.truncate_to_token_limit(text, 3, 'unknown-model-family')
    assert truncated
    assert tokenizer_api.count_tokens(truncated, 'unknown-model-family') <= 3
