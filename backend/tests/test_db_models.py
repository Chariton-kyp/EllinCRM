"""
Tests for database ORM models.
"""

import uuid
from datetime import datetime, timezone, timedelta
from decimal import Decimal
from unittest.mock import MagicMock

import pytest

from app.db.models import Base, ExtractionRecordDB
from app.models.schemas import (
    ContactFormData,
    EmailData,
    EmailType,
    ExtractionResult,
    InvoiceData,
    RecordType,
    Priority,
)


class TestBase:
    """Tests for the Base declarative class."""

    def test_base_exists(self) -> None:
        """Test that Base class exists."""
        assert Base is not None

    def test_base_is_declarative(self) -> None:
        """Test that Base has metadata."""
        assert hasattr(Base, "metadata")


class TestExtractionRecordDB:
    """Tests for ExtractionRecordDB model."""

    @pytest.fixture
    def sample_form_record(self) -> ExtractionRecordDB:
        """Create a sample form record."""
        return ExtractionRecordDB(
            id=uuid.uuid4(),
            source_file="/app/data/forms/form_1.html",
            record_type="FORM",
            extracted_data={
                "full_name": "Κώστας Παπαδόπουλος",
                "email": "kostas@example.gr",
                "phone": "210-1234567",
                "company": "Tech Solutions",
                "service_interest": "CRM System",
                "message": "Χρειαζόμαστε βοήθεια",
                "priority": "high",
                "submission_date": "2024-01-15T10:30:00",
            },
            confidence_score=0.92,
            warnings=["Low phone confidence"],
            errors=[],
            status="pending",
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )

    @pytest.fixture
    def sample_email_record(self) -> ExtractionRecordDB:
        """Create a sample email record."""
        return ExtractionRecordDB(
            id=uuid.uuid4(),
            source_file="/app/data/emails/email_01.eml",
            record_type="EMAIL",
            extracted_data={
                "email_type": "client_inquiry",
                "sender_name": "Νίκος Γεωργίου",
                "sender_email": "nikos@company.gr",
                "recipient_email": "info@ellincrm.gr",
                "subject": "Αίτημα πληροφοριών",
                "date_sent": "2024-01-15T14:30:00",
                "body": "Καλησπέρα, ενδιαφέρομαι για τις υπηρεσίες σας.",
                "service_interest": "consulting",
            },
            confidence_score=0.88,
            warnings=[],
            errors=[],
            status="pending",
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )

    @pytest.fixture
    def sample_invoice_record(self) -> ExtractionRecordDB:
        """Create a sample invoice record."""
        return ExtractionRecordDB(
            id=uuid.uuid4(),
            source_file="/app/data/invoices/invoice_001.html",
            record_type="INVOICE",
            extracted_data={
                "invoice_number": "TF-2024-001",
                "invoice_date": "2024-01-15",
                "client_name": "Office Solutions Ltd",
                "net_amount": "1000.00",
                "vat_rate": "24",
                "vat_amount": "240.00",
                "total_amount": "1240.00",
                "payment_terms": "30 days",
                "notes": "Test invoice",
            },
            confidence_score=0.95,
            warnings=[],
            errors=[],
            status="approved",
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )

    def test_tablename(self) -> None:
        """Test table name is set correctly."""
        assert ExtractionRecordDB.__tablename__ == "extraction_records"

    def test_record_creation(self, sample_form_record: ExtractionRecordDB) -> None:
        """Test record creation with all fields."""
        assert sample_form_record.id is not None
        assert sample_form_record.source_file == "/app/data/forms/form_1.html"
        assert sample_form_record.record_type == "FORM"
        assert sample_form_record.status == "pending"
        assert sample_form_record.confidence_score == 0.92

    def test_record_with_greek_data(self, sample_form_record: ExtractionRecordDB) -> None:
        """Test Greek text is preserved in extracted data."""
        data = sample_form_record.extracted_data
        assert data["full_name"] == "Κώστας Παπαδόπουλος"
        assert data["message"] == "Χρειαζόμαστε βοήθεια"

    def test_final_data_without_edits(self, sample_form_record: ExtractionRecordDB) -> None:
        """Test final_data returns extracted_data when no edits."""
        sample_form_record.edited_data = None
        assert sample_form_record.final_data == sample_form_record.extracted_data

    def test_final_data_with_edits(self, sample_form_record: ExtractionRecordDB) -> None:
        """Test final_data returns edited_data when present."""
        edited = {"full_name": "Updated Name", "email": "new@example.com"}
        sample_form_record.edited_data = edited
        assert sample_form_record.final_data == edited

    def test_to_pydantic_form(self, sample_form_record: ExtractionRecordDB) -> None:
        """Test conversion to Pydantic model for form record."""
        record = sample_form_record.to_pydantic()

        assert record.id == sample_form_record.id
        assert record.status.value == "pending"
        assert record.extraction is not None
        assert record.extraction.record_type == RecordType.FORM
        assert record.extraction.form_data is not None
        assert record.extraction.form_data.full_name == "Κώστας Παπαδόπουλος"
        assert record.extraction.email_data is None
        assert record.extraction.invoice_data is None

    def test_to_pydantic_email(self, sample_email_record: ExtractionRecordDB) -> None:
        """Test conversion to Pydantic model for email record."""
        record = sample_email_record.to_pydantic()

        assert record.extraction.record_type == RecordType.EMAIL
        assert record.extraction.email_data is not None
        assert record.extraction.email_data.sender_name == "Νίκος Γεωργίου"
        assert record.extraction.form_data is None
        assert record.extraction.invoice_data is None

    def test_to_pydantic_invoice(self, sample_invoice_record: ExtractionRecordDB) -> None:
        """Test conversion to Pydantic model for invoice record."""
        record = sample_invoice_record.to_pydantic()

        assert record.extraction.record_type == RecordType.INVOICE
        assert record.extraction.invoice_data is not None
        assert record.extraction.invoice_data.invoice_number == "TF-2024-001"
        assert record.extraction.form_data is None
        assert record.extraction.email_data is None

    def test_to_pydantic_with_warnings(self, sample_form_record: ExtractionRecordDB) -> None:
        """Test conversion preserves warnings."""
        record = sample_form_record.to_pydantic()
        assert "Low phone confidence" in record.extraction.warnings

    def test_to_pydantic_with_review_info(self, sample_form_record: ExtractionRecordDB) -> None:
        """Test conversion includes review information."""
        sample_form_record.status = "approved"
        sample_form_record.reviewed_by = "admin"
        sample_form_record.reviewed_at = datetime.now(timezone.utc)
        sample_form_record.review_notes = "All good"

        record = sample_form_record.to_pydantic()
        assert record.reviewed_by == "admin"
        assert record.reviewed_at is not None
        assert record.review_notes == "All good"


