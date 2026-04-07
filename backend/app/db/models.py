"""
SQLAlchemy ORM models for database persistence.
Uses SQLAlchemy 2.0 declarative mapping with type hints.
"""

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import ARRAY, CheckConstraint, DateTime, Index, String, Text, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from app.models.schemas import (
    ContactFormData,
    EmailData,
    ExtractionRecord,
    ExtractionResult,
    ExtractionStatus,
    InvoiceData,
    RecordType,
)


class Base(DeclarativeBase):
    """Base class for all ORM models."""

    pass


class ExtractionRecordDB(Base):
    """
    SQLAlchemy model for extraction records.

    Stores extracted data from forms, emails, and invoices
    along with workflow status for human-in-the-loop approval.
    """

    __tablename__ = "extraction_records"

    # Primary Key
    id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
    )

    # Source Information
    source_file: Mapped[str] = mapped_column(String(500), nullable=False)
    record_type: Mapped[str] = mapped_column(String(20), nullable=False)

    # Extraction Data (JSONB for flexibility)
    extracted_data: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    edited_data: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)

    # Extraction Metadata
    confidence_score: Mapped[float] = mapped_column(default=1.0, server_default=text("1.0"))
    warnings: Mapped[list[str] | None] = mapped_column(ARRAY(String), nullable=True)
    errors: Mapped[list[str] | None] = mapped_column(ARRAY(String), nullable=True)

    # Workflow Status
    status: Mapped[str] = mapped_column(
        String(20), default="pending", server_default=text("'pending'"), nullable=False
    )

    # Review Information
    reviewed_by: Mapped[str | None] = mapped_column(String(100), nullable=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    review_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    rejection_reason: Mapped[str | None] = mapped_column(Text, nullable=True)

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

    # Table configuration
    __table_args__ = (
        CheckConstraint(
            "status IN ('pending', 'approved', 'rejected', 'edited', 'exported')",
            name="valid_status",
        ),
        CheckConstraint(
            "record_type IN ('FORM', 'EMAIL', 'INVOICE')", name="valid_record_type"
        ),
        CheckConstraint(
            "confidence_score >= 0 AND confidence_score <= 1", name="valid_confidence"
        ),
        Index("idx_records_status", "status"),
        Index("idx_records_record_type", "record_type"),
        Index("idx_records_created_at", "created_at", postgresql_using="btree"),
    )

    def to_pydantic(self) -> ExtractionRecord:
        """
        Convert ORM model to Pydantic ExtractionRecord.

        Returns:
            ExtractionRecord: Pydantic model for API responses.
        """
        # Parse extracted data based on record type
        form_data = None
        email_data = None
        invoice_data = None

        if self.record_type == RecordType.FORM.value:
            form_data = ContactFormData.model_validate(self.extracted_data)
        elif self.record_type == RecordType.EMAIL.value:
            email_data = EmailData.model_validate(self.extracted_data)
        elif self.record_type == RecordType.INVOICE.value:
            invoice_data = InvoiceData.model_validate(self.extracted_data)

        # Build ExtractionResult
        extraction = ExtractionResult(
            id=self.id,
            source_file=self.source_file,
            record_type=RecordType(self.record_type),
            confidence_score=self.confidence_score,
            warnings=self.warnings or [],
            errors=self.errors or [],
            form_data=form_data,
            email_data=email_data,
            invoice_data=invoice_data,
        )

        return ExtractionRecord(
            id=self.id,
            extraction=extraction,
            status=ExtractionStatus(self.status),
            reviewed_by=self.reviewed_by,
            reviewed_at=self.reviewed_at,
            review_notes=self.review_notes,
            edited_data=self.edited_data,
            created_at=self.created_at,
            updated_at=self.updated_at,
        )

    @classmethod
    def from_extraction_result(cls, result: ExtractionResult) -> "ExtractionRecordDB":
        """
        Create ORM model from ExtractionResult.

        Args:
            result: ExtractionResult from extractor.

        Returns:
            ExtractionRecordDB: ORM model ready for database insertion.
        """
        # Get the extracted data as dict
        data = result.data
        if data is None:
            raise ValueError("ExtractionResult has no data")

        # Serialize data preserving Greek characters
        # mode="json" escapes unicode, so we use "python" and manually convert datetimes/Decimals
        from datetime import datetime as dt
        from decimal import Decimal

        def serialize_value(obj: Any) -> Any:
            """Convert Python objects to JSON-serializable types."""
            if isinstance(obj, dt):
                return obj.isoformat()
            elif isinstance(obj, Decimal):
                return str(obj)
            elif isinstance(obj, dict):
                return {k: serialize_value(v) for k, v in obj.items()}
            elif isinstance(obj, list):
                return [serialize_value(v) for v in obj]
            return obj

        extracted = data.model_dump(mode="python", by_alias=True)
        extracted = serialize_value(extracted)

        return cls(
            id=result.id,
            source_file=result.source_file,
            record_type=result.record_type.value,
            extracted_data=extracted,
            confidence_score=result.confidence_score,
            warnings=result.warnings if result.warnings else None,
            errors=result.errors if result.errors else None,
            status="pending",
        )

    @property
    def final_data(self) -> dict[str, Any]:
        """Get the final data (edited if available, otherwise original)."""
        return self.edited_data if self.edited_data else self.extracted_data


class AuditLogDB(Base):
    """
    SQLAlchemy model for audit trail persistence.

    Stores all user actions and system events for compliance and debugging.
    This provides a permanent, queryable history of all operations.
    """

    __tablename__ = "audit_logs"

    # Primary Key
    id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
    )

    # Action Information
    action: Mapped[str] = mapped_column(String(50), nullable=False)
    # Actions: extraction_started, extraction_completed, record_created,
    #          record_approved, record_rejected, record_edited, data_export

    # Related Record (optional - some actions like export may not have a single record)
    record_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), nullable=True
    )

    # User Information
    user_id: Mapped[str | None] = mapped_column(String(100), nullable=True)

    # Action Details (JSONB for flexibility)
    details: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)

    # Timestamp
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        server_default=text("NOW()"),
        nullable=False,
    )

    # Table configuration
    __table_args__ = (
        Index("idx_audit_logs_action", "action"),
        Index("idx_audit_logs_record_id", "record_id"),
        Index("idx_audit_logs_timestamp", "timestamp", postgresql_using="btree"),
        Index("idx_audit_logs_user_id", "user_id"),
    )
