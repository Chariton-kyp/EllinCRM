"""
Similarity search service using pgvector + hybrid search.

Provides semantic search capabilities for finding similar documents
based on their embedding representations, with optional hybrid search
combining semantic and keyword matching for Greek text.

Hybrid Search Strategy:
- Semantic: pgvector embeddings (conceptual similarity)
- Keyword: tsvector full-text search (exact Greek term matching)
- Combined: 0.7 * semantic + 0.3 * keyword
"""

from typing import Any
from uuid import UUID

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.embeddings import (
    EmbeddingService,
    extract_text_for_embedding,
    get_embedding_service,
)
from app.ai.greek_text import normalize_greek_text, tokenize_for_search
from app.ai.models import EMBEDDING_DIMENSION, DocumentEmbeddingDB
from app.core.logging import get_logger
from app.db.models import ExtractionRecordDB

logger = get_logger(__name__)

# Hybrid search weights
SEMANTIC_WEIGHT = 0.7
KEYWORD_WEIGHT = 0.3


class SimilaritySearchService:
    """
    Service for semantic similarity search over extraction records.

    Uses pgvector's HNSW index for efficient approximate nearest neighbor search.
    Supports finding similar documents by text query or by existing record.

    Example:
        >>> service = SimilaritySearchService(db_session)
        >>> results = await service.search_similar("CRM υπηρεσίες", limit=5)
        >>> for record, score in results:
        ...     print(f"{record.source_file}: {score:.2f}")
    """

    def __init__(
        self,
        db: AsyncSession,
        embedding_service: EmbeddingService | None = None,
    ):
        """
        Initialize the similarity search service.

        Args:
            db: Async database session.
            embedding_service: Optional custom embedding service.
        """
        self.db = db
        self.embedding_service = embedding_service or get_embedding_service()

    async def search_by_text(
        self,
        query: str,
        limit: int = 10,
        min_similarity: float = 0.0,
        record_type: str | None = None,
        status: str | None = None,
    ) -> list[tuple[ExtractionRecordDB, float]]:
        """
        Search for similar documents using a text query.

        Args:
            query: Search query in Greek or English.
            limit: Maximum number of results.
            min_similarity: Minimum similarity score (0-1).
            record_type: Filter by record type (FORM, EMAIL, INVOICE).
            status: Filter by status (pending, approved, etc.).

        Returns:
            List of (record, similarity_score) tuples, sorted by similarity.
        """
        if not query or not query.strip():
            return []

        # Generate embedding for the query
        query_embedding = await self.embedding_service.generate_embedding_async(query)

        # Build the similarity search query using pgvector's cosine distance
        # Lower distance = higher similarity, so we use 1 - distance
        # Format the embedding as a vector literal for direct SQL injection (safe - we control the values)
        embedding_str = f"'[{','.join(map(str, query_embedding))}]'"

        # Build WHERE clauses dynamically to avoid asyncpg NULL handling issues
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
        # Note: embedding is inserted directly as a literal since asyncpg doesn't support
        # binding vector parameters well. This is safe because we generate the embedding.
        sql = text(f"""
            SELECT
                er.*,
                1 - (de.embedding <=> {embedding_str}::vector) as similarity
            FROM extraction_records er
            JOIN document_embeddings de ON de.record_id = er.id
            WHERE {where_sql}
            ORDER BY de.embedding <=> {embedding_str}::vector
            LIMIT :limit
        """)

        result = await self.db.execute(sql, params)

        rows = result.fetchall()
        records_with_scores = []

        for row in rows:
            # Reconstruct the record from the row
            record = await self.db.get(ExtractionRecordDB, row.id)
            if record:
                records_with_scores.append((record, float(row.similarity)))

        logger.info(
            "similarity_search_completed",
            query=query[:50],
            results=len(records_with_scores),
            top_score=records_with_scores[0][1] if records_with_scores else 0,
        )

        return records_with_scores

    async def find_similar_records(
        self,
        record_id: UUID,
        limit: int = 5,
        min_similarity: float = 0.5,
    ) -> list[tuple[ExtractionRecordDB, float]]:
        """
        Find records similar to a given record.

        Args:
            record_id: ID of the reference record.
            limit: Maximum number of similar records.
            min_similarity: Minimum similarity threshold.

        Returns:
            List of (record, similarity_score) tuples, excluding the reference.
        """
        # Get the embedding for the reference record
        stmt = select(DocumentEmbeddingDB).where(
            DocumentEmbeddingDB.record_id == record_id
        )
        result = await self.db.execute(stmt)
        embedding_row = result.scalar_one_or_none()

        if not embedding_row:
            logger.warning(
                "no_embedding_for_record",
                record_id=str(record_id),
            )
            return []

        # Search for similar embeddings, excluding the reference
        # Format the embedding as a vector literal for direct SQL insertion (safe - we control the values)
        embedding_str = f"'[{','.join(map(str, embedding_row.embedding))}]'"

        sql = text(f"""
            SELECT
                er.*,
                1 - (de.embedding <=> {embedding_str}::vector) as similarity
            FROM extraction_records er
            JOIN document_embeddings de ON de.record_id = er.id
            WHERE er.id != :record_id
            AND 1 - (de.embedding <=> {embedding_str}::vector) >= :min_similarity
            ORDER BY de.embedding <=> {embedding_str}::vector
            LIMIT :limit
        """)

        result = await self.db.execute(
            sql,
            {
                "record_id": record_id,
                "min_similarity": min_similarity,
                "limit": limit,
            },
        )

        rows = result.fetchall()
        records_with_scores = []

        for row in rows:
            record = await self.db.get(ExtractionRecordDB, row.id)
            if record:
                records_with_scores.append((record, float(row.similarity)))

        return records_with_scores

    async def create_embedding(
        self,
        record: ExtractionRecordDB,
    ) -> DocumentEmbeddingDB | None:
        """
        Create and store an embedding for a record.

        Also populates hybrid search columns (content_normalized, search_vector)
        for combined semantic + keyword search.

        Args:
            record: The extraction record to embed.

        Returns:
            The created embedding record, or None if embedding failed.
        """
        # Extract text for embedding based on record type
        content_text = extract_text_for_embedding(
            record.record_type,
            record.final_data,
        )

        if not content_text:
            logger.warning(
                "no_content_for_embedding",
                record_id=str(record.id),
                record_type=record.record_type,
            )
            return None

        # Generate embedding
        embedding = await self.embedding_service.generate_embedding_async(content_text)

        # Normalize text for keyword search (Greek accent-insensitive)
        content_normalized = normalize_greek_text(content_text)

        # Check if embedding already exists
        stmt = select(DocumentEmbeddingDB).where(
            DocumentEmbeddingDB.record_id == record.id
        )
        result = await self.db.execute(stmt)
        existing = result.scalar_one_or_none()

        if existing:
            # Update existing embedding
            existing.content_text = content_text
            existing.embedding = embedding
            existing.content_normalized = content_normalized
            await self.db.commit()
            await self.db.refresh(existing)

            # Update search_vector using raw SQL (tsvector requires SQL)
            await self._update_search_vector(existing.id, content_normalized)

            logger.info(
                "embedding_updated",
                record_id=str(record.id),
            )
            return existing
        else:
            # Create new embedding
            embedding_record = DocumentEmbeddingDB(
                record_id=record.id,
                content_text=content_text,
                embedding=embedding,
                content_normalized=content_normalized,
            )
            self.db.add(embedding_record)
            await self.db.commit()
            await self.db.refresh(embedding_record)

            # Update search_vector using raw SQL
            await self._update_search_vector(embedding_record.id, content_normalized)

            logger.info(
                "embedding_created",
                record_id=str(record.id),
            )
            return embedding_record

    async def _update_search_vector(
        self,
        embedding_id: Any,
        normalized_text: str,
    ) -> None:
        """
        Update the search_vector (tsvector) column for an embedding.

        Uses raw SQL to generate tsvector from normalized text.

        Args:
            embedding_id: The UUID of the embedding record.
            normalized_text: The normalized text to index.
        """
        # Tokenize for tsvector (remove stopwords)
        tokens = tokenize_for_search(normalized_text, remove_stopwords=True)
        if not tokens:
            return

        # Create simple tsvector from tokens
        tsvector_text = " ".join(tokens)

        sql = text("""
            UPDATE document_embeddings
            SET search_vector = to_tsvector('simple', :text)
            WHERE id = :id
        """)

        await self.db.execute(sql, {"id": embedding_id, "text": tsvector_text})
        await self.db.commit()

    async def create_embeddings_batch(
        self,
        records: list[ExtractionRecordDB],
    ) -> int:
        """
        Create embeddings for multiple records efficiently.

        Also populates hybrid search columns (content_normalized, search_vector)
        for combined semantic + keyword search.

        Args:
            records: List of extraction records to embed.

        Returns:
            Number of embeddings created/updated.
        """
        if not records:
            return 0

        # Extract texts for all records
        texts = []
        valid_records = []
        for record in records:
            content_text = extract_text_for_embedding(
                record.record_type,
                record.final_data,
            )
            if content_text:
                texts.append(content_text)
                content_normalized = normalize_greek_text(content_text)
                valid_records.append((record, content_text, content_normalized))

        if not texts:
            return 0

        # Generate embeddings in batch
        embeddings = await self.embedding_service.generate_embeddings_batch_async(texts)

        # Store embeddings
        created = 0
        embedding_ids = []
        normalized_texts = []

        for (record, content_text, content_normalized), embedding in zip(valid_records, embeddings):
            # Check if exists
            stmt = select(DocumentEmbeddingDB).where(
                DocumentEmbeddingDB.record_id == record.id
            )
            result = await self.db.execute(stmt)
            existing = result.scalar_one_or_none()

            if existing:
                existing.content_text = content_text
                existing.embedding = embedding
                existing.content_normalized = content_normalized
                embedding_ids.append(existing.id)
            else:
                embedding_record = DocumentEmbeddingDB(
                    record_id=record.id,
                    content_text=content_text,
                    embedding=embedding,
                    content_normalized=content_normalized,
                )
                self.db.add(embedding_record)
                # Need to flush to get the ID
                await self.db.flush()
                embedding_ids.append(embedding_record.id)

            normalized_texts.append(content_normalized)
            created += 1

        await self.db.commit()

        # Update search vectors in batch
        for emb_id, normalized in zip(embedding_ids, normalized_texts):
            await self._update_search_vector(emb_id, normalized)

        logger.info(
            "batch_embeddings_created",
            count=created,
        )
        return created

    async def delete_embedding(self, record_id: UUID) -> bool:
        """
        Delete the embedding for a record.

        Args:
            record_id: ID of the record whose embedding to delete.

        Returns:
            True if deleted, False if not found.
        """
        stmt = select(DocumentEmbeddingDB).where(
            DocumentEmbeddingDB.record_id == record_id
        )
        result = await self.db.execute(stmt)
        embedding = result.scalar_one_or_none()

        if embedding:
            await self.db.delete(embedding)
            await self.db.commit()
            return True
        return False

    async def get_embedding_stats(self) -> dict[str, Any]:
        """
        Get statistics about stored embeddings.

        Returns:
            Dictionary with embedding statistics.
        """
        # Count total embeddings
        count_result = await self.db.execute(
            text("SELECT COUNT(*) FROM document_embeddings")
        )
        total = count_result.scalar() or 0

        # Count records without embeddings
        missing_result = await self.db.execute(
            text("""
                SELECT COUNT(*) FROM extraction_records er
                WHERE NOT EXISTS (
                    SELECT 1 FROM document_embeddings de
                    WHERE de.record_id = er.id
                )
            """)
        )
        missing = missing_result.scalar() or 0

        return {
            "total_embeddings": total,
            "records_without_embeddings": missing,
            "embedding_dimension": EMBEDDING_DIMENSION,
            "model": self.embedding_service.model_name,
        }
