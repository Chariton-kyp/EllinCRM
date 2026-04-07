"""Chat router — streaming SSE endpoint for RAG-powered AI chat agent.

POST /api/v1/chat accepts user messages in Greek, retrieves relevant
extraction records via hybrid search, and streams Claude Sonnet responses
with source citations.

SSE stream format:
  data: {"type": "token", "content": "..."}
  data: {"type": "sources", "sources": [...]}
  data: {"type": "done"}

Rate limiting: Not implemented for demo — add middleware for production.
"""

import json
import logging
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.ai_router import get_ai_router
from app.db.database import get_db
from app.services.rag_service import RAGService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/chat", tags=["chat"])

# --- System prompt (Greek) ---
SYSTEM_PROMPT = (
    "Εισαι ο AI βοηθος του EllinCRM. Απαντα στα ελληνικα. "
    "Χρησιμοποιησε μονο τα δεδομενα που σου δινονται. "
    "Αναφερε τις πηγες σου (ονομα αρχειου και ID). "
    "Αν δεν βρεις σχετικα δεδομενα, πες το ειλικρινα."
)

# Fallback chain: claude-sonnet -> claude-haiku -> gemini-flash
CHAT_FALLBACK_CHAIN = ["claude-sonnet", "claude-haiku", "gemini-flash"]


# --- Pydantic models ---

class ChatMessage(BaseModel):
    """A single chat message."""
    role: Literal["user", "assistant"] = Field(..., description="Message role")
    content: str = Field(..., min_length=1, description="Message content")


class ChatRequest(BaseModel):
    """Chat request with conversation history."""
    messages: list[ChatMessage] = Field(
        ..., min_length=1, description="Conversation messages"
    )
    stream: bool = Field(default=True, description="Enable SSE streaming")


class ChatResponseSync(BaseModel):
    """Non-streaming chat response."""
    content: str
    sources: list[dict[str, Any]]


# --- Helpers ---

def _format_sse(data: dict[str, Any]) -> str:
    """Format a dict as an SSE data line."""
    return f"data: {json.dumps(data, ensure_ascii=False)}\n\n"


def _build_llm_messages(
    conversation: list[ChatMessage],
    context_string: str,
) -> list[dict[str, str]]:
    """Build the messages array for the LLM call.

    Includes system prompt, RAG context, and full conversation history.
    """
    messages: list[dict[str, str]] = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "system", "content": f"Σχετικα δεδομενα:\n{context_string}"},
    ]
    for msg in conversation:
        messages.append({"role": msg.role, "content": msg.content})
    return messages


# --- Endpoint ---

@router.post("", response_model=None)
async def chat(
    request: ChatRequest,
    db: AsyncSession = Depends(get_db),
):
    """RAG-powered chat endpoint with SSE streaming.

    Accepts conversation messages, retrieves relevant extraction records
    via hybrid search, and returns AI responses from Claude Sonnet.
    Falls back to claude-haiku then gemini-flash if primary model fails.
    """
    # Validate last message is from user
    if request.messages[-1].role != "user":
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Last message must be from user.",
        )

    # Get AI router
    ai_router = get_ai_router()
    if ai_router is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="AI service unavailable. No API keys configured.",
        )

    # Extract user question and retrieve RAG context
    question = request.messages[-1].content
    rag_service = RAGService(db)
    context_string, sources = await rag_service.retrieve_context(question, limit=5)

    # Build LLM messages
    llm_messages = _build_llm_messages(request.messages, context_string)

    if request.stream:
        return StreamingResponse(
            _stream_response(ai_router, llm_messages, sources),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            },
        )
    else:
        return await _sync_response(ai_router, llm_messages, sources)


async def _stream_response(
    ai_router: Any,
    llm_messages: list[dict[str, str]],
    sources: list[dict[str, Any]],
):
    """Generator that yields SSE events for streaming chat response."""
    response = None
    last_error = None

    for model in CHAT_FALLBACK_CHAIN:
        try:
            response = await ai_router.acompletion(
                model=model,
                messages=llm_messages,
                stream=True,
                timeout=60,
            )
            break
        except Exception as exc:
            logger.warning("chat_stream_model_failed, model=%s: %s", model, exc)
            last_error = exc
            continue

    if response is None:
        yield _format_sse({
            "type": "error",
            "content": "Δεν είναι δυνατή η σύνδεση με το AI μοντέλο. Ελέγξτε ότι τα API keys (GOOGLE_API_KEY, ANTHROPIC_API_KEY) είναι ρυθμισμένα στο .env αρχείο.",
        })
        yield _format_sse({"type": "done"})
        return

    try:
        async for chunk in response:
            choices = getattr(chunk, "choices", None)
            if not choices:
                continue
            delta = choices[0].delta
            content = getattr(delta, "content", None)
            if content:
                yield _format_sse({"type": "token", "content": content})
    except Exception as exc:
        logger.error("chat_stream_error: %s", exc)
        yield _format_sse({"type": "error", "content": "Σφάλμα κατά τη ροή απάντησης. Παρακαλώ δοκιμάστε ξανά."})

    # Send sources after streaming completes
    yield _format_sse({"type": "sources", "sources": sources})
    yield _format_sse({"type": "done"})


async def _sync_response(
    ai_router: Any,
    llm_messages: list[dict[str, str]],
    sources: list[dict[str, Any]],
) -> ChatResponseSync:
    """Non-streaming chat response with fallback chain."""
    last_error = None

    for model in CHAT_FALLBACK_CHAIN:
        try:
            response = await ai_router.acompletion(
                model=model,
                messages=llm_messages,
                timeout=60,
            )
            content = response.choices[0].message.content or ""
            if model != CHAT_FALLBACK_CHAIN[0]:
                logger.info("chat_sync_fallback: %s -> %s", CHAT_FALLBACK_CHAIN[0], model)
            return ChatResponseSync(content=content, sources=sources)
        except Exception as exc:
            logger.warning("chat_sync_model_failed, model=%s: %s", model, exc)
            last_error = exc
            continue

    raise HTTPException(
        status_code=status.HTTP_502_BAD_GATEWAY,
        detail=f"All AI models failed. Last error: {last_error}",
    )
