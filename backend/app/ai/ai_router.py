"""any-llm model dispatcher — replaces LiteLLM Router.

Ported after the March 2026 LiteLLM supply-chain compromise (TeamPCP):
  v1.82.7/1.82.8 were poisoned credential stealers (CVE-2026-35029,
  GHSA-69x8-hrgq-fjj8) that exfiltrated env vars, SSH keys, and cloud
  credentials via a compromised Trivy step in LiteLLM's CI pipeline.

Uses Mozilla.ai's any-llm, which calls the official anthropic + google-genai
SDKs directly — no central proxy, no Router component to poison.

Call-site contract is identical to the old LiteLLM Router:
    await ai_router.acompletion(model="gemini-flash", messages=..., **kwargs)
No callers (routers, services) need any changes.
"""

import logging
from typing import Any

from any_llm import acompletion as _any_llm_acompletion

from app.core.config import settings

logger = logging.getLogger(__name__)

# Logical name → (provider, provider-specific model id)
MODEL_REGISTRY: dict[str, tuple[str, str]] = {
    "gemini-flash":  ("gemini",    "gemini-3.1-flash-preview"),
    "claude-sonnet": ("anthropic", "claude-sonnet-4-6"),
    "claude-haiku":  ("anthropic", "claude-haiku-4-5-20251001"),
}

_API_KEY_BY_PROVIDER: dict[str, Any] = {
    "anthropic": lambda: settings.anthropic_api_key,
    "gemini":    lambda: settings.google_api_key,
}


class AIRouter:
    """Thin dispatcher matching the old LiteLLM Router.acompletion shape.

    Accepts the same kwargs as before (messages, response_format, stream,
    timeout). any-llm normalizes to OpenAI chunk shape on streaming, so
    callers reading choices[0].delta.content need no changes.
    """

    def __init__(self, registry: dict[str, tuple[str, str]]):
        self._registry = registry

    async def acompletion(self, *, model: str, **kwargs: Any):
        try:
            provider, model_id = self._registry[model]
        except KeyError as exc:
            raise ValueError(
                f"Unknown model '{model}'. Known: {list(self._registry)}"
            ) from exc
        api_key = _API_KEY_BY_PROVIDER[provider]()
        return await _any_llm_acompletion(
            provider=provider,
            model=model_id,
            api_key=api_key,
            **kwargs,
        )


# Module-level reference — set by init_ai_router() during startup
ai_router: AIRouter | None = None


def create_ai_router() -> AIRouter:
    """Validate API keys and return a configured AIRouter instance."""
    if not (settings.anthropic_api_key or settings.google_api_key):
        raise RuntimeError(
            "No LLM API keys configured (ANTHROPIC_API_KEY / GOOGLE_API_KEY)."
        )
    return AIRouter(MODEL_REGISTRY)


def init_ai_router() -> None:
    """Initialize the module-level ai_router. Called during app startup."""
    global ai_router
    try:
        ai_router = create_ai_router()
        logger.info("any_llm_router_initialized, models=%s", list(MODEL_REGISTRY))
    except Exception as exc:
        logger.warning("any_llm_router_init_failed (non-fatal — AI features disabled): %s", exc)
        ai_router = None


def get_ai_router() -> AIRouter | None:
    """Return the module-level AI router instance (or None if not initialized)."""
    return ai_router
