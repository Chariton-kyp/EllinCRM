"""Initial tables for extraction records.

Revision ID: 001
Revises:
Create Date: 2025-12-16

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create pgvector extension for future semantic search
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    # Create extraction_records table
    op.create_table(
        "extraction_records",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("source_file", sa.String(500), nullable=False),
        sa.Column("record_type", sa.String(20), nullable=False),
        sa.Column(
            "extracted_data",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
        ),
        sa.Column(
            "edited_data",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
        sa.Column(
            "confidence_score",
            sa.Float(),
            nullable=False,
            server_default=sa.text("1.0"),
        ),
        sa.Column("warnings", postgresql.ARRAY(sa.String()), nullable=True),
        sa.Column("errors", postgresql.ARRAY(sa.String()), nullable=True),
        sa.Column(
            "status",
            sa.String(20),
            nullable=False,
            server_default=sa.text("'pending'"),
        ),
        sa.Column("reviewed_by", sa.String(100), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("review_notes", sa.Text(), nullable=True),
        sa.Column("rejection_reason", sa.Text(), nullable=True),
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
        sa.CheckConstraint(
            "status IN ('pending', 'approved', 'rejected', 'edited', 'exported')",
            name="valid_status",
        ),
        sa.CheckConstraint(
            "record_type IN ('FORM', 'EMAIL', 'INVOICE')", name="valid_record_type"
        ),
        sa.CheckConstraint(
            "confidence_score >= 0 AND confidence_score <= 1", name="valid_confidence"
        ),
    )

    # Create indexes for common queries
    op.create_index(
        "idx_records_status", "extraction_records", ["status"], unique=False
    )
    op.create_index(
        "idx_records_record_type", "extraction_records", ["record_type"], unique=False
    )
    op.create_index(
        "idx_records_created_at",
        "extraction_records",
        [sa.text("created_at DESC")],
        unique=False,
    )
    op.create_index(
        "idx_records_status_type",
        "extraction_records",
        ["status", "record_type"],
        unique=False,
    )


def downgrade() -> None:
    # Drop indexes
    op.drop_index("idx_records_status_type", table_name="extraction_records")
    op.drop_index("idx_records_created_at", table_name="extraction_records")
    op.drop_index("idx_records_record_type", table_name="extraction_records")
    op.drop_index("idx_records_status", table_name="extraction_records")

    # Drop table
    op.drop_table("extraction_records")

    # Note: We don't drop the vector extension as it might be used by other tables
