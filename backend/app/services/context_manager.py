"""Context management: model resolution and token budgeting.

Bridges the platform's provider settings to LangChain BaseChatModel instances
for use with DeepAgents, and provides token-aware context budgeting utilities.
"""

from __future__ import annotations

from langchain_core.language_models import BaseChatModel
from langchain_openai import ChatOpenAI

from app.services.settings import get_settings, resolve_role_model


# Known context window sizes per model family (tokens).
# Used for budget allocation when litellm metadata is unavailable.
MODEL_CONTEXT_WINDOWS: dict[str, int] = {
    "gpt-4.1": 1_047_576,
    "gpt-4.1-mini": 1_047_576,
    "gpt-4.1-nano": 1_047_576,
    "gpt-4o": 128_000,
    "gpt-4o-mini": 128_000,
    "gpt-5.3-codex": 1_047_576,
    "claude-sonnet-4-6": 200_000,
    "claude-opus-4-6": 200_000,
}

DEFAULT_CONTEXT_WINDOW = 128_000
COMPRESSION_THRESHOLD = 0.85  # trigger compression at 85% of window


def _sanitize_null_content(payload: dict) -> dict:
    """Replace null content with empty strings in the serialized API payload.

    Many OpenAI-compatible servers (LM Studio, llama.cpp, etc.) use Jinja
    templates that crash on null message content. The OpenAI API spec allows
    null content on tool-call assistant messages, but these servers can't
    handle it. Patching at the payload level (after LangChain serialization)
    ensures nothing slips through.
    """
    for msg in payload.get("messages", []):
        if msg.get("content") is None:
            msg["content"] = ""
    return payload


class _NullContentSanitizer(ChatOpenAI):
    """ChatOpenAI that patches null content in the final API payload."""

    def _get_request_payload(self, input_, *, stop=None, **kwargs):
        payload = super()._get_request_payload(input_, stop=stop, **kwargs)
        return _sanitize_null_content(payload)


def resolve_langchain_model(settings: dict, role: str) -> BaseChatModel:
    """Convert platform provider settings for a role into a LangChain model.

    Supports: openai, openai_compatible, z_ai_coding providers.
    All are OpenAI-compatible and use ChatOpenAI with appropriate base_url.
    Uses _NullContentSanitizer for compatible providers that may choke on
    null content in tool-call messages.
    """
    role_cfg = resolve_role_model(settings, role) or {}
    provider = role_cfg.get("provider") or settings.get("default", {}).get("provider") or "openai"
    model = role_cfg.get("model") or settings.get("default", {}).get("model") or ""
    providers = settings.get("providers", {})

    if provider == "openai":
        cfg = providers.get("openai", {})
        api_key = cfg.get("api_key") or ""
        base_url = cfg.get("base_url") or "https://api.openai.com/v1"
        # Use sanitizer if pointing to a non-OpenAI base URL
        is_native_openai = "api.openai.com" in base_url
        cls = ChatOpenAI if is_native_openai else _NullContentSanitizer
        return cls(
            model=model,
            api_key=api_key,
            base_url=base_url.rstrip("/"),
            temperature=0.2,
        )
    elif provider in ("openai_compatible", "z_ai_coding"):
        cfg = providers.get(provider, {})
        api_key = cfg.get("api_key") or ""
        base_url = (cfg.get("base_url") or "").rstrip("/")
        effective_model = model or cfg.get("model") or ""
        return _NullContentSanitizer(
            model=effective_model,
            api_key=api_key,
            base_url=base_url,
            temperature=0.2,
        )
    else:
        raise ValueError(f"Unsupported provider for LangChain model: {provider}")


def get_context_window(model_name: str) -> int:
    """Look up the context window size for a model."""
    for key, size in MODEL_CONTEXT_WINDOWS.items():
        if key in model_name:
            return size
    return DEFAULT_CONTEXT_WINDOW


def compute_token_budget(model_name: str, reserved_for_response: int = 4096) -> dict:
    """Compute available token budget for a model.

    Returns dict with:
        - context_window: total tokens available
        - response_reserve: tokens reserved for model response
        - available: tokens available for input (system + messages + tools)
        - compression_trigger: token count at which compression should fire
    """
    window = get_context_window(model_name)
    available = window - reserved_for_response
    trigger = int(available * COMPRESSION_THRESHOLD)
    return {
        "context_window": window,
        "response_reserve": reserved_for_response,
        "available": available,
        "compression_trigger": trigger,
    }
