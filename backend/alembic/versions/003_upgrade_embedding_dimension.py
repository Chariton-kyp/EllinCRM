"""Upgrade embedding dimension from 384 to 768 for EmbeddingGemma 300M model.

Revision ID: 003
Revises: 002
Create Date: 2025-12-17

This migration upgrades the vector dimension to support the more powerful
Google EmbeddingGemma 300M model (google/embeddinggemma-300m) which produces
768-dimensional vectors.
"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "003"
down_revision: Union[str, None] = "002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# New embedding dimension for Gemma 308M
NEW_EMBEDDING_DIMENSION = 768
OLD_EMBEDDING_DIMENSION = 384


def upgrade() -> None:
    # Drop existing HNSW index (required before altering column)
    op.execute("DROP INDEX IF EXISTS idx_embeddings_vector_hnsw")

    # Drop the old embedding column
    op.execute("ALTER TABLE document_embeddings DROP COLUMN IF EXISTS embedding")

    # Add new embedding column with 768 dimensions
    op.execute(
        f"ALTER TABLE document_embeddings ADD COLUMN embedding vector({NEW_EMBEDDING_DIMENSION})"
    )

    # Recreate HNSW index for the new dimension
    op.execute(
        """
        CREATE INDEX idx_embeddings_vector_hnsw
        ON document_embeddings
        USING hnsw (embedding vector_cosine_ops)
        WITH (m = 16, ef_construction = 64)
        """
    )

    # Note: All existing embeddings will be NULL and need to be regenerated
    # using the new Gemma 308M model


def downgrade() -> None:
    # Drop HNSW index
    op.execute("DROP INDEX IF EXISTS idx_embeddings_vector_hnsw")

    # Drop 768-dim column
    op.execute("ALTER TABLE document_embeddings DROP COLUMN IF EXISTS embedding")

    # Recreate 384-dim column
    op.execute(
        f"ALTER TABLE document_embeddings ADD COLUMN embedding vector({OLD_EMBEDDING_DIMENSION})"
    )

    # Recreate HNSW index
    op.execute(
        """
        CREATE INDEX idx_embeddings_vector_hnsw
        ON document_embeddings
        USING hnsw (embedding vector_cosine_ops)
        WITH (m = 16, ef_construction = 64)
        """
    )
