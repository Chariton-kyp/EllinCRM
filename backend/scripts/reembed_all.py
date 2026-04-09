"""Re-embed all extraction records with the current primary embedding model.

Run this script after swapping the primary embedding model (Phase 2B:
EmbeddingGemma → Qwen3-Embedding) to regenerate all document_embeddings
rows with the new model's vector space.

Usage (inside the dev container):
    docker exec ellincrm-backend-dev python -m scripts.reembed_all

Usage (on the host, with backend venv active):
    cd backend && python -m scripts.reembed_all

Behavior:
    1. Loads the current primary embedding model (blocking — waits until ready).
    2. Fetches every row in extraction_records.
    3. For each record, computes the embedding text (via
       extract_text_for_embedding) and upserts document_embeddings.
    4. Reports per-record status and final summary.

Safety:
    - Writes to document_embeddings but NEVER modifies extraction_records.
    - Idempotent: re-running on an already-embedded corpus is safe (updates
      in place via ON CONFLICT).
    - No API dependencies; runs fully offline with local sentence-transformers.
"""

from __future__ import annotations

import asyncio
import sys
import time

from sqlalchemy import text

from app.ai.embeddings import (
    extract_text_for_embedding,
    get_embedding_service,
)
from app.ai.greek_text import normalize_greek_text
from app.core.logging import get_logger, setup_logging
from app.db.database import AsyncSessionLocal

setup_logging()
logger = get_logger("reembed_all")


async def reembed_all() -> int:
    """Re-embed every extraction record. Returns the number of records processed."""
    if AsyncSessionLocal is None:
        logger.error("DATABASE_URL is not configured; cannot connect to Postgres.")
        return 0

    service = get_embedding_service()
    logger.info(
        "loading_embedding_model",
        primary=service._primary_model,
        fallback=service._fallback_model,
    )
    service.load_model_sync()
    if not service.is_ready:
        logger.error("embedding_model_not_ready", status=service.status.value)
        return 0
    logger.info("embedding_model_loaded", model=service.model_name)

    async with AsyncSessionLocal() as session:
        # Fetch all records
        rows = (
            await session.execute(
                text(
                    "SELECT id, record_type, extracted_data, edited_data "
                    "FROM extraction_records "
                    "ORDER BY created_at"
                )
            )
        ).all()
        total = len(rows)
        logger.info("fetched_records", count=total)

        if total == 0:
            logger.info("no_records_to_embed")
            return 0

        start = time.time()
        embedded = 0
        skipped = 0
        failed = 0

        for row in rows:
            record_id = row.id
            record_type = row.record_type
            data = row.edited_data or row.extracted_data or {}

            content_text = extract_text_for_embedding(record_type, data)
            if not content_text.strip():
                logger.warning(
                    "empty_content_skipped",
                    record_id=str(record_id),
                    record_type=record_type,
                )
                skipped += 1
                continue

            content_normalized = normalize_greek_text(content_text)

            try:
                vector = service.generate_embedding(content_text)
                if vector is None:
                    logger.error("embedding_returned_none", record_id=str(record_id))
                    failed += 1
                    continue
            except Exception as exc:
                logger.error(
                    "embedding_generation_failed",
                    record_id=str(record_id),
                    error=str(exc),
                )
                failed += 1
                continue

            # Upsert into document_embeddings
            try:
                embedding_str = "[" + ",".join(str(v) for v in vector) + "]"
                await session.execute(
                    text(
                        """
                        INSERT INTO document_embeddings (
                            record_id, content_text, content_normalized, embedding
                        )
                        VALUES (
                            :record_id, :content_text, :content_normalized,
                            CAST(:embedding AS vector)
                        )
                        ON CONFLICT (record_id) DO UPDATE SET
                            content_text = EXCLUDED.content_text,
                            content_normalized = EXCLUDED.content_normalized,
                            embedding = EXCLUDED.embedding,
                            updated_at = NOW()
                        """
                    ),
                    {
                        "record_id": record_id,
                        "content_text": content_text,
                        "content_normalized": content_normalized,
                        "embedding": embedding_str,
                    },
                )
                embedded += 1
                logger.info(
                    "embedded_record",
                    record_id=str(record_id),
                    record_type=record_type,
                    text_length=len(content_text),
                )
            except Exception as exc:
                logger.error(
                    "upsert_failed",
                    record_id=str(record_id),
                    error=str(exc),
                )
                failed += 1

        await session.commit()

        duration = time.time() - start
        logger.info(
            "reembed_complete",
            total=total,
            embedded=embedded,
            skipped=skipped,
            failed=failed,
            duration_s=round(duration, 2),
        )
        return embedded


if __name__ == "__main__":
    count = asyncio.run(reembed_all())
    sys.exit(0 if count >= 0 else 1)
