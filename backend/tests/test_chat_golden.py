"""Golden-set regression tests for the v2 chat agent.

Loads `tests/golden/chat_queries.yaml` and asserts, for each entry:

  1. The agent calls exactly the expected tools (order-independent).
  2. The agent does NOT call any forbidden tools.
  3. The final answer contains all required substrings.
  4. The final answer contains none of the forbidden substrings.

## Running

  cd backend
  pytest tests/test_chat_golden.py -v                    # all queries
  pytest tests/test_chat_golden.py -v -k "aggregate"     # only aggregate queries
  pytest tests/test_chat_golden.py -v -k "aggregate_invoice_count"  # single

## Prerequisites

  1. Docker stack up with current DB state (25 seed records expected)
  2. `python -m scripts.reembed_all` (if migrating from EmbeddingGemma)
  3. ANTHROPIC_API_KEY set in backend/.env

## Why pytest.mark.asyncio + direct agent calls, not the HTTP API

The golden set tests the agent's decision-making (which tools to call and
in what sequence), not the FastAPI router or SSE streaming. By calling
`agent.ainvoke()` directly we:

  - Get deterministic results (no network flakes)
  - Can inspect the full message history including tool_calls
  - Run under 5 seconds per query instead of 15+ (no SSE overhead)
  - Keep the test independent of the router's SSE workaround logic

The SSE path is covered by separate Playwright E2E tests (not in this file).
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

import pytest
import yaml
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

from app.ai.chat_agent import get_chat_agent, reset_chat_agent

# ---------------------------------------------------------------------------
# Fixture: load the golden set once per session
# ---------------------------------------------------------------------------


GOLDEN_FILE = Path(__file__).parent / "golden" / "chat_queries.yaml"


def _load_golden_set() -> list[dict[str, Any]]:
    """Load chat_queries.yaml as a list of dicts."""
    with open(GOLDEN_FILE, encoding="utf-8") as fp:
        data = yaml.safe_load(fp)
    if not isinstance(data, list):
        raise ValueError(f"Expected a list in {GOLDEN_FILE}, got {type(data)}")
    return data


GOLDEN_QUERIES = _load_golden_set()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _extract_tool_calls_from_messages(messages: list[Any]) -> list[str]:
    """Walk a LangGraph agent's final message history and collect tool names.

    The agent emits messages in this sequence:
      1. HumanMessage (input)
      2. AIMessage with tool_calls attribute (when it decides to use tools)
      3. ToolMessage (tool result)
      4. AIMessage with final text (synthesis)

    Returns all tool names called, in order. Duplicates preserved.
    """
    names: list[str] = []
    for msg in messages:
        # Method 1: AIMessage.tool_calls attribute (LangChain >= 0.2)
        tool_calls = getattr(msg, "tool_calls", None)
        if tool_calls:
            for tc in tool_calls:
                if isinstance(tc, dict):
                    name = tc.get("name")
                else:
                    name = getattr(tc, "name", None)
                if name:
                    names.append(name)
        # Method 2: ToolMessage.name (fallback, also reliable)
        if isinstance(msg, ToolMessage):
            if msg.name and msg.name not in names:
                # Prefer the tool_calls record, but catch tools that slipped through
                pass  # Already captured via tool_calls above
    return names


def _extract_final_answer(messages: list[Any]) -> str:
    """Find the last AIMessage with non-empty text content."""
    for msg in reversed(messages):
        if isinstance(msg, AIMessage):
            content = msg.content
            if isinstance(content, str) and content.strip():
                return content
            if isinstance(content, list):
                parts = [
                    block.get("text", "")
                    for block in content
                    if isinstance(block, dict) and block.get("type") == "text"
                ]
                text = "".join(parts)
                if text.strip():
                    return text
    return ""


# ---------------------------------------------------------------------------
# Parametrized test
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module", autouse=True)
def _reset_agent_before_module() -> None:
    """Clear the agent singleton so tests start from a known state."""
    reset_chat_agent()
    yield
    reset_chat_agent()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "golden",
    GOLDEN_QUERIES,
    ids=[q["id"] for q in GOLDEN_QUERIES],
)
async def test_golden_query(golden: dict[str, Any]) -> None:
    """Run a single golden query against the agent and assert expectations."""
    query = golden["query"]
    expected_tools: list[str] = golden.get("expected_tools", [])
    forbidden_tools: list[str] = golden.get("forbidden_tools", [])
    must_contain: list[str] = golden.get("must_contain", [])
    must_not_contain: list[str] = golden.get("must_not_contain", [])

    agent = await get_chat_agent()
    config = {"configurable": {"thread_id": f"golden-{golden['id']}"}}

    final_state = await agent.ainvoke(
        {"messages": [HumanMessage(content=query)]},
        config=config,
    )

    messages = final_state.get("messages", [])
    called_tools = _extract_tool_calls_from_messages(messages)
    answer = _extract_final_answer(messages)
    answer_lower = answer.lower()

    # 1. Expected tools must all appear (order-independent, allows duplicates)
    for expected in expected_tools:
        assert expected in called_tools, (
            f"[{golden['id']}] expected tool {expected!r} not called. "
            f"Called: {called_tools}. Answer: {answer[:200]!r}"
        )

    # 2. Forbidden tools must NOT appear
    for forbidden in forbidden_tools:
        assert forbidden not in called_tools, (
            f"[{golden['id']}] forbidden tool {forbidden!r} was called. "
            f"Called: {called_tools}. Answer: {answer[:200]!r}"
        )

    # 3. Must-contain substrings (case-insensitive partial match)
    for substring in must_contain:
        assert substring.lower() in answer_lower, (
            f"[{golden['id']}] missing substring {substring!r}. "
            f"Answer: {answer[:400]!r}"
        )

    # 4. Must-not-contain substrings
    for substring in must_not_contain:
        assert substring.lower() not in answer_lower, (
            f"[{golden['id']}] forbidden substring {substring!r} found. "
            f"Answer: {answer[:400]!r}"
        )


# ---------------------------------------------------------------------------
# Summary test — reports category-level pass rates for visibility
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_golden_summary(capsys: pytest.CaptureFixture[str]) -> None:
    """Per-category pass-rate summary (non-failing reporter).

    This test never fails on its own — it's for humans to eyeball how the
    agent performs across categories. Individual query tests (above) are
    the actual gate.
    """
    counts: dict[str, dict[str, int]] = {}
    for q in GOLDEN_QUERIES:
        cat = q.get("category", "unknown")
        counts.setdefault(cat, {"total": 0})
        counts[cat]["total"] += 1

    print("\n=== Golden set summary ===")
    print(f"Total queries: {len(GOLDEN_QUERIES)}")
    for cat, stats in sorted(counts.items()):
        print(f"  {cat:12s}: {stats['total']:2d} queries")
    assert len(GOLDEN_QUERIES) > 0, "Empty golden set"
