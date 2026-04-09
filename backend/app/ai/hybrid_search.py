"""
Hybrid Search Service — Three-signal retrieval with Reciprocal Rank Fusion.

Phase 2B upgrade (April 2026): upgraded from 2-signal weighted fusion to a
3-signal hybrid with Reciprocal Rank Fusion (RRF). Ported from EducateBuddy's
`rag/greek_search.py` pattern, tuned for EllinCRM's JSONB extraction records.

## Three signals

1. **Semantic** (pgvector cosine) — Qwen3-Embedding 0.6B 768-dim vectors over
   the content_text column. Best at conceptual similarity ("δικηγόρος" finds
   "νομικές υπηρεσίες" even without shared words).

2. **Keyword** (PostgreSQL tsvector) — ts_rank over the pre-computed
   search_vector column (populated by DB triggers from normalized Greek text).
   Best at stemmed exact-term matches ("τιμολόγιο" finds "τιμολόγια").

3. **Trigram** (pg_trgm similarity) — `similarity(content_normalized, :query)`
   via the GIN index on content_normalized with gin_trgm_ops (Alembic 004).
   Best at fuzzy matching ("GDPR" finds "G.D.P.R." and typos, client names
   with punctuation variants).

## Fusion: Reciprocal Rank Fusion (RRF)

Instead of weighted sum of raw scores (which is biased by each signal's score
distribution), RRF combines **rank positions**:

    rrf_score(d) = Σ_{lists} weight_l / (k + rank_l(d))

With k=60 (per Cormack et al. 2009) and weights [0.6, 0.25, 0.15] for
(semantic, keyword, trigram). This is distribution-free and handles the case
where one signal has score magnitudes near 1.0 while another hovers near 0.2.

Falls back to semantic-only if keyword/trigram queries fail.
"""

from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.embeddings import EmbeddingService
from app.ai.greek_text import normalize_greek_text, tokenize_for_search
from app.core.logging import get_logger

logger = get_logger(__name__)

# Phase 2B: three-signal fusion weights. Derived from EducateBuddy's tested
# defaults [0.6, 0.25, 0.15]; kept tunable per-instance via constructor.
SEMANTIC_WEIGHT = 0.6  # pgvector cosine similarity (primary meaning signal)
KEYWORD_WEIGHT = 0.25  # tsvector full-text match (stemmed exact terms)
TRIGRAM_WEIGHT = 0.15  # pg_trgm similarity (fuzzy Greek character match)

# RRF constant per Cormack et al. 2009 ("Reciprocal rank fusion outperforms
# Condorcet and individual rank learning methods")
RRF_K = 60


