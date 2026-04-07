"""
Search router with hybrid semantic + keyword search.

Provides AI-powered search capabilities combining:
- Semantic search: pgvector embeddings (conceptual similarity)
- Keyword search: PostgreSQL tsvector (exact Greek term matching)
- Combined scoring: 0.7 * semantic + 0.3 * keyword

This hybrid approach ensures "Δικηγορικό" finds both:
- Semantically similar content (other professional services)
- Exact keyword matches (documents containing "Δικηγορικό")
"""

from typing import Any, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.embeddings import get_embedding_service, get_embedding_status
from app.ai.hybrid_search import HybridSearchService
from app.ai.similarity import SimilaritySearchService
from app.core.logging import get_logger
from app.db.database import get_db
from app.db.repositories import RecordRepository
from app.models.schemas import ExtractionRecord

logger = get_logger(__name__)

router = APIRouter(prefix="/search", tags=["search"])


def _check_embedding_model_ready() -> tuple[bool, dict[str, Any]]:
    """
    Check if the embedding model is ready for use.

    Returns:
        Tuple of (is_ready, status_info)
    """
    status = get_embedding_status()
    return status["is_ready"], status


# --- Request/Response Models ---


class SearchRequest(BaseModel):
    """Request model for hybrid search."""

    query: str = Field(..., min_length=1, max_length=1000, description="Search query")
    limit: int = Field(10, ge=1, le=100, description="Maximum results")
    min_similarity: float = Field(
        0.3, ge=0.0, le=1.0, description="Minimum similarity threshold"
    )
    record_type: str | None = Field(None, description="Filter by record type")
    status: str | None = Field(None, description="Filter by status")
    search_mode: Literal["hybrid", "semantic", "keyword"] = Field(
        "hybrid",
        description="Search mode: hybrid (default), semantic, or keyword"
    )


class SearchResult(BaseModel):
    """Individual search result with similarity scores."""

    record: ExtractionRecord
    similarity: float = Field(..., description="Combined similarity score (0-1)")
    semantic_score: float = Field(0.0, description="Semantic similarity score")
    keyword_score: float = Field(0.0, description="Keyword match score")
    search_method: str = Field("hybrid", description="Method that found this result")
    highlight: str | None = Field(None, description="Matched content snippet")


class SearchResponse(BaseModel):
    """Response model for search results."""

    query: str
    results: list[SearchResult]
    total: int
    model: str


class SimilarRecordsResponse(BaseModel):
    """Response model for similar records."""

    record_id: str
    similar: list[SearchResult]
    total: int


class EmbeddingStatsResponse(BaseModel):
    """Statistics about embeddings."""

    total_embeddings: int
    records_without_embeddings: int
    embedding_dimension: int
    model: str
    model_status: str = Field("ready", description="Model loading status")
    model_ready: bool = Field(True, description="Whether model is ready for use")


class GenerateEmbeddingsRequest(BaseModel):
    """Request to generate embeddings for records."""

    record_ids: list[UUID] | None = Field(
        None, description="Specific record IDs, or None for all missing"
    )


class GenerateEmbeddingsResponse(BaseModel):
    """Response from embedding generation."""

    generated: int
    message: str


# --- Dependencies ---


async def get_similarity_service(
    db: AsyncSession = Depends(get_db),
) -> SimilaritySearchService:
    """Get SimilaritySearchService with database session."""
    return SimilaritySearchService(db)


async def get_hybrid_search_service(
    db: AsyncSession = Depends(get_db),
) -> HybridSearchService:
    """Get HybridSearchService with database session."""
    embedding_service = get_embedding_service()
    return HybridSearchService(db, embedding_service)


# --- Endpoints ---