class TestFromExtractionResult:
    """Tests for ExtractionRecordDB.from_extraction_result."""

    def test_from_form_extraction(self) -> None:
        """Test creating record from form extraction result."""
        form_data = ContactFormData(
            full_name="Test User",
            email="test@example.com",
            phone="123-456-7890",
            company="Test Co",
            service_interest="web",
            message="Hello",
            priority=Priority.HIGH,
            submission_date=datetime.now(timezone.utc),
        )

        result = ExtractionResult(
            id=uuid.uuid4(),
            source_file="form_1.html",
            record_type=RecordType.FORM,
            form_data=form_data,
            confidence_score=0.95,
            warnings=["Low confidence on phone"],
            errors=[],
        )

        record = ExtractionRecordDB.from_extraction_result(result)

        assert record.id == result.id
        assert record.source_file == "form_1.html"
        assert record.record_type == "FORM"
        assert record.status == "pending"
        assert record.confidence_score == 0.95
        assert record.warnings == ["Low confidence on phone"]
        assert record.extracted_data["full_name"] == "Test User"

    def test_from_email_extraction(self) -> None:
        """Test creating record from email extraction result."""
        email_data = EmailData(
            email_type=EmailType.CLIENT_INQUIRY,
            sender_name="John",
            sender_email="john@example.com",
            recipient_email="info@company.com",
            subject="Inquiry",
            date_sent=datetime.now(timezone.utc),
            body="Hello",
        )

        result = ExtractionResult(
            id=uuid.uuid4(),
            source_file="email_1.eml",
            record_type=RecordType.EMAIL,
            email_data=email_data,
            confidence_score=0.88,
        )

        record = ExtractionRecordDB.from_extraction_result(result)

        assert record.record_type == "EMAIL"
        assert record.extracted_data["sender_name"] == "John"

    def test_from_invoice_extraction(self) -> None:
        """Test creating record from invoice extraction result."""
        invoice_data = InvoiceData(
            invoice_number="INV-001",
            invoice_date=datetime.now(timezone.utc),
            client_name="Client Co",
            net_amount=Decimal("1000.00"),
            vat_rate=Decimal("24"),
            vat_amount=Decimal("240.00"),
            total_amount=Decimal("1240.00"),
        )

        result = ExtractionResult(
            id=uuid.uuid4(),
            source_file="invoice_1.html",
            record_type=RecordType.INVOICE,
            invoice_data=invoice_data,
            confidence_score=0.92,
        )

        record = ExtractionRecordDB.from_extraction_result(result)

        assert record.record_type == "INVOICE"
        assert record.extracted_data["invoice_number"] == "INV-001"
        # Decimal should be serialized to string
        assert record.extracted_data["net_amount"] == "1000.00"

    def test_from_extraction_result_no_data(self) -> None:
        """Test creating record from extraction with no data raises error."""
        result = ExtractionResult(
            id=uuid.uuid4(),
            source_file="empty.html",
            record_type=RecordType.FORM,
            confidence_score=0.0,
            errors=["No data extracted"],
        )

        with pytest.raises(ValueError, match="ExtractionResult has no data"):
            ExtractionRecordDB.from_extraction_result(result)

    def test_datetime_serialization(self) -> None:
        """Test datetime fields are serialized correctly."""
        form_data = ContactFormData(
            full_name="Test",
            email="test@example.com",
            submission_date=datetime(2024, 1, 15, 10, 30, 0, tzinfo=timezone.utc),
        )

        result = ExtractionResult(
            id=uuid.uuid4(),
            source_file="form.html",
            record_type=RecordType.FORM,
            form_data=form_data,
            confidence_score=0.9,
        )

        record = ExtractionRecordDB.from_extraction_result(result)

        # Datetime should be serialized to ISO format
        assert "2024-01-15" in record.extracted_data["submission_date"]

    def test_greek_text_preserved(self) -> None:
        """Test Greek text is preserved during serialization."""
        form_data = ContactFormData(
            full_name="Μαρία Παπαδοπούλου",
            email="maria@example.gr",
            message="Καλημέρα, θέλω πληροφορίες",
        )

        result = ExtractionResult(
            id=uuid.uuid4(),
            source_file="form.html",
            record_type=RecordType.FORM,
            form_data=form_data,
            confidence_score=0.9,
        )

        record = ExtractionRecordDB.from_extraction_result(result)

        assert record.extracted_data["full_name"] == "Μαρία Παπαδοπούλου"
        assert "Καλημέρα" in record.extracted_data["message"]


