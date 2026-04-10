"""Chat router — SSE streaming endpoint powered by the LangGraph ReAct agent.

POST /api/v1/chat accepts user messages in Greek, runs them through the
tool-calling chat agent (Claude Sonnet 4.6 + 5 structured DB tools), and
streams results as server-sent events.

## SSE event protocol (v2)

  data: {"type": "status", "step": "starting"|"tool_running"|"generating"}
  data: {"type": "tool_call_start", "id": "...", "name": "...", "display_el": "..."}
  data: {"type": "tool_call_result", "id": "...", "name": "...", "ok": true, "summary_el": "..."}
  data: {"type": "token", "content": "..."}       # Greek answer chunk
  data: {"type": "sources", "sources": [...]}      # citations (v1 compatible)
  data: {"type": "done", "thread_id": "..."}       # includes thread_id for conversation persistence
  data: {"type": "error", "content": "..."}

## Whitespace bug workaround

LangGraph's high-level graph events (on_chain_*) can corrupt Unicode token
boundaries, producing garbled Greek like "Ν ο μο θε τικό". This router
filters only `on_chat_model_stream` events for tokens — these come directly
from the Claude model's streaming API and are not corrupted. See
EducateBuddy's `legal-prep/legal_prep/api/routers/query.py` for the same
workaround documented.

## Phase 2C (memory)

The request accepts an optional `thread_id`. When the checkpointer is wired
(Phase 2C), this enables natural follow-up questions: "πόσα τιμολόγια;" →
"9" → "και από αυτά πόσα εγκρίθηκαν;" resolves "αυτά" via message history.
"""

from __future__ import annotations

import json
import uuid
from collections.abc import AsyncGenerator
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Request as FastAPIRequest, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from app.ai.chat_agent import get_chat_agent
from app.core.rate_limit import limiter
from app.ai.chat_tools import TOOL_DISPLAY_NAMES_EL
from app.core.config import settings
from app.core.logging import get_logger
from app.db.database import get_db  # noqa: F401 — kept for legacy imports

logger = get_logger(__name__)

router = APIRouter(prefix="/chat", tags=["chat"])


# ---------------------------------------------------------------------------
# Request / response schemas (v1 API compatibility preserved)
# ---------------------------------------------------------------------------


class ChatMessage(BaseModel):
    """A single chat message in the conversation history."""

    role: Literal["user", "assistant"] = Field(..., description="Message role")
    content: str = Field(..., min_length=1, description="Message content")


class ChatRequest(BaseModel):
    """Chat request with conversation history and optional thread ID."""

    messages: list[ChatMessage] = Field(
        ..., min_length=1, description="Conversation messages"
    )
    stream: bool = Field(default=True, description="Enable SSE streaming")
    thread_id: str | None = Field(
        default=None,
        description=(
            "Optional conversation thread ID for multi-turn memory (Phase 2C). "
            "If omitted, a new UUID is generated and returned in the `done` event."
        ),
    )


class ChatResponseSync(BaseModel):
    """Non-streaming chat response (rarely used in practice)."""

    content: str
    sources: list[dict[str, Any]]
    thread_id: str
    tools_called: list[str] = Field(default_factory=list, description="Tool names invoked by the agent")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _format_sse(data: dict[str, Any]) -> str:
    """Format a dict as an SSE data line (UTF-8, Greek-safe)."""
    return f"data: {json.dumps(data, ensure_ascii=False)}\n\n"


def _extract_text_from_chunk(chunk: Any) -> str:
    """Extract plain text from a LangChain AIMessageChunk.

    AIMessageChunk.content may be:
      - A simple string (older model backends)
      - A list of content blocks (Anthropic: [{"type": "text", "text": "..."},
        {"type": "tool_use", ...}])

    Only text blocks contribute to streaming output. Tool-use blocks are
    handled separately via on_tool_* events.
    """
    if chunk is None:
        return ""
    content = getattr(chunk, "content", None)
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for block in content:
            if isinstance(block, dict):
                if block.get("type") == "text":
                    parts.append(block.get("text", ""))
            elif hasattr(block, "text"):
                parts.append(block.text)
        return "".join(parts)
    return ""


