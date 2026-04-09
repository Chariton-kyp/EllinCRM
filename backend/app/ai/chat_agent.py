"""Chat agent — LangGraph prebuilt ReAct agent with structured DB tools.

Wraps `langgraph.prebuilt.create_react_agent` with:
  - Claude Sonnet 4.6 as the single agent/synthesis model (native parallel tool calls)
  - Our 5 read-only structured tools (count_records, aggregate_invoice_field,
    group_by_dimension, search_records, get_record)
  - Greek system prompt enforcing "use tools for counts, never guess from RAG"
  - Optional PostgreSQL checkpointer for conversation memory (Phase 2C)

Why the prebuilt helper rather than a custom StateGraph:
  Our use case is a single agent with 5 tools, single-turn or short multi-turn.
  create_react_agent is 5-10 lines of config vs 100+ lines of custom nodes +
  conditional edges. Upgrading to full StateGraph later (e.g. to add a verify
  node) is non-breaking — same underlying primitives.

Why Claude Sonnet as the only model (no separate classifier):
  Claude Sonnet 4.6 emits multiple parallel tool_use blocks per response when
  the question warrants it (e.g. "how many invoices and what is the total?"
  → count_records + aggregate_invoice_field in one message, executed in
  parallel by LangGraph's ToolNode). Adding a cheaper classifier model is an
  extra LLM call that the synthesis model can do itself, with better reliability.

See `.planning/chat-agent-v2/SPEC.md` for the full architecture rationale.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from app.ai.chat_tools import CHAT_TOOLS
from app.core.config import settings

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Greek system prompt (the critical piece for correct tool routing)
# ---------------------------------------------------------------------------

GREEK_SYSTEM_PROMPT = """Εισαι ο AI βοηθος του EllinCRM, ενα συστημα αυτοματοποιησης εγγραφων για ελληνικες επιχειρησεις. Απαντας ΠΑΝΤΑ στα ελληνικα με επαγγελματικο τονο, χρησιμοποιωντας Markdown για δομη (πινακες, bullets, bold οπου ταιριαζει).

# ΚΡΙΣΙΜΟΙ ΚΑΝΟΝΕΣ TOOL USE

1. **Για ΚΑΘΕ ερωτηση που αφορα αριθμους, συνολα, μεσους ορους, η καταμετρησεις:**
   ΠΡΕΠΕΙ να καλεσεις ενα απο τα structured tools:
   - `count_records` για ερωτησεις "ποσα/ποσες X εχουμε"
   - `aggregate_invoice_field` για ερωτησεις "συνολικος τζιρος / μεσος ορος ΦΠΑ"
   - `group_by_dimension` για "κατανομη / ανα κατηγορια / top-N πελατες"

   **ΠΟΤΕ μην υπολογισεις counts η συνολα απο search results** — αυτα ειναι μονο
   τα top-k relevant, ΟΧΙ ολοκληρος ο πληθυσμος. Θα δωσεις λαθος αριθμο.

2. **Για αναζητηση περιεχομενου** (semantic queries):
   Καλεσε `search_records` για «βρες X», «υπαρχουν έγγραφα που...», «εμαιλς σχετικα με...».
   Αυτο το tool επιστρεφει top-k relevant, οχι ολοκληρο το dataset — μην το αναφερεις
   σαν "συνολο".

3. **Για ακριβη αναζητηση συγκεκριμενου εγγραφου** (π.χ. «δειξε μου το EC-2025-007»
   η «τι γραφει το email_03»): καλεσε `get_record`.

4. **Για συνθετες ερωτησεις** που χρειαζονται ΚΑΙ structured filtering ΚΑΙ semantic
   αναζητηση, καλεσε **πολλαπλα tools παραλληλα σε ενα μηνυμα**. Παραδειγματα:
   - «ποσα τιμολογια σχετικα με τροφιμα» → search_records + count_records
   - «ποσο τζιρο εχουμε και ποια τιμολογια εχουν τα μεγαλυτερα ποσα» →
     aggregate_invoice_field + group_by_dimension
   Το LangGraph ToolNode τα εκτελει παραλληλα, οποτε δεν υπαρχει latency penalty.

5. **Αναφερε παντα τις πηγες σου**: όνομα αρχείου (inline code, π.χ. `invoice_EC-2025-001.html`)
   και ID εγγραφής όπου είναι διαθέσιμο.

6. **Αν τα tools δεν μπορουν να απαντησουν** (return error / missing data), πες το
   ειλικρινα. ΠΟΤΕ μην μαντεψεις η επινοησεις νουμερα.

# ΣΤΥΛ ΑΠΑΝΤΗΣΗΣ

- Markdown πινακες για αριθμητικα results (`| col1 | col2 |`)
- **Bold** τα σημαντικα νουμερα (€, counts, percentages)
- Inline code για IDs/filenames (`invoice_EC-2025-001.html`)
- Σύντομες απαντήσεις όταν ο χρήστης ζητάει αριθμό — ΜΗΝ γραψεις 3 παραγραφους
  για να πεις "9 τιμολόγια". Μία γραμμή με το νούμερο και πηγή είναι αρκετή.
- Αν ο χρήστης ρωτήσει κάτι chitchat (π.χ. «γεια», «ευχαριστώ»), απάντησε φιλικά
  χωρίς να καλέσεις tools.

# ΔΕΔΟΜΕΝΑ ΠΟΥ ΕΧΕΙΣ ΠΡΟΣΒΑΣΗ