class TestRecordStatuses:
    """Tests for record status transitions."""

    @pytest.fixture
    def pending_record(self) -> ExtractionRecordDB:
        """Create a pending record."""
        return ExtractionRecordDB(
            id=uuid.uuid4(),
            source_file="test.html",
            record_type="FORM",
            extracted_data={"test": "data"},
            status="pending",
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )

    def test_pending_status(self, pending_record: ExtractionRecordDB) -> None:
        """Test record starts with pending status."""
        assert pending_record.status == "pending"

    def test_approved_status(self, pending_record: ExtractionRecordDB) -> None:
        """Test record can be set to approved."""
        pending_record.status = "approved"
        assert pending_record.status == "approved"

    def test_rejected_status(self, pending_record: ExtractionRecordDB) -> None:
        """Test record can be set to rejected."""
        pending_record.status = "rejected"
        pending_record.rejection_reason = "Invalid data"
        assert pending_record.status == "rejected"
        assert pending_record.rejection_reason == "Invalid data"

    def test_edited_status(self, pending_record: ExtractionRecordDB) -> None:
        """Test record can be set to edited."""
        pending_record.status = "edited"
        pending_record.edited_data = {"new": "data"}
        assert pending_record.status == "edited"
        assert pending_record.edited_data is not None

    def test_exported_status(self, pending_record: ExtractionRecordDB) -> None:
        """Test record can be set to exported."""
        pending_record.status = "exported"
        assert pending_record.status == "exported"


class TestRecordConfidenceScore:
    """Tests for confidence score validation."""

    def test_confidence_score_default(self) -> None:
        """Test default confidence score when explicitly set."""
        # Note: Default only applies at database level (server_default)
        # When creating directly in Python, we must provide a value
        record = ExtractionRecordDB(
            id=uuid.uuid4(),
            source_file="test.html",
            record_type="FORM",
            extracted_data={},
            confidence_score=1.0,  # Explicitly set default
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        assert record.confidence_score == 1.0

    def test_confidence_score_range(self) -> None:
        """Test confidence score within valid range."""
        record = ExtractionRecordDB(
            id=uuid.uuid4(),
            source_file="test.html",
            record_type="FORM",
            extracted_data={},
            confidence_score=0.5,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        assert 0 <= record.confidence_score <= 1

    def test_low_confidence_warning(self) -> None:
        """Test record with low confidence has warnings."""
        record = ExtractionRecordDB(
            id=uuid.uuid4(),
            source_file="test.html",
            record_type="FORM",
            extracted_data={},
            confidence_score=0.3,
            warnings=["Low extraction confidence"],
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        assert record.confidence_score < 0.5
        assert len(record.warnings) > 0
