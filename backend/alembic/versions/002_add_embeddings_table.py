"""Add document embeddings table for semantic search.

Revision ID: 002
Revises: 001
Create Date: 2025-12-16

This migration adds support for AI-powered semantic search using pgvector.
Embeddings are stored separately from extraction records for flexibility.
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "002"
down_revision: Union[str, None] = "001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Embedding dimension for the model we use
# paraphrase-multilingual-MiniLM-L12-v2 produces 384-dim vectors
EMBEDDING_DIMENSION = 384


def upgrade() -> None:
    # Create document_embeddings table
    op.create_table(
        "document_embeddings",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column(
            "record_id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
        ),
        # Store the text that was embedded for reference
        sa.Column("content_text", sa.Text(), nullable=False),
        # The embedding vector - using pgvector's vector type
        # We'll create this column with raw SQL for proper vector type
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("NOW()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("NOW()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["record_id"],
            ["extraction_records.id"],
            ondelete="CASCADE",
        ),
    )

    # Add the vector column using raw SQL (Alembic doesn't natively support pgvector)
    op.execute(
        f"ALTER TABLE document_embeddings ADD COLUMN embedding vector({EMBEDDING_DIMENSION})"
    )

    # Create HNSW index for fast approximate nearest neighbor search
    # HNSW (Hierarchical Navigable Small World) is faster than IVFFlat for queries
    op.execute(
        """
        CREATE INDEX idx_embeddings_vector_hnsw
        ON document_embeddings
        USING hnsw (embedding vector_cosine_ops)
        WITH (m = 16, ef_construction = 64)
        """
    )

    # Create index for record lookups
    op.create_index(
        "idx_embeddings_record_id",
        "document_embeddings",
        ["record_id"],
        unique=True,  # One embedding per record
    )


def downgrade() -> None:
    # Drop indexes
    op.execute("DROP INDEX IF EXISTS idx_embeddings_vector_hnsw")
    op.drop_index("idx_embeddings_record_id", table_name="document_embeddings")

    # Drop table
    op.drop_table("document_embeddings")
