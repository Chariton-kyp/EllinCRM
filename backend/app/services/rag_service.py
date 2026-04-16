"""RAG (Retrieval-Augmented Generation) service for chat context retrieval.

Implements the retrieve step of the RAG pipeline:
1. Embed user query via EmbeddingGemma
2. Hybrid search (semantic + keyword) over extraction records
3. Build formatted context string with source citations
4. Return context + sources for LLM prompt injection
"""

import logging
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.embeddings import get_embedding_service, get_embedding_status
from app.ai.hybrid_search import HybridSearchService
from app.db.repositories import RecordRepository

logger = logging.getLogger(__name__)


class RAGService:
    """Retrieval-Augmented Generation service for chat context.

    Queries the hybrid search index to find relevant extraction records,
    then formats them as structured context for the LLM prompt.
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    async def retrieve_context(
        self, query: str, limit: int = 5
    ) -> tuple[str, list[dict[str, Any]]]:
        """Retrieve relevant context from extraction records via hybrid search.

        Args:
            query: User's question (Greek or English).
            limit: Maximum number of records to retrieve.

        Returns:
            Tuple of (context_string, sources_list).
            context_string: Formatted text block for LLM system prompt.
            sources_list: List of dicts with record_id, source_file, record_type, score.
        """
        # Check embedding model readiness
        embedding_status = get_embedding_status()
        if not embedding_status["is_ready"]:
            logger.warning("rag_embedding_not_ready, status=%s", embedding_status["status"])
            return (
                "Προσοχη: Το μοντελο embeddings δεν ειναι ετοιμο ακομα. "
                "Δεν μπορω να αναζητησω σχετικα δεδομενα.",
                [],
            )

        embedding_service = get_embedding_service()
        search_service = HybridSearchService(self.db, embedding_service)

        try:
            results = await search_service.hybrid_search(
                query=query,
                limit=limit,
                min_similarity=0.15,
            )
        except Exception as exc:
            logger.error("rag_hybrid_search_failed: %s", exc)
            return "Σφαλμα κατα την αναζητηση δεδομενων.", []

        if not results:
            return "Δεν βρεθηκαν σχετικα δεδομενα για το ερωτημα σου.", []

        # Load full records and build context
        repo = RecordRepository(self.db)
        context_parts: list[str] = []
        sources: list[dict[str, Any]] = []

        for result in results:
            record_id_str = result["record_id"]
            try:
                record = await repo.get_by_id(UUID(record_id_str))
            except Exception:
                logger.warning("rag_record_load_failed, id=%s", record_id_str)
                continue

            if record is None:
                continue

            # Build context block from final_data (edited if available, else extracted)
            data = record.final_data
            data_lines = [
                f"  {key}: {value}"
                for key, value in data.items()
                if value is not None and value != "" and value != []
            ]
            data_text = "\n".join(data_lines)

            context_parts.append(
                f"[Πηγη: {record.source_file} | Τυπος: {record.record_type} "
                f"| ID: {record_id_str}]\n{data_text}"
            )

            score = result.get("combined_score", result.get("semantic_score", 0.0))
            sources.append(
                {
                    "record_id": record_id_str,
                    "source_file": record.source_file,
                    "record_type": record.record_type,
                    "score": round(float(score), 4),
                }
            )

        context_string = (
            "\n\n".join(context_parts)
            if context_parts
            else ("Δεν βρεθηκαν σχετικα δεδομενα για το ερωτημα σου.")
        )

        logger.info(
            "rag_context_retrieved, query=%s, records=%d",
            query[:50],
            len(sources),
        )
        return context_string, sources
