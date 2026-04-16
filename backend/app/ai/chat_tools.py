"""Chat agent tools — structured DB queries exposed as LangChain tools.

The chat agent uses these five tools to answer user questions deterministically:

  1. `count_records`         — COUNT(*) with filters
  2. `aggregate_invoice_field` — SUM/AVG/MIN/MAX on invoice numeric fields (JSONB)
  3. `group_by_dimension`    — GROUP BY with count/sum aggregation
  4. `search_records`        — Hybrid search wrapper (semantic + keyword)
  5. `get_record`            — Exact lookup by UUID or source filename

Why structured tools instead of text-to-SQL:
  - Deterministic: tool parameters are type-checked Pydantic Literals
  - Safe: runs against a read-only SQLAlchemy session with statement_timeout=3s
  - Observable: each call is a known function, trivially logged and unit-tested
  - Injection-proof: LLM only chooses tool + params, never writes SQL
  - Correct by construction for the aggregate-query failure mode (see SPEC.md §1)

All tools are async and return JSON-serializable dicts/lists that Claude can
incorporate into its Greek answer without additional processing.

Data model note:
  Records live in `extraction_records` with `extracted_data JSONB`. Invoice
  numeric fields (total_amount, net_amount, vat_amount) are JSONB path
  extractions that require an explicit NUMERIC cast. We use raw SQL via
  `sqlalchemy.text()` with bound parameters for clarity and performance.
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Any, Literal
from uuid import UUID

from langchain_core.tools import tool
from sqlalchemy import text

from app.core.logging import get_logger
from app.db.readonly_session import get_readonly_session

logger = get_logger(__name__)

# Hard cap on any list-returning tool — prevents accidental full-table dumps
MAX_RESULT_LIMIT = 200
DEFAULT_LIST_LIMIT = 50


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _coerce_decimal(value: Any) -> float | None:
    """Coerce a numeric-looking value to float for JSON serialization."""
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, Decimal):
        return float(value)
    try:
        return float(value)
    except (ValueError, TypeError):
        return None


def _format_filters_summary(
    record_type: str | None,
    status: str | None,
    date_from: str | None,
    date_to: str | None,
    customer_vat: str | None,
) -> str:
    """Build a human-readable Greek summary of applied filters for logging/SSE."""
    parts: list[str] = []
    if record_type:
        type_el = {"FORM": "φόρμες", "EMAIL": "emails", "INVOICE": "τιμολόγια"}
        parts.append(type_el.get(record_type, record_type))
    if status:
        status_el = {
            "pending": "εκκρεμείς",
            "approved": "εγκεκριμένες",
            "rejected": "απορριφθείσες",
            "edited": "επεξεργασμένες",
            "exported": "εξαχθείσες",
        }
        parts.append(status_el.get(status, status))
    if date_from or date_to:
        parts.append(f"από {date_from or '...'} έως {date_to or '...'}")
    if customer_vat:
        parts.append(f"πελάτης ΑΦΜ {customer_vat}")
    return ", ".join(parts) if parts else "χωρίς φίλτρα"


def _build_where_clause(
    record_type: str | None,
    status: str | None,
    date_from: date | str | None,
    date_to: date | str | None,
    customer_vat: str | None,
) -> tuple[str, dict[str, Any]]:
    """Build a reusable WHERE clause + bound params for filtering extraction_records.

    All conditions are null-safe: a None filter doesn't narrow the result set.
    Returns (sql_fragment, params_dict).
    """
    conditions: list[str] = ["1=1"]
    params: dict[str, Any] = {}

    if record_type is not None:
        conditions.append("record_type = :record_type")
        params["record_type"] = record_type

    if status is not None:
        conditions.append("status = :status")
        params["status"] = status

    if date_from is not None:
        conditions.append("created_at >= :date_from")
        params["date_from"] = date_from

    if date_to is not None:
        conditions.append("created_at <= :date_to")
        params["date_to"] = date_to

    if customer_vat is not None:
        conditions.append("extracted_data->>'client_vat_number' = :customer_vat")
        params["customer_vat"] = customer_vat

    return " AND ".join(conditions), params


# ---------------------------------------------------------------------------
# Tool 1: count_records
# ---------------------------------------------------------------------------


@tool
async def count_records(
    record_type: Literal["FORM", "EMAIL", "INVOICE"] | None = None,
    status: Literal["pending", "approved", "rejected", "edited", "exported"] | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    customer_vat: str | None = None,
) -> dict[str, Any]:
    """Count records in the EllinCRM database with optional filters.

    Use this tool for questions like:
      - "Πόσα τιμολόγια έχουμε;" → count_records(record_type="INVOICE")
      - "Πόσες εκκρεμείς εγγραφές;" → count_records(status="pending")
      - "Πόσα emails εγκρίθηκαν τον Μάρτιο;" → count_records(record_type="EMAIL", status="approved", date_from="2026-03-01", date_to="2026-03-31")

    Args:
        record_type: Filter by document type (FORM/EMAIL/INVOICE). None = all types.
        status: Filter by workflow status. None = all statuses.
        date_from: ISO date (YYYY-MM-DD). Only records created on/after this date.
        date_to: ISO date (YYYY-MM-DD). Only records created on/before this date.
        customer_vat: Greek VAT number (ΑΦΜ). Only matches invoices for this customer.

    Returns:
        {"count": int, "filters_applied": str (Greek summary)}
    """
    where_sql, params = _build_where_clause(record_type, status, date_from, date_to, customer_vat)
    sql = text(f"SELECT COUNT(*) AS n FROM extraction_records WHERE {where_sql}")

    async with get_readonly_session() as session:
        result = await session.execute(sql, params)
        row = result.one()
        count_val = int(row.n)

    filters_summary = _format_filters_summary(record_type, status, date_from, date_to, customer_vat)
    logger.info(
        "chat_tool_count_records",
        count=count_val,
        filters=filters_summary,
    )
    return {
        "count": count_val,
        "filters_applied": filters_summary,
    }


# ---------------------------------------------------------------------------
# Tool 2: aggregate_invoice_field
# ---------------------------------------------------------------------------


@tool
async def aggregate_invoice_field(
    field: Literal["total_amount", "net_amount", "vat_amount"],
    metric: Literal["sum", "avg", "min", "max"],
    status: Literal["pending", "approved", "rejected", "edited", "exported"] | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    customer_vat: str | None = None,
) -> dict[str, Any]:
    """Compute an aggregate (sum/avg/min/max) over an invoice numeric field.

    Use this tool for questions like:
      - "Ποιο είναι το συνολικό ποσό των τιμολογίων;" → aggregate_invoice_field(field="total_amount", metric="sum")
      - "Ποιος είναι ο μέσος όρος τιμολογίων;" → aggregate_invoice_field(field="total_amount", metric="avg")
      - "Πόσο ΦΠΑ οφείλουμε στα εγκεκριμένα;" → aggregate_invoice_field(field="vat_amount", metric="sum", status="approved")

    Only operates on records with record_type='INVOICE' (automatically filtered).
    Fields are extracted from extracted_data JSONB with numeric type casting.

    Args:
        field: Numeric field to aggregate (total_amount, net_amount, vat_amount).
        metric: Aggregation function (sum/avg/min/max).
        status: Optional workflow status filter.
        date_from/date_to: Optional date range (ISO YYYY-MM-DD).
        customer_vat: Optional customer filter by VAT number.

    Returns:
        {"value": float|None, "count": int, "metric": str, "field": str,
         "currency": "EUR", "filters_applied": str}
    """
    # Runtime allowlists — defense in depth beyond Pydantic Literal validation.
    # Direct callers (tests, future code) may bypass LangChain's schema check.
    ALLOWED_FIELDS = {"total_amount", "net_amount", "vat_amount"}
    if field not in ALLOWED_FIELDS:
        return {
            "error": "invalid_field",
            "field": field,
            "value": None,
            "count": 0,
            "metric": metric,
            "currency": "EUR",
            "filters_applied": "",
        }

    agg_fn_map = {"sum": "SUM", "avg": "AVG", "min": "MIN", "max": "MAX"}
    if metric not in agg_fn_map:
        return {
            "error": "invalid_metric",
            "field": field,
            "value": None,
            "count": 0,
            "metric": metric,
            "currency": "EUR",
            "filters_applied": "",
        }
    agg_fn = agg_fn_map[metric]

    # Always filter to invoices for this tool
    where_sql, params = _build_where_clause(
        record_type="INVOICE",
        status=status,
        date_from=date_from,
        date_to=date_to,
        customer_vat=customer_vat,
    )

    # JSONB extraction + numeric cast. Rows with non-numeric values become NULL,
    # which are naturally ignored by SQL aggregate functions.
    #
    # NOTE: This regex assumes JSONB numeric values use period as decimal
    # separator (e.g. "2418.00", not "2.418,00"). This is guaranteed by the
    # Gemini Flash extraction layer which normalizes all amounts to
    # period-decimal format. If a future extractor produces comma-decimal
    # values, this regex will silently produce 100x errors.
    # See: backend/app/services/llm_extractor.py INVOICE_SYSTEM_PROMPT
    sql = text(
        f"""
        SELECT
            COUNT(extracted_data->>'{field}') AS n,
            {agg_fn}(
                NULLIF(regexp_replace(extracted_data->>'{field}', '[^0-9.\\-]', '', 'g'), '')::NUMERIC
            ) AS agg_value
        FROM extraction_records
        WHERE {where_sql}
          AND extracted_data ? '{field}'
        """
    )

    async with get_readonly_session() as session:
        result = await session.execute(sql, params)
        row = result.one()
        value = _coerce_decimal(row.agg_value)
        count_val = int(row.n)

    filters_summary = _format_filters_summary("INVOICE", status, date_from, date_to, customer_vat)
    logger.info(
        "chat_tool_aggregate_invoice_field",
        field=field,
        metric=metric,
        value=value,
        count=count_val,
        filters=filters_summary,
    )
    return {
        "field": field,
        "metric": metric,
        "value": value,
        "count": count_val,
        "currency": "EUR",
        "filters_applied": filters_summary,
    }


# ---------------------------------------------------------------------------
# Tool 3: group_by_dimension
# ---------------------------------------------------------------------------


@tool
async def group_by_dimension(
    dimension: Literal["status", "record_type", "month", "client_vat"],
    metric: Literal["count", "sum_total_amount", "avg_total_amount"] = "count",
    record_type: Literal["FORM", "EMAIL", "INVOICE"] | None = None,
    limit: int = DEFAULT_LIST_LIMIT,
) -> list[dict[str, Any]]:
    """Group records by a dimension and aggregate.

    Use this tool for questions like:
      - "Κατανομή τιμολογίων ανά κατάσταση" → group_by_dimension(dimension="status", record_type="INVOICE")
      - "Πόσα έγγραφα ανά τύπο έχουμε;" → group_by_dimension(dimension="record_type")
      - "Ποιος πελάτης έχει τον μεγαλύτερο τζίρο;" → group_by_dimension(dimension="client_vat", metric="sum_total_amount", record_type="INVOICE")
      - "Εγγραφές ανά μήνα" → group_by_dimension(dimension="month")

    The `sum_total_amount` and `avg_total_amount` metrics are only meaningful
    for INVOICE records (they operate on extracted_data->>'total_amount').
    When used with other record types, they return None values.

    Args:
        dimension: Grouping field. 'month' groups by month(created_at); 'client_vat'
            groups by JSONB client_vat_number + includes client_name.
        metric: What to compute per group.
        record_type: Optional filter before grouping.
        limit: Max groups to return (capped at MAX_RESULT_LIMIT).

    Returns:
        List of dicts, each with {key, label (Greek), count, sum_total_amount (opt)}.
    """
    limit = min(max(limit, 1), MAX_RESULT_LIMIT)

    # Dimension → SQL SELECT expression + GROUP BY expression
    if dimension == "status":
        key_expr = "status"
        label_expr = "status"
        group_expr = "status"
    elif dimension == "record_type":
        key_expr = "record_type"
        label_expr = "record_type"
        group_expr = "record_type"
    elif dimension == "month":
        key_expr = "to_char(date_trunc('month', created_at), 'YYYY-MM')"
        label_expr = key_expr
        group_expr = "date_trunc('month', created_at)"
    elif dimension == "client_vat":
        key_expr = "extracted_data->>'client_vat_number'"
        label_expr = (
            "COALESCE(extracted_data->>'client_name', extracted_data->>'client_vat_number')"
        )
        group_expr = "extracted_data->>'client_vat_number', extracted_data->>'client_name'"
    else:
        # Literal enforces this, but keep a safety branch
        return []

    # Metric → aggregate expression
    if metric == "count":
        agg_expr = "COUNT(*) AS metric_value"
        order_expr = "COUNT(*) DESC"
    elif metric == "sum_total_amount":
        agg_expr = "SUM(NULLIF(regexp_replace(extracted_data->>'total_amount', '[^0-9.\\-]', '', 'g'), '')::NUMERIC) AS metric_value"
        order_expr = "metric_value DESC NULLS LAST"
    elif metric == "avg_total_amount":
        agg_expr = "AVG(NULLIF(regexp_replace(extracted_data->>'total_amount', '[^0-9.\\-]', '', 'g'), '')::NUMERIC) AS metric_value"
        order_expr = "metric_value DESC NULLS LAST"
    else:
        return []

    # Optional record_type filter
    where_conditions = ["1=1"]
    params: dict[str, Any] = {"limit": limit}
    if record_type is not None:
        where_conditions.append("record_type = :record_type")
        params["record_type"] = record_type
    if dimension == "client_vat":
        where_conditions.append("extracted_data->>'client_vat_number' IS NOT NULL")

    where_sql = " AND ".join(where_conditions)

    sql = text(
        f"""
        SELECT
            {key_expr} AS group_key,
            {label_expr} AS group_label,
            COUNT(*) AS count,
            {agg_expr if metric != "count" else "NULL AS metric_value"}
        FROM extraction_records
        WHERE {where_sql}
        GROUP BY {group_expr}
        ORDER BY {order_expr}
        LIMIT :limit
        """
    )

    async with get_readonly_session() as session:
        result = await session.execute(sql, params)
        rows = result.all()

    output: list[dict[str, Any]] = []
    for row in rows:
        group_key = row.group_key
        group_label = row.group_label
        count_val = int(row.count)
        metric_val = _coerce_decimal(row.metric_value) if metric != "count" else count_val

        output.append(
            {
                "key": str(group_key) if group_key is not None else None,
                "label": str(group_label) if group_label is not None else None,
                "count": count_val,
                "metric": metric_val,
                "metric_name": metric,
            }
        )

    logger.info(
        "chat_tool_group_by_dimension",
        dimension=dimension,
        metric=metric,
        groups=len(output),
    )
    return output


# ---------------------------------------------------------------------------
# Tool 4: search_records (hybrid semantic + keyword)
# ---------------------------------------------------------------------------


@tool
async def search_records(
    query: str,
    top_k: int = 5,
    record_type: Literal["FORM", "EMAIL", "INVOICE"] | None = None,
) -> list[dict[str, Any]]:
    """Hybrid semantic + keyword search over EllinCRM records.

    Use this tool for content-based questions like:
      - "Βρες emails σχετικά με GDPR ή προστασία δεδομένων"
      - "Δείξε μου τιμολόγια από ελληνικές κατασκευαστικές εταιρίες"
      - "Υπάρχουν πελάτες που ζητούν on-premise εγκατάσταση;"

    Do NOT use this for counts, sums, or aggregations — use count_records,
    aggregate_invoice_field, or group_by_dimension instead. This tool returns
    only the top_k most relevant candidates, NOT the full matching population.

    Args:
        query: Natural-language search query (Greek or English).
        top_k: Number of results to return (1-20, default 5).
        record_type: Optional filter to a single record type.

    Returns:
        List of top_k records with {id, source_file, record_type, score, snippet}.
    """
    from app.ai.embeddings import get_embedding_service, get_embedding_status
    from app.ai.hybrid_search import HybridSearchService

    top_k = max(1, min(top_k, 20))

    embedding_status = get_embedding_status()
    if not embedding_status["is_ready"]:
        logger.warning(
            "chat_tool_search_embedding_not_ready",
            status=embedding_status["status"],
        )
        return [
            {
                "error": "embedding_not_ready",
                "message": "Το μοντέλο embeddings δεν είναι ακόμα έτοιμο. Δοκιμάστε ξανά σε λίγο.",
            }
        ]

    embedding_service = get_embedding_service()

    # Run hybrid search AND enrich with source_file/record_type in the same session.
    # hybrid_search natively supports record_type filtering via its signature.
    async with get_readonly_session() as session:
        search_service = HybridSearchService(session, embedding_service)
        try:
            results = await search_service.hybrid_search(
                query=query,
                limit=top_k,
                min_similarity=0.15,
                record_type=record_type,
            )
        except Exception as exc:
            logger.error("chat_tool_search_failed", error=str(exc))
            return [{"error": "search_failed", "message": str(exc)[:200]}]

        # Enrich raw results (which only have record_id + content_text + scores)
        # with source_file, record_type, and status via a single bulk lookup.
        record_ids = [r["record_id"] for r in results if r.get("record_id")]
        enrichment: dict[str, dict[str, Any]] = {}
        if record_ids:
            enrich_sql = text(
                "SELECT id::text AS id, source_file, record_type, status "
                "FROM extraction_records "
                "WHERE id::text = ANY(:ids)"
            )
            enrich_rows = (await session.execute(enrich_sql, {"ids": record_ids})).all()
            enrichment = {
                str(row.id): {
                    "source_file": row.source_file,
                    "record_type": row.record_type,
                    "status": row.status,
                }
                for row in enrich_rows
            }

    # Build a clean response shape the LLM can cite
    output: list[dict[str, Any]] = []
    for r in results[:top_k]:
        rid = r.get("record_id")
        meta = enrichment.get(rid, {})
        score = r.get("combined_score", r.get("semantic_score", 0.0))
        snippet = (r.get("content_text") or "")[:300]
        output.append(
            {
                "id": rid,
                "source_file": meta.get("source_file"),
                "record_type": meta.get("record_type"),
                "status": meta.get("status"),
                "score": round(float(score), 4) if score is not None else None,
                "snippet": snippet,
            }
        )

    logger.info(
        "chat_tool_search_records",
        query=query[:60],
        record_type=record_type,
        returned=len(output),
    )
    return output


# ---------------------------------------------------------------------------
# Tool 5: get_record
# ---------------------------------------------------------------------------


@tool
async def get_record(
    record_id: str | None = None,
    source_file: str | None = None,
) -> dict[str, Any] | list[dict[str, Any]]:
    """Exact lookup of a record by UUID or source filename.

    Use this tool when the user references a specific document by ID or
    filename, like:
      - "Δείξε μου το τιμολόγιο EC-2025-007" → get_record(source_file="invoice_EC-2025-007.html")
      - "Τι γράφει το email_03;" → get_record(source_file="email_03.eml")
      - "Το record με ID abc-123" → get_record(record_id="abc-123")

    If both arguments are given, record_id takes precedence. If neither is
    given, returns an error.

    Args:
        record_id: UUID of the record (exact match).
        source_file: Source filename or substring (ILIKE match, first 10 hits).

    Returns:
        For record_id: a single dict with all record fields.
        For source_file: a list of matching records (0-10).
    """
    if record_id is None and source_file is None:
        return {"error": "missing_argument", "message": "Provide either record_id or source_file."}

    async with get_readonly_session() as session:
        if record_id is not None:
            try:
                uid = UUID(record_id)
            except ValueError:
                return {"error": "invalid_uuid", "message": f"'{record_id}' is not a valid UUID."}

            sql = text(
                "SELECT id::text, source_file, record_type, status, confidence_score, "
                "extracted_data, created_at, updated_at "
                "FROM extraction_records WHERE id = :id"
            )
            result = await session.execute(sql, {"id": uid})
            row = result.first()
            if row is None:
                return {"error": "not_found", "message": f"No record with id {record_id}"}
            return _row_to_dict(row)

        # source_file path
        sql = text(
            "SELECT id::text, source_file, record_type, status, confidence_score, "
            "extracted_data, created_at, updated_at "
            "FROM extraction_records "
            "WHERE source_file ILIKE :pattern "
            "ORDER BY created_at DESC "
            "LIMIT 10"
        )
        result = await session.execute(sql, {"pattern": f"%{source_file}%"})
        rows = result.all()

    records = [_row_to_dict(row) for row in rows]
    logger.info(
        "chat_tool_get_record",
        record_id=record_id,
        source_file=source_file,
        found=len(records),
    )
    return (
        records if source_file is not None else (records[0] if records else {"error": "not_found"})
    )


def _row_to_dict(row: Any) -> dict[str, Any]:
    """Serialize a SQLAlchemy row to a JSON-safe dict."""

    def _iso(value: Any) -> Any:
        if isinstance(value, datetime):
            return value.isoformat()
        return value

    return {
        "id": row.id,
        "source_file": row.source_file,
        "record_type": row.record_type,
        "status": row.status,
        "confidence_score": _coerce_decimal(row.confidence_score),
        "extracted_data": row.extracted_data,
        "created_at": _iso(row.created_at),
        "updated_at": _iso(row.updated_at),
    }


# ---------------------------------------------------------------------------
# Tool registry — imported by the agent builder
# ---------------------------------------------------------------------------


CHAT_TOOLS = [
    count_records,
    aggregate_invoice_field,
    group_by_dimension,
    search_records,
    get_record,
]
"""Ordered list of all chat tools for LangGraph's create_react_agent."""


# Greek display names for SSE tool_call_start events
TOOL_DISPLAY_NAMES_EL: dict[str, str] = {
    "count_records": "Μετράω εγγραφές",
    "aggregate_invoice_field": "Υπολογίζω σύνολα τιμολογίων",
    "group_by_dimension": "Ομαδοποιώ αποτελέσματα",
    "search_records": "Αναζήτηση σε έγγραφα",
    "get_record": "Ανάκτηση εγγραφής",
}
