from app.services import tokenizer as tokenizer_api


def test_count_tokens_falls_back_without_tiktoken(monkeypatch):
    monkeypatch.setattr(tokenizer_api, 'tiktoken', None)
    assert tokenizer_api.count_tokens('abcdefgh', 'gpt-5.4') == 2


def test_truncate_to_token_limit_falls_back_without_tiktoken(monkeypatch):
    monkeypatch.setattr(tokenizer_api, 'tiktoken', None)
    text = 'abcdefghijklmnopqrstuvwxyz'
    assert tokenizer_api.truncate_to_token_limit(text, 3, 'gpt-5.4') == text[:12]