def _build_tool_result_summary_el(name: str, result: Any) -> str:
    """Build a short Greek summary of a tool result for the UI chip.

    The summary appears as a tooltip/badge on the resolved tool chip.
    Falls back to a generic ✓ marker if the shape is unknown.
    """
    try:
        if name == "count_records" and isinstance(result, dict):
            n = result.get("count")
            if n is not None:
                return f"{n} εγγραφές"
        elif name == "aggregate_invoice_field" and isinstance(result, dict):
            value = result.get("value")
            metric = result.get("metric", "")
            currency = result.get("currency", "")
            if value is not None:
                fmt_value = f"{float(value):,.2f}".replace(",", "X").replace(
                    ".", ","
                ).replace("X", ".")
                return f"{metric} = {fmt_value} {currency}".strip()
        elif name == "group_by_dimension" and isinstance(result, list):
            return f"{len(result)} ομάδες"
        elif name == "search_records" and isinstance(result, list):
            return f"{len(result)} σχετικά"
        elif name == "get_record":
            if isinstance(result, dict) and "error" not in result:
                return "βρέθηκε"
            if isinstance(result, list):
                return f"{len(result)} matches"
    except Exception:
        pass
    return "✓"


def _build_sources_from_messages(agent_state: dict[str, Any]) -> list[dict[str, Any]]:
    """Extract source citations from completed agent run state.

    Walks the final messages looking for ToolMessages from `search_records`
    or `get_record` calls and builds a sources list for the UI. Gracefully
    handles missing/malformed state.
    """
    sources: list[dict[str, Any]] = []
    try:
        messages = agent_state.get("messages", []) if isinstance(agent_state, dict) else []
    except Exception:
        return sources

    seen_ids: set[str] = set()
    for msg in messages:
        name = getattr(msg, "name", None)
        if name not in ("search_records", "get_record"):
            continue
        content = getattr(msg, "content", None)
        if content is None:
            continue
        try:
            payload = json.loads(content) if isinstance(content, str) else content
        except json.JSONDecodeError:
            continue

        items = payload if isinstance(payload, list) else [payload]
        for item in items:
            if not isinstance(item, dict):
                continue
            rid = item.get("id")
            if not rid or rid in seen_ids:
                continue
            seen_ids.add(rid)
            sources.append(
                {
                    "record_id": rid,
                    "source_file": item.get("source_file"),
                    "record_type": item.get("record_type"),
                    "score": item.get("score"),
                }
            )
    return sources


# ---------------------------------------------------------------------------
# Main endpoint
# ---------------------------------------------------------------------------


@router.post("", response_model=None)
@limiter.limit("10/minute")
async def chat(request: FastAPIRequest, body: ChatRequest):
    """RAG-powered chat endpoint with SSE streaming via LangGraph agent.

    Phase 2A (v2):
      - Routes through LangGraph's create_react_agent prebuilt helper
      - 5 structured tools (count/aggregate/group_by/search/get)
      - Claude Sonnet 4.6 with native parallel tool calls
      - Greek system prompt enforcing "use tools for counts, never guess from RAG"
    """
    # Validate last message is from user
    if body.messages[-1].role != "user":
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Last message must be from user.",
        )

    if not settings.anthropic_api_key:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="AI service unavailable. ANTHROPIC_API_KEY not configured.",
        )

    # Build thread_id for conversation persistence (used in Phase 2C).
    # Always validate as UUID to prevent injection of arbitrary strings.
    thread_id = str(uuid.uuid4())
    if body.thread_id:
        try:
            uuid.UUID(body.thread_id)  # Validate format
            thread_id = body.thread_id
        except ValueError:
            pass  # Invalid format, use the fresh UUID

    if body.stream:
        return StreamingResponse(
            _stream_agent_response(body.messages, thread_id),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",  # Disable nginx buffering for SSE
            },
        )

    # Non-streaming path (kept for programmatic clients)
    return await _sync_agent_response(body.messages, thread_id)


