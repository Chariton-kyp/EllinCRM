"""
SQLAlchemy models for AI/ML features.

Defines the document_embeddings table for storing vector representations
of extraction records, enabling hybrid search with pgvector + tsvector.

Hybrid Search Strategy:
- Semantic search: pgvector embeddings for conceptual similarity
- Keyword search: tsvector for exact Greek/English term matching
- Combined scoring: 0.7 * semantic + 0.3 * keyword
"""

import uuid
from datetime import UTC, datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import DateTime, ForeignKey, Text, text
from sqlalchemy.dialects.postgresql import TSVECTOR
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.models import Base

# Must match the embedding model dimension (google/embeddinggemma-300m = 768)
EMBEDDING_DIMENSION = 768


class DocumentEmbeddingDB(Base):
    """
    SQLAlchemy model for document embeddings with hybrid search support.

    Stores both vector representations (semantic) and tsvector (keyword)
    for hybrid search combining the best of both approaches.

    Columns:
    - embedding: pgvector for semantic similarity search
    - content_normalized: Greek accent-normalized text for ILIKE queries
    - search_vector: tsvector for full-text keyword search
    """

    __tablename__ = "document_embeddings"

    # Primary Key
    id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
    )

    # Foreign key to extraction_records
    record_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("extraction_records.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,  # One embedding per record
    )

    # The original text that was embedded (for debugging/reference)
    content_text: Mapped[str] = mapped_column(Text, nullable=False)

    # The embedding vector (pgvector) - for semantic search
    embedding: Mapped[list[float]] = mapped_column(
        Vector(EMBEDDING_DIMENSION), nullable=False
    )

    # Greek-normalized text (accent-free lowercase) - for keyword search
    # "Δικηγορικό Γραφείο" → "δικηγορικο γραφειο"
    content_normalized: Mapped[str | None] = mapped_column(
        Text, nullable=True
    )

    # Full-text search vector - for tsvector/tsquery keyword matching
    search_vector: Mapped[str | None] = mapped_column(
        TSVECTOR, nullable=True
    )

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        server_default=text("NOW()"),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
        server_default=text("NOW()"),
    )

    def __repr__(self) -> str:
        return f"<DocumentEmbedding(record_id={self.record_id})>"
