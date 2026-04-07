"""LiteLLM Router — single AI provider abstraction layer.

Provides a multi-model LLM router with automatic retries and fallback.
Ported from the browser extension project, trimmed to 3 models for EllinCRM:
  - gemini-flash  (Gemini 3.1 Flash — extraction)
  - claude-sonnet (Claude Sonnet 4.6 — chat)
  - claude-haiku  (Claude Haiku 4.5 — fallback)

All AI provider keys are loaded from server-side environment variables only.
NEVER import direct provider SDKs (anthropic, google-genai) elsewhere in the codebase.
"""

import logging

from app.core.config import settings

logger = logging.getLogger(__name__)

# Module-level reference (set by init_ai_router during startup)
ai_router = None


def create_ai_router():
    """Build and return a configured LiteLLM Router instance.

    Wrapped in a function to avoid import-time failures when API keys are not set.
    """
    from litellm import Router

    model_list = [
        # --- Gemini (extraction) ---
        {
            "model_name": "gemini-flash",
            "litellm_params": {
                "model": "gemini/gemini-3.1-flash-preview",
                "api_key": settings.google_api_key,
            },
        },
        # --- Claude (chat + fallback) ---
        {
            "model_name": "claude-sonnet",
            "litellm_params": {
                "model": "anthropic/claude-sonnet-4-6",
                "api_key": settings.anthropic_api_key,
            },
        },
        {
            "model_name": "claude-haiku",
            "litellm_params": {
                "model": "anthropic/claude-haiku-4-5-20251001",
                "api_key": settings.anthropic_api_key,
            },
        },
    ]

    return Router(
        model_list=model_list,
        num_retries=2,
        timeout=30,
    )


def init_ai_router() -> None:
    """Initialize the module-level ai_router. Call during app startup."""
    global ai_router
    try:
        ai_router = create_ai_router()
        logger.info(
            "LiteLLM AI router initialized with 3 models: "
            "gemini-flash, claude-sonnet, claude-haiku"
        )
    except Exception as exc:
        logger.warning(
            "LiteLLM AI router init failed (non-fatal — AI features disabled): %s",
            exc,
        )
        ai_router = None


def get_ai_router():
    """Return the module-level AI router instance (or None if not initialized)."""
    return ai_router