# ---------------------------------------------------------------------------
# Streaming path — astream_events filter
# ---------------------------------------------------------------------------


async def _stream_agent_response(
    messages: list[ChatMessage],
    thread_id: str,
) -> AsyncGenerator[str, None]:
    """Stream a LangGraph agent run as SSE events.

    Filters `agent.astream_events(version="v2")` down to four event types we
    care about:
      - `on_chat_model_stream`  → token deltas (bypasses the whitespace bug)
      - `on_tool_start`          → tool_call_start SSE events
      - `on_tool_end`            → tool_call_result SSE events
      - `on_chain_end` (name="LangGraph") → final state for source extraction

    Parallel tool calls are handled naturally — multiple `on_tool_*` events
    can interleave based on their `run_id`.
    """
    try:
        agent = await get_chat_agent()
    except Exception as exc:
        logger.error("chat_agent_init_failed", error=str(exc))
        yield _format_sse(
            {
                "type": "error",
                "content": f"Αδυναμία φόρτωσης του AI agent: {exc}",
            }
        )
        yield _format_sse({"type": "done", "thread_id": thread_id})
        return

    # Convert ChatMessage → LangChain BaseMessage format
    # System prompt is already configured on the agent via prompt=
    try:
        from langchain_core.messages import AIMessage, HumanMessage
    except ImportError as exc:
        logger.error("langchain_import_failed", error=str(exc))
        yield _format_sse({"type": "error", "content": "LangChain not installed"})
        yield _format_sse({"type": "done", "thread_id": thread_id})
        return

    lc_messages = []
    for msg in messages:
        if msg.role == "user":
            lc_messages.append(HumanMessage(content=msg.content))
        else:
            lc_messages.append(AIMessage(content=msg.content))

    # LangGraph config — thread_id for checkpointer, recursion_limit caps
    # tool-calling iterations to prevent runaway loops and API cost spikes.
    # Default is 25; 10 is more than enough for our 5 tools.
    config = {
        "configurable": {
            "thread_id": thread_id,
        },
        "recursion_limit": 10,
    }

    yield _format_sse({"type": "status", "step": "starting"})

    final_state: dict[str, Any] = {}
    streamed_any_token = False
    tool_calls_in_flight: dict[str, str] = {}  # run_id → tool name

    try:
        async for event in agent.astream_events(
            {"messages": lc_messages},
            config=config,
            version="v2",
        ):
            event_kind = event.get("event", "")
            event_name = event.get("name", "")
            run_id = event.get("run_id", "")
            data = event.get("data", {})

            # -------------------------------
            # Token streaming from the model
            # -------------------------------
            if event_kind == "on_chat_model_stream":
                chunk = data.get("chunk")
                text = _extract_text_from_chunk(chunk)
                if text:
                    streamed_any_token = True
                    yield _format_sse({"type": "token", "content": text})

            # -------------------------------
            # Tool lifecycle events
            # -------------------------------
            elif event_kind == "on_tool_start":
                tool_name = event_name
                tool_calls_in_flight[run_id] = tool_name
                display_el = TOOL_DISPLAY_NAMES_EL.get(tool_name, tool_name)
                yield _format_sse(
                    {
                        "type": "tool_call_start",
                        "id": run_id,
                        "name": tool_name,
                        "display_el": display_el,
                    }
                )
                yield _format_sse({"type": "status", "step": "tool_running"})

            elif event_kind == "on_tool_end":
                tool_name = tool_calls_in_flight.pop(run_id, event_name)
                output = data.get("output")
                # Tool output may be a ToolMessage with .content, or the raw result
                result_value: Any = None
                ok = True
                try:
                    if hasattr(output, "content"):
                        raw = output.content
                        if isinstance(raw, str):
                            try:
                                result_value = json.loads(raw)
                            except json.JSONDecodeError:
                                result_value = raw
                        else:
                            result_value = raw
                    else:
                        result_value = output
                except Exception as exc:
                    logger.warning("tool_result_parse_failed", error=str(exc))
                    result_value = None
                    ok = False

                summary_el = _build_tool_result_summary_el(tool_name, result_value)
                yield _format_sse(
                    {
                        "type": "tool_call_result",
                        "id": run_id,
                        "name": tool_name,
                        "ok": ok,
                        "summary_el": summary_el,
                    }
                )
                if not tool_calls_in_flight:
                    yield _format_sse({"type": "status", "step": "generating"})

            # -------------------------------
            # Final state — used for sources extraction
            # -------------------------------
            elif event_kind == "on_chain_end" and event_name == "LangGraph":
                output = data.get("output", {})
                if isinstance(output, dict):
                    final_state = output

    except Exception as exc:
        logger.error("chat_stream_error", error=str(exc), exc_type=type(exc).__name__)
        yield _format_sse(
            {
                "type": "error",
                "content": f"Σφάλμα κατά τη ροή απάντησης: {type(exc).__name__}",
            }
        )
        yield _format_sse({"type": "done", "thread_id": thread_id})
        return

    # Fallback: if no tokens were streamed (edge case), try to emit the full
    # answer from the final state as a single token chunk. This should not
    # normally happen with on_chat_model_stream events, but guards against
    # unexpected LangGraph versions.
    if not streamed_any_token and final_state:
        try:
            messages_out = final_state.get("messages", [])
            last = messages_out[-1] if messages_out else None
            if last is not None:
                fallback_text = _extract_text_from_chunk(last)
                if fallback_text:
                    logger.info("chat_stream_fallback_to_final_state")
                    yield _format_sse({"type": "token", "content": fallback_text})
        except Exception:
            pass

    # Extract source citations from the agent's tool messages
    sources = _build_sources_from_messages(final_state)
    yield _format_sse({"type": "sources", "sources": sources})
    yield _format_sse({"type": "done", "thread_id": thread_id})