@router.post("", response_model=SearchResponse)
async def search_records(
    request: SearchRequest,
    db: AsyncSession = Depends(get_db),
) -> SearchResponse:
    """
    Search for records using hybrid semantic + keyword search.

    By default, uses hybrid search combining:
    - Semantic search (70%): Finds conceptually similar documents
    - Keyword search (30%): Finds exact Greek term matches

    This ensures "Δικηγορικό" finds both semantically similar
    professional services AND documents containing the exact word.

    Search modes:
    - hybrid (default): Combined semantic + keyword
    - semantic: Only embedding-based similarity
    - keyword: Only full-text keyword matching

    NOTE: If the embedding model is still loading, semantic search
    features will be unavailable and the endpoint will return a
    503 Service Unavailable status.

    Example queries:
    - "υπηρεσίες CRM για μικρές επιχειρήσεις"
    - "Δικηγορικό γραφείο"
    - "invoice payment overdue"
    """
    # Check if model is ready for semantic search
    model_ready, model_status = _check_embedding_model_ready()

    if not model_ready and request.search_mode in ("hybrid", "semantic"):
        raise HTTPException(
            status_code=503,
            detail={
                "message": "Embedding model is still loading. Semantic search unavailable.",
                "model_status": model_status["status"],
                "suggestion": "Please try again in a few seconds or use keyword search mode.",
            },
        )

    try:
        repository = RecordRepository(db)
        embedding_service = get_embedding_service()
        similarity_service = SimilaritySearchService(db, embedding_service)
        hybrid_service = HybridSearchService(db, embedding_service)

        if request.search_mode == "hybrid":
            # Use hybrid search (default)
            results = await hybrid_service.hybrid_search(
                query=request.query,
                limit=request.limit,
                min_similarity=request.min_similarity,
                record_type=request.record_type,
                status=request.status,
            )

            search_results = []
            for result in results:
                record = await repository.get_by_id(UUID(result["record_id"]))
                if record:
                    search_results.append(
                        SearchResult(
                            record=record.to_pydantic(),
                            similarity=result["combined_score"],
                            semantic_score=result["semantic_score"],
                            keyword_score=result["keyword_score"],
                            search_method=result["search_method"],
                            highlight=result.get("content_text", "")[:200],
                        )
                    )
        else:
            # Use semantic-only search (legacy)
            results = await similarity_service.search_by_text(
                query=request.query,
                limit=request.limit,
                min_similarity=request.min_similarity,
                record_type=request.record_type,
                status=request.status,
            )

            search_results = [
                SearchResult(
                    record=record.to_pydantic(),
                    similarity=score,
                    semantic_score=score,
                    keyword_score=0.0,
                    search_method="semantic",
                    highlight=_get_highlight(record, request.query),
                )
                for record, score in results
            ]

        return SearchResponse(
            query=request.query,
            results=search_results,
            total=len(search_results),
            model=embedding_service.model_name,
        )

    except Exception as e:
        logger.error("search_failed", error=str(e), query=request.query)
        raise HTTPException(status_code=500, detail=f"Search failed: {str(e)}")


@router.get("/similar/{record_id}", response_model=SimilarRecordsResponse)
async def find_similar_records(
    record_id: UUID,
    limit: int = Query(5, ge=1, le=20, description="Maximum similar records"),
    min_similarity: float = Query(0.5, ge=0.0, le=1.0),
    db: AsyncSession = Depends(get_db),
) -> SimilarRecordsResponse:
    """
    Find records similar to a given record.

    Uses the embedding of the specified record to find
    semantically similar documents in the database.

    NOTE: Requires embedding model to be ready.
    """
    # Check if model is ready
    model_ready, model_status = _check_embedding_model_ready()

    if not model_ready:
        raise HTTPException(
            status_code=503,
            detail={
                "message": "Embedding model is still loading. Similar records unavailable.",
                "model_status": model_status["status"],
            },
        )

    try:
        embedding_service = get_embedding_service()
        service = SimilaritySearchService(db, embedding_service)
        results = await service.find_similar_records(
            record_id=record_id,
            limit=limit,
            min_similarity=min_similarity,
        )

        similar_results = [
            SearchResult(
                record=record.to_pydantic(),
                similarity=score,
            )
            for record, score in results
        ]

        return SimilarRecordsResponse(
            record_id=str(record_id),
            similar=similar_results,
            total=len(similar_results),
        )

    except Exception as e:
        logger.error("find_similar_failed", error=str(e), record_id=str(record_id))
        raise HTTPException(
            status_code=500, detail=f"Failed to find similar records: {str(e)}"
        )


