"""Shared AI completion helper with JSON parsing, fallback chains, and clean errors.

Ported from browser extension's ai_call.py, trimmed to 3 models for EllinCRM.
Uses any-llm (Mozilla.ai) under the hood via AIRouter — LiteLLM was removed
after the March 2026 TeamPCP supply-chain compromise (CVE-2026-35029).
"""

import asyncio
import json
import logging

from fastapi import HTTPException, status

from app.ai.ai_router import get_ai_router

# any-llm v1 only exports a subset of exception classes. Timeouts come from
# asyncio.TimeoutError (enforced by AIRouter via asyncio.wait_for), and
# connection errors bubble up as the underlying provider SDK's exceptions —
# both are handled by the string-sniffing fallback below.
try:
    from any_llm.exceptions import (  # type: ignore[import]
        AuthenticationError as _AnyLLMAuthenticationError,
    )
    from any_llm.exceptions import (
        RateLimitError as _AnyLLMRateLimitError,
    )

    _ANY_LLM_EXCEPTIONS = True
except ImportError:
    _ANY_LLM_EXCEPTIONS = False

logger = logging.getLogger(__name__)

# When a model fails, try these fallbacks in order
FALLBACK_CHAIN = {
    "gemini-flash": ["claude-haiku", "claude-sonnet"],
    "claude-sonnet": ["gemini-flash", "claude-haiku"],
    "claude-haiku": ["gemini-flash", "claude-sonnet"],
}

# User-friendly error messages
ERROR_MESSAGES = {
    "RateLimitError": "Rate limit reached for {model}. {fallback_msg}",
    "AuthenticationError": "API key invalid for {model}. Please check your API keys in the backend .env file.",
    "Timeout": "Request to {model} timed out. {fallback_msg}",
    "APIConnectionError": "Could not connect to {model} API. {fallback_msg}",
}


def strip_code_fences(text: str) -> str:
    """Strip markdown code fences (```json ... ```) from AI responses."""
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.split("\n", 1)[1] if "\n" in cleaned else cleaned[3:]
    if cleaned.endswith("```"):
        cleaned = cleaned[:-3].rstrip()
    return cleaned


async def ai_completion_json(
    messages: list[dict],
    model: str,
    timeout: int = 30,
) -> tuple[dict, str]:
    """Call AI model and parse JSON response, with automatic fallback.

    Returns:
        Tuple of (parsed_json_dict, model_actually_used)

    Raises:
        HTTPException 503 if AI router is not initialized.
        HTTPException 502 if all models fail.
    """
    router = get_ai_router()
    if router is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="AI service unavailable. No API keys configured.",
        )

    models_to_try = [model] + FALLBACK_CHAIN.get(model, [])
    last_error = None
    raw_content = ""

    for attempt_model in models_to_try:
        try:
            response = await router.acompletion(
                model=attempt_model,
                messages=messages,
                response_format={"type": "json_object"},
                timeout=timeout,
            )
            raw_content = response.choices[0].message.content or ""
            cleaned = strip_code_fences(raw_content)
            parsed = json.loads(cleaned)

            if attempt_model != model:
                logger.info("Fallback succeeded: %s -> %s", model, attempt_model)

            return parsed, attempt_model

        except json.JSONDecodeError as exc:
            logger.error(
                "JSON parse failure from %s: %s | raw=%s",
                attempt_model,
                exc,
                repr(raw_content[:200]) if raw_content else "<EMPTY>",
            )
            last_error = f"AI returned invalid JSON from {attempt_model}"
            continue

        except Exception as exc:
            error_type = type(exc).__name__
            exc_str = str(exc)

            # Rate-limit and auth are classified via any-llm's typed exceptions
            # when available. Timeouts come from asyncio.TimeoutError (AIRouter
            # wraps every call in asyncio.wait_for). Connection errors are
            # provider-SDK specific and caught via string-sniffing.
            if isinstance(exc, asyncio.TimeoutError):
                core_type = "Timeout"
            elif _ANY_LLM_EXCEPTIONS and isinstance(exc, _AnyLLMRateLimitError):
                core_type = "RateLimitError"
            elif _ANY_LLM_EXCEPTIONS and isinstance(exc, _AnyLLMAuthenticationError):
                core_type = "AuthenticationError"
            elif "RateLimitError" in error_type or "429" in exc_str:
                core_type = "RateLimitError"
            elif "AuthenticationError" in error_type or "401" in exc_str:
                core_type = "AuthenticationError"
            elif "Timeout" in error_type or "timeout" in exc_str.lower():
                core_type = "Timeout"
            elif "APIConnectionError" in error_type or "ConnectionError" in error_type:
                core_type = "APIConnectionError"
            else:
                core_type = error_type

            logger.warning(
                "AI call failed (%s, %s): %s",
                attempt_model,
                core_type,
                exc_str[:200],
            )
            last_error = (core_type, attempt_model)
            continue

    # All models failed — return a clean error
    if isinstance(last_error, tuple):
        core_type, failed_model = last_error
        template = ERROR_MESSAGES.get(
            core_type,
            "AI request failed for {model}: " + core_type + ". {fallback_msg}",
        )
        fallback_msg = (
            "All fallback models also failed."
            if len(models_to_try) > 1
            else "Try a different model."
        )
        detail = template.format(model=model, fallback_msg=fallback_msg)
    else:
        detail = last_error or "AI request failed. Please try again."

    raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=detail)