# ---------------------------------------------------------------------------
# Non-streaming path — used by tests and programmatic clients
# ---------------------------------------------------------------------------


async def _sync_agent_response(
    messages: list[ChatMessage],
    thread_id: str,
) -> ChatResponseSync:
    """Collect the full agent response synchronously (no streaming).

    Used primarily by the golden-set pytest runner (Phase 2D), where we want
    to assert on the complete final answer + tool sequence without parsing SSE.
    """
    try:
        agent = await get_chat_agent()
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Chat agent unavailable: {exc}",
        ) from exc

    try:
        from langchain_core.messages import AIMessage, HumanMessage
    except ImportError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"LangChain not installed: {exc}",
        ) from exc

    lc_messages = []
    for msg in messages:
        if msg.role == "user":
            lc_messages.append(HumanMessage(content=msg.content))
        else:
            lc_messages.append(AIMessage(content=msg.content))

    config = {"configurable": {"thread_id": thread_id}, "recursion_limit": 10}

    try:
        final_state = await agent.ainvoke(
            {"messages": lc_messages},
            config=config,
        )
    except Exception as exc:
        logger.error("chat_sync_error", error=str(exc), exc_type=type(exc).__name__)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Agent execution failed: {type(exc).__name__}",
        ) from exc

    # Extract the final answer from the last AI message
    messages_out = final_state.get("messages", [])
    answer = ""
    for msg in reversed(messages_out):
        if getattr(msg, "type", "") == "ai":
            answer = _extract_text_from_chunk(msg)
            if answer:
                break

    sources = _build_sources_from_messages(final_state)

    # Extract tool names from agent message history
    tools_called: list[str] = []
    for msg in messages_out:
        tc = getattr(msg, "tool_calls", None)
        if tc:
            for call in tc:
                name = call.get("name") if isinstance(call, dict) else getattr(call, "name", None)
                if name:
                    tools_called.append(name)

    return ChatResponseSync(
        content=answer,
        sources=sources,
        thread_id=thread_id,
        tools_called=tools_called,
    )
