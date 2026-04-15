"""
Pydantic schemas for data extraction and validation.
Defines all data models for forms, emails, invoices, and extraction results.
"""

from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Any, Literal
from uuid import UUID, uuid4

from pydantic import BaseModel, EmailStr, Field, field_validator


class RecordType(str, Enum):
    """Type of data record."""
    FORM = "FORM"
    EMAIL = "EMAIL"
    INVOICE = "INVOICE"


class EmailType(str, Enum):
    """Type of email content."""
    CLIENT_INQUIRY = "client_inquiry"
    INVOICE_NOTIFICATION = "invoice_notification"


class Priority(str, Enum):
    """Priority level for requests."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class ExtractionStatus(str, Enum):
    """Status of an extraction record."""
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    EDITED = "edited"
    EXPORTED = "exported"


class ContactFormData(BaseModel):
    """Data extracted from HTML contact forms."""

    full_name: str = Field(..., min_length=1, description="Full name of the contact")
    email: EmailStr = Field(..., description="Email address")
    phone: str | None = Field(default=None, description="Phone number")
    company: str | None = Field(default=None, description="Company name")
    service_interest: str | None = Field(default=None, description="Service of interest")
    message: str | None = Field(default=None, description="Contact message")
    submission_date: datetime | None = Field(default=None, description="Form submission date")
    priority: Priority = Field(default=Priority.MEDIUM, description="Request priority")

    @field_validator("phone", mode="before")
    @classmethod
    def clean_phone(cls, v: str | None) -> str | None:
        """Clean and validate phone number format."""
        if v is None:
            return None
        # Remove common formatting characters
        cleaned = v.replace(" ", "").replace("-", "").replace("(", "").replace(")", "")
        # Return original format for display, but ensure it's valid
        if cleaned and not cleaned.replace("+", "").isdigit():
            return None
        return v


class InvoiceItem(BaseModel):
    """Single line item on an invoice."""

    description: str = Field(..., description="Item description")
    quantity: int = Field(..., ge=0, description="Item quantity")
    unit_price: Decimal = Field(..., ge=0, description="Price per unit")
    total: Decimal = Field(..., ge=0, description="Line total")


class InvoiceData(BaseModel):
    """Data extracted from HTML invoices."""

    invoice_number: str = Field(..., description="Unique invoice number")
    invoice_date: datetime = Field(..., description="Invoice issue date")
    client_name: str = Field(..., description="Client/customer name")
    client_address: str | None = Field(default=None, description="Client address")
    client_vat_number: str | None = Field(default=None, description="Client VAT number (ΑΦΜ)")
    items: list[InvoiceItem] = Field(default_factory=list, description="Invoice line items")
    net_amount: Decimal = Field(..., ge=0, description="Net amount before VAT")
    vat_rate: Decimal = Field(default=Decimal("24"), description="VAT rate percentage")
    vat_amount: Decimal = Field(..., ge=0, description="VAT amount")
    total_amount: Decimal = Field(..., ge=0, description="Total amount including VAT")
    payment_terms: str | None = Field(default=None, description="Payment terms")
    notes: str | None = Field(default=None, description="Additional notes")

    @field_validator("vat_rate", mode="before")
    @classmethod
    def validate_vat_rate(cls, v: Any) -> Decimal:
        """Ensure VAT rate is a valid decimal."""
        if isinstance(v, (int, float)):
            return Decimal(str(v))
        return Decimal(v) if v else Decimal("24")


class EmailData(BaseModel):
    """Data extracted from EML email files."""

    email_type: EmailType = Field(..., description="Type of email content")
    sender_name: str | None = Field(default=None, description="Sender's name")
    sender_email: EmailStr = Field(..., description="Sender's email address")
    recipient_email: str = Field(..., description="Recipient email address")
    subject: str = Field(..., description="Email subject line")
    date_sent: datetime = Field(..., description="Email send date")
    body: str = Field(..., description="Email body content")

    # For client inquiries
    phone: str | None = Field(default=None, description="Contact phone from email")
    company: str | None = Field(default=None, description="Company name from email")
    position: str | None = Field(default=None, description="Job position/title")
    service_interest: str | None = Field(default=None, description="Service of interest")

    # For invoice notifications
    invoice_number: str | None = Field(default=None, description="Referenced invoice number")
    invoice_amount: Decimal | None = Field(default=None, description="Invoice total amount")
    vendor_name: str | None = Field(default=None, description="Vendor/supplier name")


class ExtractionResult(BaseModel):
    """Result of a data extraction operation."""

    id: UUID = Field(default_factory=uuid4, description="Unique extraction ID")
    source_file: str = Field(..., description="Source file path")
    record_type: RecordType = Field(..., description="Type of extracted record")
    extracted_at: datetime = Field(default_factory=datetime.utcnow, description="Extraction timestamp")
    confidence_score: float = Field(
        default=1.0,
        ge=0.0,
        le=1.0,
        description="Extraction confidence (1.0 for rule-based, varies for AI)"
    )
    warnings: list[str] = Field(default_factory=list, description="Extraction warnings")
    errors: list[str] = Field(default_factory=list, description="Extraction errors")

    # Extracted data (one of these will be populated)
    form_data: ContactFormData | None = Field(default=None)
    email_data: EmailData | None = Field(default=None)
    invoice_data: InvoiceData | None = Field(default=None)

    @property
    def has_errors(self) -> bool:
        """Check if extraction has errors."""
        return len(self.errors) > 0

    @property
    def has_warnings(self) -> bool:
        """Check if extraction has warnings."""
        return len(self.warnings) > 0

    @property
    def data(self) -> ContactFormData | EmailData | InvoiceData | None:
        """Get the extracted data regardless of type."""
        return self.form_data or self.email_data or self.invoice_data


class ExtractionRecord(BaseModel):
    """
    A record ready for human review and export.
    Contains the extraction result plus workflow status.
    """

    id: UUID = Field(default_factory=uuid4, description="Record ID")
    extraction: ExtractionResult = Field(..., description="Extraction result")
    status: ExtractionStatus = Field(
        default=ExtractionStatus.PENDING,
        description="Current workflow status"
    )
    reviewed_by: str | None = Field(default=None, description="User who reviewed")
    reviewed_at: datetime | None = Field(default=None, description="Review timestamp")
    review_notes: str | None = Field(default=None, description="Review notes")
    edited_data: dict[str, Any] | None = Field(
        default=None,
        description="User-edited data (if status is EDITED)"
    )
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    @property
    def is_pending(self) -> bool:
        """Check if record is pending review."""
        return self.status == ExtractionStatus.PENDING

    @property
    def is_approved(self) -> bool:
        """Check if record is approved."""
        return self.status in (ExtractionStatus.APPROVED, ExtractionStatus.EDITED)

    @property
    def final_data(self) -> dict[str, Any]:
        """Get the final data (edited if available, otherwise original)."""
        if self.edited_data:
            return self.edited_data
        data = self.extraction.data
        return data.model_dump() if data else {}


# Request/Response schemas for API
class ApproveRequest(BaseModel):
    """Request to approve an extraction record."""
    notes: str | None = Field(default=None, description="Approval notes")


class RejectRequest(BaseModel):
    """Request to reject an extraction record."""
    reason: str = Field(..., min_length=1, description="Rejection reason")


class EditRequest(BaseModel):
    """Request to edit an extraction record."""
    data: dict[str, Any] = Field(..., description="Edited data")
    notes: str | None = Field(default=None, description="Edit notes")


class ExportRequest(BaseModel):
    """Request to export records."""
    record_ids: list[UUID] | None = Field(
        default=None,
        description="Specific record IDs to export (None = all approved)"
    )
    format: Literal["csv", "xlsx", "json"] = Field(default="csv", description="Export format (csv, xlsx, json)")
    include_rejected: bool = Field(default=False, description="Include rejected records")


class BatchApproveRequest(BaseModel):
    """Request to approve multiple records."""
    record_ids: list[UUID] = Field(..., description="List of record UUIDs to approve", alias="ids")
    notes: str | None = Field(default=None, description="Approval notes for all records")

    model_config = {
        "populate_by_name": True
    }


class BatchRejectRequest(BaseModel):
    """Request to reject multiple records."""
    record_ids: list[UUID] = Field(..., description="List of record UUIDs to reject", alias="ids")
    reason: str = Field(..., min_length=1, description="Rejection reason for all records")

    model_config = {
        "populate_by_name": True
    }
