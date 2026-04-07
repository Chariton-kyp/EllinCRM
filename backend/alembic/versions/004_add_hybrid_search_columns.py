"""Add hybrid search columns for Greek full-text search.

Revision ID: 004
Revises: 003
Create Date: 2025-12-17

This migration adds columns for hybrid search combining:
- Semantic search (pgvector embeddings)
- Keyword search (PostgreSQL tsvector)

Features:
- content_normalized: Greek accent-insensitive text
- search_vector: tsvector for full-text search
- GIN index for fast keyword matching
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "004"
down_revision: Union[str, None] = "003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Enable pg_trgm extension for trigram indexes (needed for gin_trgm_ops)
    # Must be created BEFORE any index that uses it
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")

    # Add content_normalized column for accent-insensitive Greek text
    op.execute(
        """
        ALTER TABLE document_embeddings
        ADD COLUMN IF NOT EXISTS content_normalized TEXT
        """
    )

    # Add search_vector column for full-text search
    op.execute(
        """
        ALTER TABLE document_embeddings
        ADD COLUMN IF NOT EXISTS search_vector tsvector
        """
    )

    # Create GIN index for fast full-text search
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_embeddings_search_vector
        ON document_embeddings
        USING GIN (search_vector)
        """
    )

    # Create index on content_normalized for ILIKE queries (using trigrams)
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_embeddings_content_normalized
        ON document_embeddings
        USING GIN (content_normalized gin_trgm_ops)
        """
    )


def downgrade() -> None:
    # Drop indexes
    op.execute("DROP INDEX IF EXISTS idx_embeddings_search_vector")
    op.execute("DROP INDEX IF EXISTS idx_embeddings_content_normalized")

    # Drop columns
    op.execute("ALTER TABLE document_embeddings DROP COLUMN IF EXISTS search_vector")
    op.execute("ALTER TABLE document_embeddings DROP COLUMN IF EXISTS content_normalized")