@router.get("/stats", response_model=EmbeddingStatsResponse)
async def get_embedding_stats(
    db: AsyncSession = Depends(get_db),
) -> EmbeddingStatsResponse:
    """
    Get statistics about document embeddings.

    Returns information about the number of embeddings stored,
    records without embeddings, and the embedding model used.

    This endpoint does NOT block on model loading - it returns
    database stats and model loading status immediately.
    """
    try:
        # Get embedding count from database (doesn't need model)
        result = await db.execute(
            text("SELECT COUNT(*) FROM document_embeddings")
        )
        total_embeddings = result.scalar() or 0

        # Get records without embeddings count
        result = await db.execute(
            text("""
                SELECT COUNT(*) FROM extraction_records er
                WHERE NOT EXISTS (
                    SELECT 1 FROM document_embeddings de
                    WHERE de.record_id = er.id
                )
            """)
        )
        records_without = result.scalar() or 0

        # Get model status (doesn't trigger loading)
        model_status = get_embedding_status()

        return EmbeddingStatsResponse(
            total_embeddings=total_embeddings,
            records_without_embeddings=records_without,
            embedding_dimension=768,  # Fixed dimension
            model=model_status.get("model_name", "loading..."),
            model_status=model_status["status"],
            model_ready=model_status["is_ready"],
        )
    except Exception as e:
        logger.error("stats_failed", error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to get stats: {str(e)}")


@router.post("/embeddings/generate", response_model=GenerateEmbeddingsResponse)
async def generate_embeddings(
    request: GenerateEmbeddingsRequest | None = None,
    db: AsyncSession = Depends(get_db),
) -> GenerateEmbeddingsResponse:
    """
    Generate embeddings for records.

    If record_ids is provided, generates embeddings for those specific records.
    Otherwise, generates embeddings for all records that don't have them.

    NOTE: Requires embedding model to be ready.
    """
    # Check if model is ready
    model_ready, model_status = _check_embedding_model_ready()

    if not model_ready:
        raise HTTPException(
            status_code=503,
            detail={
                "message": "Embedding model is still loading. Cannot generate embeddings.",
                "model_status": model_status["status"],
            },
        )

    try:
        embedding_service = get_embedding_service()
        service = SimilaritySearchService(db, embedding_service)
        repository = RecordRepository(db)

        if request and request.record_ids:
            # Generate for specific records
            records = []
            for rid in request.record_ids:
                record = await repository.get_by_id(rid)
                if record:
                    records.append(record)
        else:
            # Get all records without embeddings
            result = await db.execute(
                text("""
                    SELECT er.id FROM extraction_records er
                    WHERE NOT EXISTS (
                        SELECT 1 FROM document_embeddings de
                        WHERE de.record_id = er.id
                    )
                """)
            )
            record_ids = [row[0] for row in result.fetchall()]
            records = []
            for rid in record_ids:
                record = await repository.get_by_id(rid)
                if record:
                    records.append(record)

        if not records:
            return GenerateEmbeddingsResponse(
                generated=0,
                message="No records need embeddings",
            )

        generated = await service.create_embeddings_batch(records)

        return GenerateEmbeddingsResponse(
            generated=generated,
            message=f"Successfully generated {generated} embeddings",
        )

    except Exception as e:
        logger.error("embedding_generation_failed", error=str(e))
        raise HTTPException(
            status_code=500, detail=f"Failed to generate embeddings: {str(e)}"
        )


@router.post("/embeddings/refresh-hybrid", response_model=GenerateEmbeddingsResponse)
async def refresh_hybrid_search_columns(
    db: AsyncSession = Depends(get_db),
) -> GenerateEmbeddingsResponse:
    """
    Refresh hybrid search columns for existing embeddings.

    Updates content_normalized and search_vector columns for all
    existing embeddings to enable hybrid (semantic + keyword) search.
    """
    try:
        from app.ai.greek_text import normalize_greek_text, tokenize_for_search

        # Get all embeddings
        result = await db.execute(
            text("SELECT id, content_text FROM document_embeddings")
        )
        rows = result.fetchall()

        if not rows:
            return GenerateEmbeddingsResponse(
                generated=0,
                message="No embeddings to refresh",
            )

        updated = 0
        for row in rows:
            embedding_id = row.id
            content_text = row.content_text

            # Normalize text for keyword search
            content_normalized = normalize_greek_text(content_text)
            tokens = tokenize_for_search(content_normalized, remove_stopwords=True)
            tsvector_text = " ".join(tokens) if tokens else ""

            # Update the record
            await db.execute(
                text("""
                    UPDATE document_embeddings
                    SET content_normalized = :normalized,
                        search_vector = to_tsvector('simple', :tsvector_text)
                    WHERE id = :id
                """),
                {
                    "id": embedding_id,
                    "normalized": content_normalized,
                    "tsvector_text": tsvector_text,
                },
            )
            updated += 1

        await db.commit()

        logger.info("hybrid_columns_refreshed", count=updated)

        return GenerateEmbeddingsResponse(
            generated=updated,
            message=f"Successfully refreshed {updated} embeddings with hybrid search columns",
        )

    except Exception as e:
        logger.error("hybrid_refresh_failed", error=str(e))
        raise HTTPException(
            status_code=500, detail=f"Failed to refresh hybrid columns: {str(e)}"
        )


def _get_highlight(record, query: str) -> str | None:
    """
    Generate a highlight snippet showing matched content.

    Args:
        record: The matched record.
        query: The search query.

    Returns:
        A snippet of the matched content, or None.
    """
    # Get the main text content from the record
    data = record.final_data
    text_parts = []

    if record.record_type == "FORM":
        if data.get("message"):
            text_parts.append(data["message"])
        if data.get("service_interest"):
            text_parts.append(data["service_interest"])
    elif record.record_type == "EMAIL":
        if data.get("subject"):
            text_parts.append(data["subject"])
        if data.get("body"):
            text_parts.append(data["body"][:200])
    elif record.record_type == "INVOICE":
        if data.get("client_name"):
            text_parts.append(data["client_name"])
        if data.get("notes"):
            text_parts.append(data["notes"])

    if not text_parts:
        return None

    # Return a truncated version
    content = " | ".join(text_parts)
    return content[:200] + "..." if len(content) > 200 else content
