"""
Tests for Pydantic models/schemas.
"""

from datetime import datetime
from decimal import Decimal
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.models.schemas import (
    ContactFormData,
    EmailData,
    InvoiceData,
    InvoiceItem,
    ExtractionResult,
    ExtractionRecord,
    RecordType,
    Priority,
    ExtractionStatus,
    ApproveRequest,
    RejectRequest,
    EditRequest,
    ExportRequest,
)


class TestPriority:
    """Tests for Priority enum."""

    def test_priority_values(self) -> None:
        """Test priority enum values."""
        assert Priority.LOW.value == "low"
        assert Priority.MEDIUM.value == "medium"
        assert Priority.HIGH.value == "high"


class TestRecordType:
    """Tests for RecordType enum."""

    def test_record_type_values(self) -> None:
        """Test record type enum values."""
        assert RecordType.FORM.value == "FORM"
        assert RecordType.EMAIL.value == "EMAIL"
        assert RecordType.INVOICE.value == "INVOICE"


class TestExtractionStatus:
    """Tests for ExtractionStatus enum."""

    def test_status_values(self) -> None:
        """Test status enum values."""
        assert ExtractionStatus.PENDING.value == "pending"
        assert ExtractionStatus.APPROVED.value == "approved"
        assert ExtractionStatus.REJECTED.value == "rejected"
        assert ExtractionStatus.EDITED.value == "edited"
        assert ExtractionStatus.EXPORTED.value == "exported"


class TestContactFormData:
    """Tests for ContactFormData model."""

    def test_valid_minimal(self) -> None:
        """Test with minimal required fields."""
        form = ContactFormData(
            full_name="Test User",
            email="test@example.com",
        )
        assert form.full_name == "Test User"
        assert form.email == "test@example.com"

    def test_valid_complete(self) -> None:
        """Test with all fields."""
        form = ContactFormData(
            full_name="Νίκος Παπαδόπουλος",
            email="nikos@example.gr",
            phone="210-1234567",
            company="Test Company",
            service_interest="CRM System",
            message="Test message",
            submission_date=datetime.now(),
            priority=Priority.HIGH,
        )
        assert form.phone == "210-1234567"
        assert form.priority == Priority.HIGH

    def test_invalid_email(self) -> None:
        """Test that invalid email fails."""
        with pytest.raises(ValidationError):
            ContactFormData(
                full_name="Test",
                email="not-an-email",
            )

    def test_greek_characters(self) -> None:
        """Test Greek character support."""
        form = ContactFormData(
            full_name="Κώστας Παπαδόπουλος",
            email="kostas@example.gr",
            message="Καλημέρα, χρειαζόμαστε βοήθεια",
        )
        assert "Κώστας" in form.full_name
        assert "Καλημέρα" in form.message


class TestEmailData:
    """Tests for EmailData model."""

    def test_valid_email_data(self) -> None:
        """Test valid email data."""
        from app.models.schemas import EmailType
        email = EmailData(
            email_type=EmailType.CLIENT_INQUIRY,
            sender_name="Test Sender",
            sender_email="sender@example.com",
            recipient_email="info@ellincrm.gr",
            subject="Test Subject",
            date_sent=datetime.now(),
            body="Test body content",
        )
        assert email.sender_name == "Test Sender"
        assert email.subject == "Test Subject"

    def test_email_type_inquiry(self) -> None:
        """Test email with type inquiry."""
        from app.models.schemas import EmailType
        email = EmailData(
            email_type=EmailType.CLIENT_INQUIRY,
            sender_name="Test",
            sender_email="test@example.com",
            recipient_email="info@ellincrm.gr",
            subject="Inquiry",
            date_sent=datetime.now(),
            body="Body",
        )
        assert email.email_type == EmailType.CLIENT_INQUIRY


class TestInvoiceItem:
    """Tests for InvoiceItem model."""

    def test_valid_item(self) -> None:
        """Test valid invoice item."""
        item = InvoiceItem(
            description="Χαρτί Α4",
            quantity=20,
            unit_price=Decimal("12.00"),
            total=Decimal("240.00"),
        )
        assert item.description == "Χαρτί Α4"
        assert item.quantity == 20
        assert item.total == Decimal("240.00")