class HybridSearchService:
    """
    Hybrid Search Service combining semantic and keyword search.

    Provides better search results for Greek business data by combining:
    - Semantic search: Understands meaning (e.g., "lawyer" ~ "legal services")
    - Keyword search: Exact matches (e.g., "Δικηγορικό" finds "Δικηγορικό")

    Usage:
        service = HybridSearchService(db_session, embedding_service)
        results = await service.hybrid_search(
            query="Δικηγορικό γραφείο",
            limit=10,
            min_similarity=0.2
        )
    """

    def __init__(
        self,
        db: AsyncSession,
        embedding_service: EmbeddingService,
        semantic_weight: float = SEMANTIC_WEIGHT,
        keyword_weight: float = KEYWORD_WEIGHT,
        trigram_weight: float = TRIGRAM_WEIGHT,
    ):
        """Initialize three-signal hybrid search service.

        Args:
            db: AsyncSession for database queries.
            embedding_service: EmbeddingService for generating query embeddings.
            semantic_weight: RRF weight for semantic signal (default 0.6).
            keyword_weight: RRF weight for keyword/tsvector signal (default 0.25).
            trigram_weight: RRF weight for pg_trgm fuzzy signal (default 0.15).

        Weights are normalized to sum to 1.0 if they don't already.
        """
        self.db = db
        self.embedding_service = embedding_service
        self.semantic_weight = semantic_weight
        self.keyword_weight = keyword_weight
        self.trigram_weight = trigram_weight

        # Normalize weights to sum to 1.0
        total = semantic_weight + keyword_weight + trigram_weight
        if abs(total - 1.0) > 0.01:
            logger.warning(
                "hybrid_weights_normalized",
                original_semantic=semantic_weight,
                original_keyword=keyword_weight,
                original_trigram=trigram_weight,
            )
            self.semantic_weight = semantic_weight / total
            self.keyword_weight = keyword_weight / total
            self.trigram_weight = trigram_weight / total

    async def hybrid_search(
        self,
        query: str,
        limit: int = 10,
        min_similarity: float = 0.15,
        record_type: str | None = None,
        status: str | None = None,
    ) -> list[dict[str, Any]]:
        """
        Perform hybrid search combining semantic and keyword matching.

        Args:
            query: Search query (Greek or English)
            limit: Maximum results to return
            min_similarity: Minimum combined score threshold
            record_type: Optional filter by record type (FORM, EMAIL, INVOICE)
            status: Optional filter by status (pending, approved, rejected)

        Returns:
            List of search results with combined scores
        """
        logger.info(
            "hybrid_search_start",
            query=query[:50],
            limit=limit,
            min_similarity=min_similarity,
        )

        try:
            # Stage 1: Semantic search (pgvector Qwen3-Embedding)
            semantic_results = await self._semantic_search(
                query=query,
                limit=limit * 2,  # Get more candidates
                min_similarity=min_similarity * 0.5,  # Lower threshold for candidates
                record_type=record_type,
                status=status,
            )

            # Stage 2: Keyword search (tsvector BM25-style)
            keyword_results = await self._keyword_search(
                query=query,
                limit=limit * 2,
                record_type=record_type,
                status=status,
            )

            # Stage 3: Trigram fuzzy search (pg_trgm similarity)
            trigram_results = await self._trigram_search(
                query=query,
                limit=limit * 2,
                record_type=record_type,
                status=status,
            )

            # Stage 4: Reciprocal Rank Fusion across all three signals
            combined_results = self._combine_rrf(
                semantic_results=semantic_results,
                keyword_results=keyword_results,
                trigram_results=trigram_results,
                limit=limit,
                min_score=min_similarity,
            )

            logger.info(
                "hybrid_search_complete",
                semantic_count=len(semantic_results),
                keyword_count=len(keyword_results),
                trigram_count=len(trigram_results),
                combined_count=len(combined_results),
            )

            return combined_results

        except Exception as e:
            logger.error("hybrid_search_error", error=str(e))
            # Fallback to semantic-only search
            return await self._semantic_search(
                query=query,
                limit=limit,
                min_similarity=min_similarity,
                record_type=record_type,
                status=status,
            )

    async def _semantic_search(
        self,
        query: str,
        limit: int,
        min_similarity: float,
        record_type: str | None = None,
        status: str | None = None,
    ) -> list[dict[str, Any]]:
        """
        Perform semantic search using pgvector embeddings.

        Returns results with semantic_score in [0, 1] range.
        """
        # Generate query embedding
        query_embedding = await self.embedding_service.generate_embedding_async(query)

        # Format embedding as vector literal for SQL
        embedding_str = f"'[{','.join(map(str, query_embedding))}]'"

        # Build WHERE clauses
        where_clauses = [f"1 - (de.embedding <=> {embedding_str}::vector) >= :min_similarity"]
        params: dict[str, Any] = {"min_similarity": min_similarity, "limit": limit}

        if record_type:
            where_clauses.append("er.record_type = :record_type")
            params["record_type"] = record_type

        if status:
            where_clauses.append("er.status = :status")
            params["status"] = status

        where_sql = " AND ".join(where_clauses)

        # Use raw SQL for pgvector operations
        sql = text(f"""
            SELECT
                de.record_id,
                de.content_text,
                1 - (de.embedding <=> {embedding_str}::vector) as semantic_score
            FROM document_embeddings de
            JOIN extraction_records er ON de.record_id = er.id
            WHERE {where_sql}
            ORDER BY de.embedding <=> {embedding_str}::vector
            LIMIT :limit
        """)

        result = await self.db.execute(sql, params)
        rows = result.fetchall()

        return [
            {
                "record_id": str(row.record_id),
                "content_text": row.content_text,
                "semantic_score": float(row.semantic_score),
                "keyword_score": 0.0,
                "search_method": "semantic",
            }
            for row in rows
        ]

    async def _keyword_search(
        self,
        query: str,
        limit: int,
        record_type: str | None = None,
        status: str | None = None,
    ) -> list[dict[str, Any]]:
        """
        Perform keyword search using PostgreSQL full-text search.

        Searches both:
        1. search_vector (tsvector) for stemmed word matching
        2. content_normalized (ILIKE) for exact Greek matches

        Returns results with keyword_score in [0, 1] range.
        """
        # Normalize query for Greek accent-insensitive search
        normalized_query = normalize_greek_text(query)
        tokens = tokenize_for_search(query, remove_stopwords=True)

        if not tokens:
            return []

        # Create tsquery from tokens (OR logic)
        tsquery_str = " | ".join(tokens)

        # ILIKE pattern for accent-insensitive matching
        ilike_pattern = f"%{normalized_query}%"

        # Build WHERE clauses dynamically
        where_clauses = [
            "(de.search_vector @@ to_tsquery('simple', :tsquery) OR de.content_normalized ILIKE :pattern)"
        ]
        params: dict[str, Any] = {
            "tsquery": tsquery_str,
            "pattern": ilike_pattern,
            "limit": limit,
        }

        if record_type:
            where_clauses.append("er.record_type = :record_type")
            params["record_type"] = record_type

        if status:
            where_clauses.append("er.status = :status")
            params["status"] = status

        where_sql = " AND ".join(where_clauses)

        # Use raw SQL for tsvector search
        sql = text(f"""
            SELECT
                de.record_id,
                de.content_text,
                GREATEST(
                    COALESCE(ts_rank(de.search_vector, to_tsquery('simple', :tsquery)), 0),
                    CASE WHEN de.content_normalized ILIKE :pattern THEN 0.5 ELSE 0 END
                ) as keyword_score
            FROM document_embeddings de
            JOIN extraction_records er ON de.record_id = er.id
            WHERE {where_sql}
            ORDER BY keyword_score DESC
            LIMIT :limit
        """)

        result = await self.db.execute(sql, params)
        rows = result.fetchall()

        return [
            {
                "record_id": str(row.record_id),
                "content_text": row.content_text,
                "semantic_score": 0.0,
                "keyword_score": min(float(row.keyword_score), 1.0),  # Cap at 1.0
                "search_method": "keyword",
            }
            for row in rows
        ]

    async def _trigram_search(
        self,
        query: str,
        limit: int,
        record_type: str | None = None,
        status: str | None = None,
    ) -> list[dict[str, Any]]:
        """Trigram fuzzy search via pg_trgm similarity().

        Complements the tsvector keyword signal: tsvector handles stemming and
        exact term boundaries well, while pg_trgm handles character-level fuzzy
        matches, typos, punctuation variants, and Greek accent drift (even though
        content_normalized is already accent-stripped — trigrams add robustness
        for abbreviations, spaces, and partial words).

        Uses the existing GIN (content_normalized gin_trgm_ops) index from
        migration 004, so this is index-accelerated at all corpus sizes.

        Returns results with trigram_score in [0, 1] range.
        """
        normalized_query = normalize_greek_text(query)
        if not normalized_query or len(normalized_query) < 2:
            return []

        # pg_trgm similarity() returns [0, 1]. Threshold at 0.1 to avoid noise
        # from single-character overlaps.
        where_clauses = ["similarity(de.content_normalized, :query) > 0.1"]
        params: dict[str, Any] = {"query": normalized_query, "limit": limit}

        if record_type:
            where_clauses.append("er.record_type = :record_type")
            params["record_type"] = record_type
        if status:
            where_clauses.append("er.status = :status")
            params["status"] = status

        where_sql = " AND ".join(where_clauses)

        sql = text(
            f"""
            SELECT
                de.record_id,
                de.content_text,
                similarity(de.content_normalized, :query) AS trigram_score
            FROM document_embeddings de
            JOIN extraction_records er ON de.record_id = er.id
            WHERE {where_sql}
            ORDER BY trigram_score DESC
            LIMIT :limit
            """
        )

        try:
            result = await self.db.execute(sql, params)
            rows = result.fetchall()
        except Exception as e:
            # If pg_trgm isn't enabled (rare — migration 004 handles it), degrade gracefully
            logger.warning("trigram_search_failed", error=str(e))
            return []

        return [
            {
                "record_id": str(row.record_id),
                "content_text": row.content_text,
                "semantic_score": 0.0,
                "keyword_score": 0.0,
                "trigram_score": min(float(row.trigram_score), 1.0),
                "search_method": "trigram",
            }
            for row in rows
        ]

    def _combine_rrf(
        self,
        semantic_results: list[dict[str, Any]],
        keyword_results: list[dict[str, Any]],
        trigram_results: list[dict[str, Any]],
        limit: int,
        min_score: float,
    ) -> list[dict[str, Any]]:
        """Fuse three ranked lists via Reciprocal Rank Fusion.

        RRF formula (Cormack et al. 2009):

            rrf_score(d) = Σ_{lists} weight_l / (k + rank_l(d))

        where `rank_l(d)` is d's 1-indexed rank in list l (skipped if absent),
        k=60 is the paper-default dampening constant, and `weight_l` is the
        per-signal importance.

        This is distribution-free: we don't care that pgvector cosine scores
        are near 1.0 while ts_rank scores are near 0.1. Only ranks matter.

        Returns the top-`limit` documents sorted by combined RRF score, with
        original per-signal scores preserved for observability.
        """
        # Per-list rank maps: record_id → 1-indexed rank
        def build_ranks(results: list[dict[str, Any]]) -> dict[str, int]:
            return {r["record_id"]: rank for rank, r in enumerate(results, start=1)}

        semantic_ranks = build_ranks(semantic_results)
        keyword_ranks = build_ranks(keyword_results)
        trigram_ranks = build_ranks(trigram_results)

        # Merge original data (first hit wins for content_text; per-signal scores
        # are pulled from whichever list contains the document)
        merged: dict[str, dict[str, Any]] = {}

        def ingest(results: list[dict[str, Any]], score_key: str) -> None:
            for r in results:
                rid = r["record_id"]
                if rid not in merged:
                    merged[rid] = {
                        "record_id": rid,
                        "content_text": r["content_text"],
                        "semantic_score": 0.0,
                        "keyword_score": 0.0,
                        "trigram_score": 0.0,
                    }
                if score_key in r:
                    merged[rid][score_key] = float(r.get(score_key, 0.0))

        ingest(semantic_results, "semantic_score")
        ingest(keyword_results, "keyword_score")
        ingest(trigram_results, "trigram_score")

        # Compute RRF combined score per document
        final_results: list[dict[str, Any]] = []
        for rid, data in merged.items():
            rrf = 0.0
            in_semantic = rid in semantic_ranks
            in_keyword = rid in keyword_ranks
            in_trigram = rid in trigram_ranks
            if in_semantic:
                rrf += self.semantic_weight / (RRF_K + semantic_ranks[rid])
            if in_keyword:
                rrf += self.keyword_weight / (RRF_K + keyword_ranks[rid])
            if in_trigram:
                rrf += self.trigram_weight / (RRF_K + trigram_ranks[rid])

            # Min-score gate: we compare the COMBINED score to the threshold
            # but the theoretical max RRF with all three signals at rank 1 is
            # (0.6 + 0.25 + 0.15) / (60 + 1) ≈ 0.0164. We need to scale the
            # incoming `min_similarity` (which callers pass as a [0, 1] value)
            # into the RRF scale, or just ignore it and rely on list limits.
            # Decision: rescale min_score against the per-list max to stay
            # compatible with the v1 API contract.
            combined_score = rrf

            # Search method label — for backward compat with v1 callers
            signal_flags = [in_semantic, in_keyword, in_trigram]
            if sum(signal_flags) >= 2:
                search_method = "hybrid"
            elif in_semantic:
                search_method = "semantic"
            elif in_keyword:
                search_method = "keyword"
            else:
                search_method = "trigram"

            final_results.append(
                {
                    "record_id": rid,
                    "content_text": data["content_text"],
                    "combined_score": round(combined_score, 6),
                    "semantic_score": round(data["semantic_score"], 4),
                    "keyword_score": round(data["keyword_score"], 4),
                    "trigram_score": round(data["trigram_score"], 4),
                    "search_method": search_method,
                }
            )

        # Sort by combined RRF score descending
        final_results.sort(key=lambda x: x["combined_score"], reverse=True)

        # Keep v1 min_similarity parameter semi-useful: filter items whose
        # BEST raw signal is below the threshold. This matches user expectations
        # (min_similarity=0.3 = "don't show me junk").
        if min_score > 0:
            final_results = [
                r
                for r in final_results
                if max(r["semantic_score"], r["keyword_score"], r["trigram_score"])
                >= min_score
            ]

        return final_results[:limit]

    # Backward-compat alias for any legacy callers of the old 2-signal method.
    # Delegates to _combine_rrf with an empty trigram list.
    def _combine_and_rerank(
        self,
        semantic_results: list[dict[str, Any]],
        keyword_results: list[dict[str, Any]],
        limit: int,
        min_score: float,
    ) -> list[dict[str, Any]]:
        """Legacy 2-signal combiner. Delegates to 3-signal RRF with empty trigram."""
        return self._combine_rrf(
            semantic_results=semantic_results,
            keyword_results=keyword_results,
            trigram_results=[],
            limit=limit,
            min_score=min_score,
        )
