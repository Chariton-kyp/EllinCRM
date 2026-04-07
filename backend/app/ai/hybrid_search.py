"""
Hybrid Search Service combining Semantic + Keyword search.

Implements a 3-stage hybrid search strategy:
1. Semantic search: pgvector embeddings for conceptual similarity
2. Keyword search: PostgreSQL tsvector for exact term matching
3. Score fusion: Combines results with weighted scoring

Algorithm:
    final_score = SEMANTIC_WEIGHT * semantic_score + KEYWORD_WEIGHT * keyword_score

Default weights optimized for Greek business data:
- SEMANTIC_WEIGHT: 0.7 (conceptual understanding)
- KEYWORD_WEIGHT: 0.3 (exact term matching)

This ensures "Δικηγορικό" finds both:
- Semantically similar content (other professional services)
- Exact keyword matches (documents containing "Δικηγορικό")
"""

from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.embeddings import EmbeddingService
from app.ai.greek_text import normalize_greek_text, tokenize_for_search
from app.core.logging import get_logger

logger = get_logger(__name__)

# Hybrid search weights (must sum to 1.0)
SEMANTIC_WEIGHT = 0.7  # pgvector cosine similarity
KEYWORD_WEIGHT = 0.3   # tsvector full-text match


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
    ):
        """
        Initialize hybrid search service.

        Args:
            db: AsyncSession for database queries
            embedding_service: EmbeddingService for generating query embeddings
            semantic_weight: Weight for semantic search (default: 0.7)
            keyword_weight: Weight for keyword search (default: 0.3)
        """
        self.db = db
        self.embedding_service = embedding_service
        self.semantic_weight = semantic_weight
        self.keyword_weight = keyword_weight

        # Normalize weights to sum to 1.0
        total = semantic_weight + keyword_weight
        if abs(total - 1.0) > 0.01:
            logger.warning(
                "hybrid_weights_normalized",
                original_semantic=semantic_weight,
                original_keyword=keyword_weight,
            )
            self.semantic_weight = semantic_weight / total
            self.keyword_weight = keyword_weight / total

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
            # Stage 1: Semantic search (pgvector)
            semantic_results = await self._semantic_search(
                query=query,
                limit=limit * 2,  # Get more candidates
                min_similarity=min_similarity * 0.5,  # Lower threshold for candidates
                record_type=record_type,
                status=status,
            )

            # Stage 2: Keyword search (tsvector)
            keyword_results = await self._keyword_search(
                query=query,
                limit=limit * 2,
                record_type=record_type,
                status=status,
            )

            # Stage 3: Combine and rerank
            combined_results = self._combine_and_rerank(
                semantic_results=semantic_results,
                keyword_results=keyword_results,
                limit=limit,
                min_score=min_similarity,
            )

            logger.info(
                "hybrid_search_complete",
                semantic_count=len(semantic_results),
                keyword_count=len(keyword_results),
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

    def _combine_and_rerank(
        self,
        semantic_results: list[dict[str, Any]],
        keyword_results: list[dict[str, Any]],
        limit: int,
        min_score: float,
    ) -> list[dict[str, Any]]:
        """
        Combine semantic and keyword results with weighted score fusion.

        Algorithm:
        1. Merge results by record_id
        2. Calculate combined_score = 0.7 * semantic + 0.3 * keyword
        3. Sort by combined score
        4. Apply threshold and limit
        """
        # Create lookup by record_id
        combined: dict[str, dict[str, Any]] = {}

        # Process semantic results
        for result in semantic_results:
            record_id = result["record_id"]
            combined[record_id] = {
                "record_id": record_id,
                "content_text": result["content_text"],
                "semantic_score": result["semantic_score"],
                "keyword_score": 0.0,
            }

        # Merge keyword results
        for result in keyword_results:
            record_id = result["record_id"]
            if record_id in combined:
                # Document found in both - update keyword score
                combined[record_id]["keyword_score"] = result["keyword_score"]
            else:
                # Document only in keyword results
                combined[record_id] = {
                    "record_id": record_id,
                    "content_text": result["content_text"],
                    "semantic_score": 0.0,
                    "keyword_score": result["keyword_score"],
                }

        # Calculate combined scores and determine search method
        final_results = []
        for record_id, data in combined.items():
            combined_score = (
                self.semantic_weight * data["semantic_score"]
                + self.keyword_weight * data["keyword_score"]
            )

            # Determine which search method contributed
            if data["semantic_score"] > 0 and data["keyword_score"] > 0:
                search_method = "hybrid"
            elif data["semantic_score"] > 0:
                search_method = "semantic"
            else:
                search_method = "keyword"

            if combined_score >= min_score:
                final_results.append({
                    "record_id": record_id,
                    "content_text": data["content_text"],
                    "combined_score": round(combined_score, 4),
                    "semantic_score": round(data["semantic_score"], 4),
                    "keyword_score": round(data["keyword_score"], 4),
                    "search_method": search_method,
                })

        # Sort by combined score
        final_results.sort(key=lambda x: x["combined_score"], reverse=True)

        # Apply limit
        return final_results[:limit]