class TestInvoiceData:
    """Tests for InvoiceData model."""

    def test_valid_invoice(self) -> None:
        """Test valid invoice data."""
        invoice = InvoiceData(
            invoice_number="TF-2024-001",
            invoice_date=datetime.now(),
            client_name="Test Client",
            net_amount=Decimal("1000.00"),
            vat_rate=Decimal("24"),
            vat_amount=Decimal("240.00"),
            total_amount=Decimal("1240.00"),
        )
        assert invoice.invoice_number == "TF-2024-001"
        assert invoice.vat_rate == Decimal("24")

    def test_invoice_with_items(self) -> None:
        """Test invoice with line items."""
        items = [
            InvoiceItem(
                description="Item 1",
                quantity=1,
                unit_price=Decimal("100"),
                total=Decimal("100"),
            ),
            InvoiceItem(
                description="Item 2",
                quantity=2,
                unit_price=Decimal("50"),
                total=Decimal("100"),
            ),
        ]
        invoice = InvoiceData(
            invoice_number="TF-2024-002",
            invoice_date=datetime.now(),
            client_name="Client",
            net_amount=Decimal("200"),
            vat_rate=Decimal("24"),
            vat_amount=Decimal("48"),
            total_amount=Decimal("248"),
            items=items,
        )
        assert len(invoice.items) == 2


class TestExtractionResult:
    """Tests for ExtractionResult model."""

    def test_result_with_form_data(self) -> None:
        """Test extraction result with form data."""
        form = ContactFormData(
            full_name="Test",
            email="test@test.com",
        )
        result = ExtractionResult(
            source_file="form_1.html",
            record_type=RecordType.FORM,
            form_data=form,
            confidence_score=0.95,
        )
        assert result.record_type == RecordType.FORM
        assert result.form_data is not None
        assert result.confidence_score == 0.95

    def test_result_with_errors(self) -> None:
        """Test extraction result with errors."""
        result = ExtractionResult(
            source_file="bad_file.html",
            record_type=RecordType.FORM,
            errors=["Missing required field", "Invalid format"],
            confidence_score=0.0,
        )
        assert result.has_errors is True
        assert len(result.errors) == 2

    def test_result_with_warnings(self) -> None:
        """Test extraction result with warnings."""
        result = ExtractionResult(
            source_file="file.html",
            record_type=RecordType.FORM,
            warnings=["Low confidence"],
            confidence_score=0.6,
        )
        assert len(result.warnings) == 1


class TestApproveRequest:
    """Tests for ApproveRequest model."""

    def test_empty_approve(self) -> None:
        """Test approve with no notes."""
        request = ApproveRequest()
        assert request.notes is None

    def test_approve_with_notes(self) -> None:
        """Test approve with notes."""
        request = ApproveRequest(notes="Looks good!")
        assert request.notes == "Looks good!"


class TestRejectRequest:
    """Tests for RejectRequest model."""

    def test_reject_with_reason(self) -> None:
        """Test reject with reason."""
        request = RejectRequest(reason="Data is incorrect")
        assert request.reason == "Data is incorrect"


class TestEditRequest:
    """Tests for EditRequest model."""

    def test_edit_with_data(self) -> None:
        """Test edit with new data."""
        new_data = {"full_name": "Updated Name", "email": "new@example.com"}
        request = EditRequest(data=new_data)
        assert request.data["full_name"] == "Updated Name"

    def test_edit_with_notes(self) -> None:
        """Test edit with notes."""
        request = EditRequest(data={"test": "value"}, notes="Fixed typo")
        assert request.notes == "Fixed typo"


class TestExportRequest:
    """Tests for ExportRequest model."""

    def test_csv_export(self) -> None:
        """Test CSV export request."""
        request = ExportRequest(format="csv")
        assert request.format == "csv"

    def test_xlsx_export(self) -> None:
        """Test Excel export request."""
        request = ExportRequest(format="xlsx")
        assert request.format == "xlsx"

    def test_json_export(self) -> None:
        """Test JSON export request."""
        request = ExportRequest(format="json")
        assert request.format == "json"

    def test_export_with_record_ids(self) -> None:
        """Test export with specific record IDs."""
        ids = [uuid4(), uuid4()]
        request = ExportRequest(format="csv", record_ids=ids)
        assert len(request.record_ids) == 2

    def test_include_rejected(self) -> None:
        """Test export including rejected records."""
        request = ExportRequest(format="csv", include_rejected=True)
        assert request.include_rejected is True
