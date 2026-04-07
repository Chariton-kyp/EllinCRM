"""Add audit_logs table for persistent audit trail.

Revision ID: 005_audit_logs
Revises: 004_add_hybrid_search_columns
Create Date: 2025-12-23

This migration creates the audit_logs table to store all user actions
and system events for compliance and debugging purposes.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "005"
down_revision: Union[str, None] = "004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create audit_logs table."""
    op.create_table(
        "audit_logs",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("action", sa.String(50), nullable=False),
        sa.Column("record_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("user_id", sa.String(100), nullable=True),
        sa.Column("details", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column(
            "timestamp",
            sa.DateTime(timezone=True),
            server_default=sa.text("NOW()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    # Create indexes for efficient querying
    op.create_index("idx_audit_logs_action", "audit_logs", ["action"])
    op.create_index("idx_audit_logs_record_id", "audit_logs", ["record_id"])
    op.create_index(
        "idx_audit_logs_timestamp",
        "audit_logs",
        ["timestamp"],
        postgresql_using="btree",
    )
    op.create_index("idx_audit_logs_user_id", "audit_logs", ["user_id"])


def downgrade() -> None:
    """Drop audit_logs table."""
    op.drop_index("idx_audit_logs_user_id", table_name="audit_logs")
    op.drop_index("idx_audit_logs_timestamp", table_name="audit_logs")
    op.drop_index("idx_audit_logs_record_id", table_name="audit_logs")
    op.drop_index("idx_audit_logs_action", table_name="audit_logs")
    op.drop_table("audit_logs")
