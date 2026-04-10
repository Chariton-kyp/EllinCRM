"""Golden-set regression tests for the v2 chat agent (HTTP-based).

Loads ``tests/golden/chat_queries.yaml`` and asserts, for each entry:

  1. The agent calls all expected tools (``tools_called`` field).
  2. The agent does NOT call any forbidden tools.
  3. The final answer contains all required substrings (case-insensitive).
  4. The final answer contains none of the forbidden substrings.

Prerequisites
-------------
These tests hit the **running** backend via HTTP, so the Docker dev stack
must be up (``docker compose --profile dev up``) with the database seeded
(25 records) and ``ANTHROPIC_API_KEY`` configured.

Running
-------
::

    cd backend
    pytest tests/test_chat_golden.py -v -m integration          # all queries
    pytest tests/test_chat_golden.py -v -m integration -k "aggregate"  # subset
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import httpx
import pytest
import yaml

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

BACKEND_URL = "http://localhost:7000/api/v1/chat"

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
# Parametrized test
# ---------------------------------------------------------------------------


@pytest.mark.integration
@pytest.mark.asyncio
@pytest.mark.parametrize(
    "golden",
    GOLDEN_QUERIES,
    ids=[q["id"] for q in GOLDEN_QUERIES],
)
async def test_golden_query(golden: dict[str, Any]) -> None:
    """Run a single golden query against the HTTP endpoint and assert expectations."""
    query = golden["query"]
    expected_tools: list[str] = golden.get("expected_tools", [])
    forbidden_tools: list[str] = golden.get("forbidden_tools", [])
    must_contain: list[str] = golden.get("must_contain", [])
    must_not_contain: list[str] = golden.get("must_not_contain", [])

    async with httpx.AsyncClient(timeout=60.0) as client:
        resp = await client.post(
            BACKEND_URL,
            json={
                "messages": [{"role": "user", "content": query}],
                "stream": False,
            },
        )

    assert resp.status_code == 200, (
        f"[{golden['id']}] HTTP {resp.status_code}: {resp.text[:300]}"
    )

    data = resp.json()
    tools_called: list[str] = data.get("tools_called", [])
    answer: str = data.get("content", "")
    answer_lower = answer.lower()

    # 1. Expected tools must all appear (order-independent)
    for expected in expected_tools:
        assert expected in tools_called, (
            f"[{golden['id']}] expected tool {expected!r} not called. "
            f"Called: {tools_called}. Answer: {answer[:200]!r}"
        )

    # 2. Forbidden tools must NOT appear
    for forbidden in forbidden_tools:
        assert forbidden not in tools_called, (
            f"[{golden['id']}] forbidden tool {forbidden!r} was called. "
            f"Called: {tools_called}. Answer: {answer[:200]!r}"
        )

    # 3. Must-contain substrings (case-insensitive)
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


@pytest.mark.integration
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