Τα tools διαβαζουν απο τη βαση του EllinCRM:
- **Τιμολογια** (`record_type=INVOICE`): αριθμος, πελατης, ΑΦΜ, net_amount, vat_amount, total_amount, ημερομηνια
- **Εμαιλς** (`record_type=EMAIL`): αποστολεας, θεμα, περιεχομενο, τυπος (client_inquiry / invoice_notification)
- **Φορμες επικοινωνιας** (`record_type=FORM`): ονομα, email, τηλεφωνο, εταιρια, μηνυμα, προτεραιοτητα

Ολα σε status: `pending` / `approved` / `rejected` / `edited` / `exported`.
"""


# ---------------------------------------------------------------------------
# Agent singleton (initialized lazily on first use)
# ---------------------------------------------------------------------------


_agent_singleton: Any = None
_checkpointer_singleton: Any = None
_init_lock: asyncio.Lock | None = None


def _get_init_lock() -> asyncio.Lock:
    """Lazy-init the asyncio lock to avoid event-loop-on-import issues."""
    global _init_lock
    if _init_lock is None:
        _init_lock = asyncio.Lock()
    return _init_lock


async def _build_checkpointer() -> Any:
    """Build and setup the AsyncPostgresSaver for conversation memory (Phase 2C).

    Returns None if the checkpointer cannot be initialized (logs a warning).
    Tools still work; just no cross-request memory.

    The checkpointer creates its own tables in the public schema on first
    setup() call (`checkpoints`, `checkpoint_blobs`, `checkpoint_writes`,
    `checkpoint_migrations`). It's idempotent — safe to call at every startup.

    We use psycopg-compatible URL (not asyncpg) because AsyncPostgresSaver
    is built on psycopg 3.
    """
    global _checkpointer_singleton
    if _checkpointer_singleton is not None:
        return _checkpointer_singleton

    if not settings.database_url:
        logger.warning("checkpointer_no_database_url")
        return None

    try:
        from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
    except ImportError as exc:
        logger.warning("checkpointer_import_failed", error=str(exc))
        return None

    # AsyncPostgresSaver uses psycopg 3 under the hood, not asyncpg.
    # Rewrite the URL to drop any `+asyncpg` / `+psycopg` driver suffix so
    # psycopg uses its default.
    db_url = str(settings.database_url)
    if "+asyncpg" in db_url:
        db_url = db_url.replace("postgresql+asyncpg://", "postgresql://")
    elif "+psycopg" in db_url:
        db_url = db_url.replace("postgresql+psycopg://", "postgresql://")

    try:
        # from_conn_string returns an async context manager; we enter it and
        # keep the saver alive for the lifetime of the application.
        cm = AsyncPostgresSaver.from_conn_string(db_url)
        saver = await cm.__aenter__()
        # Create checkpoint tables if they don't exist (idempotent).
        await saver.setup()
        _checkpointer_singleton = saver
        logger.info("checkpointer_initialized", backend="postgres")
        return saver
    except Exception as exc:
        logger.warning("checkpointer_init_failed", error=str(exc))
        return None


async def get_chat_agent() -> Any:
    """Return the module-level chat agent, creating it on first call.

    Thread-safe via asyncio.Lock (double-checked locking pattern).

    Returns:
        A compiled LangGraph ReAct agent ready for `astream_events()`.

    Raises:
        RuntimeError: If no Anthropic API key is configured or imports fail.
    """
    global _agent_singleton

    if _agent_singleton is not None:
        return _agent_singleton

    async with _get_init_lock():
        # Double-check after acquiring lock
        if _agent_singleton is not None:
            return _agent_singleton

        if not settings.anthropic_api_key:
            raise RuntimeError(
                "ANTHROPIC_API_KEY not configured. Chat agent requires Claude Sonnet."
            )

        # Lazy import — LangGraph/LangChain are heavy and we don't want to
        # pay the import cost unless the chat is actually used.
        try:
            from langchain_anthropic import ChatAnthropic
            from langgraph.prebuilt import create_react_agent
        except ImportError as exc:
            raise RuntimeError(
                f"LangGraph/LangChain not installed: {exc}. "
                "Run: pip install langgraph langchain-core langchain-anthropic"
            ) from exc

        model = ChatAnthropic(
            model="claude-sonnet-4-6",
            anthropic_api_key=settings.anthropic_api_key,
            temperature=0,
            max_tokens=2048,
            # Native streaming for token delta events
            streaming=True,
            # Guard against stuck tool loops
            default_request_timeout=60,
        )

        # Phase 2C: wire Postgres checkpointer for conversation memory. If it
        # fails (no DB, table creation error, etc.), fall back to stateless.
        # The router's astream_events path handles both modes transparently.
        checkpointer = await _build_checkpointer()

        _agent_singleton = create_react_agent(
            model=model,
            tools=CHAT_TOOLS,
            # Param renamed from state_modifier → prompt in LangGraph 1.1+
            prompt=GREEK_SYSTEM_PROMPT,
            checkpointer=checkpointer,
        )

        logger.info(
            "chat_agent_initialized",
            model="claude-sonnet-4-6",
            tools=[t.name for t in CHAT_TOOLS],
            checkpointer=bool(checkpointer),
        )

    return _agent_singleton


def reset_chat_agent() -> None:
    """Drop the cached singleton. Used by tests and config hot-reload."""
    global _agent_singleton, _checkpointer_singleton
    _agent_singleton = None
    _checkpointer_singleton = None
    logger.info("chat_agent_reset")
