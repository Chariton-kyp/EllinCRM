"""
Tests for base extractor class.
"""

import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch
from uuid import UUID

from app.extractors.base import BaseExtractor
from app.models.schemas import (
    ContactFormData,
    EmailData,
    EmailType,
    ExtractionResult,
    InvoiceData,
    RecordType,
)
from datetime import datetime, timezone
from decimal import Decimal


class ConcreteExtractor(BaseExtractor):
    """Concrete implementation for testing."""

    record_type = RecordType.FORM

    def extract(self, file_path: Path) -> ExtractionResult:
        """Extract data from file."""
        content = self.read_file(file_path)
        data = ContactFormData(
            full_name="Test User",
            email="test@example.com",
        )
        return self._create_result(
            source_file=str(file_path),
            data=data,
            confidence=0.95,
        )

    def validate(self, data: ContactFormData) -> tuple[bool, list[str]]:
        """Validate extracted data."""
        messages = []
        if not data.full_name:
            messages.append("Missing full name")
        if not data.email:
            messages.append("Missing email")
        return len(messages) == 0, messages


class TestBaseExtractor:
    """Tests for BaseExtractor abstract class."""

    @pytest.fixture
    def extractor(self) -> ConcreteExtractor:
        """Create a concrete extractor instance."""
        return ConcreteExtractor()

    @pytest.fixture
    def temp_file(self, tmp_path: Path) -> Path:
        """Create a temporary test file."""
        file = tmp_path / "test.html"
        file.write_text("<html><body>Test content</body></html>", encoding="utf-8")
        return file

    def test_extractor_creation(self, extractor: ConcreteExtractor) -> None:
        """Test extractor can be instantiated."""
        assert extractor is not None
        assert extractor.record_type == RecordType.FORM
        assert hasattr(extractor, "logger")

    def test_read_file_success(
        self, extractor: ConcreteExtractor, temp_file: Path
    ) -> None:
        """Test reading a file successfully."""
        content = extractor.read_file(temp_file)
        assert "<html>" in content
        assert "Test content" in content

    def test_read_file_not_found(self, extractor: ConcreteExtractor) -> None:
        """Test reading a non-existent file."""
        with pytest.raises(FileNotFoundError, match="File not found"):
            extractor.read_file(Path("/nonexistent/file.html"))

    def test_read_file_utf8(
        self, extractor: ConcreteExtractor, tmp_path: Path
    ) -> None:
        """Test reading a file with Greek characters."""
        file = tmp_path / "greek.html"
        file.write_text("<p>Καλημέρα κόσμε</p>", encoding="utf-8")

        content = extractor.read_file(file)
        assert "Καλημέρα" in content
        assert "κόσμε" in content


class TestCreateResult:
    """Tests for _create_result method."""

    @pytest.fixture
    def extractor(self) -> ConcreteExtractor:
        """Create extractor instance."""
        return ConcreteExtractor()

    def test_create_result_with_form_data(
        self, extractor: ConcreteExtractor
    ) -> None:
        """Test creating result with ContactFormData."""
        form_data = ContactFormData(
            full_name="Μαρία Παπαδοπούλου",
            email="maria@example.gr",
            phone="210-1234567",
            company="Tech Solutions",
            service_interest="CRM",
            message="Χρειάζομαι βοήθεια",
        )

        result = extractor._create_result(
            source_file="form.html",
            data=form_data,
            confidence=0.92,
            warnings=["Low phone confidence"],
        )

        assert result.source_file == "form.html"
        assert result.record_type == RecordType.FORM
        assert result.form_data is not None
        assert result.form_data.full_name == "Μαρία Παπαδοπούλου"
        assert result.confidence_score == 0.92
        assert "Low phone confidence" in result.warnings

    def test_create_result_with_email_data(self) -> None:
        """Test creating result with EmailData."""

        class EmailExtractor(BaseExtractor):
            record_type = RecordType.EMAIL

            def extract(self, file_path: Path) -> ExtractionResult:
                return ExtractionResult(
                    source_file="test.eml",
                    record_type=RecordType.EMAIL,
                    confidence_score=0.9,
                )

            def validate(self, data: EmailData) -> tuple[bool, list[str]]:
                return True, []

        extractor = EmailExtractor()
        email_data = EmailData(
            email_type=EmailType.CLIENT_INQUIRY,
            sender_name="John Doe",
            sender_email="john@example.com",
            recipient_email="info@company.com",
            subject="Inquiry",
            date_sent=datetime.now(timezone.utc),
            body="Hello",
        )

        result = extractor._create_result(
            source_file="email.eml",
            data=email_data,
            confidence=0.88,
        )

        assert result.record_type == RecordType.EMAIL
        assert result.email_data is not None
        assert result.email_data.sender_name == "John Doe"

    def test_create_result_with_invoice_data(self) -> None:
        """Test creating result with InvoiceData."""

        class InvoiceExtractor(BaseExtractor):
            record_type = RecordType.INVOICE

            def extract(self, file_path: Path) -> ExtractionResult:
                return ExtractionResult(
                    source_file="test.html",
                    record_type=RecordType.INVOICE,
                    confidence_score=0.9,
                )

            def validate(self, data: InvoiceData) -> tuple[bool, list[str]]:
                return True, []

        extractor = InvoiceExtractor()
        invoice_data = InvoiceData(
            invoice_number="INV-001",
            invoice_date=datetime.now(timezone.utc),
            client_name="Test Client",
            net_amount=Decimal("1000.00"),
            vat_rate=Decimal("24"),
            vat_amount=Decimal("240.00"),
            total_amount=Decimal("1240.00"),
        )

        result = extractor._create_result(
            source_file="invoice.html",
            data=invoice_data,
            confidence=0.95,
        )

        assert result.record_type == RecordType.INVOICE
        assert result.invoice_data is not None
        assert result.invoice_data.invoice_number == "INV-001"

    def test_create_result_without_data(
        self, extractor: ConcreteExtractor
    ) -> None:
        """Test creating result without data (error case)."""
        result = extractor._create_result(
            source_file="empty.html",
            data=None,
            confidence=0.0,
            errors=["Failed to extract data"],
        )

        assert result.form_data is None
        assert result.email_data is None
        assert result.invoice_data is None
        assert result.confidence_score == 0.0
        assert "Failed to extract data" in result.errors

    def test_create_result_generates_uuid(
        self, extractor: ConcreteExtractor
    ) -> None:
        """Test that result has a valid UUID."""
        form_data = ContactFormData(
            full_name="Test",
            email="test@example.com",
        )

        result = extractor._create_result(
            source_file="test.html",
            data=form_data,
        )

        assert result.id is not None
        assert isinstance(result.id, UUID)

    def test_create_result_empty_warnings_errors(
        self, extractor: ConcreteExtractor
    ) -> None:
        """Test result has empty lists when no warnings/errors."""
        form_data = ContactFormData(
            full_name="Test",
            email="test@example.com",
        )

        result = extractor._create_result(
            source_file="test.html",
            data=form_data,
        )

        assert result.warnings == []
        assert result.errors == []


class TestLogExtraction:
    """Tests for _log_extraction method."""

    @pytest.fixture
    def extractor(self) -> ConcreteExtractor:
        """Create extractor instance."""
        return ConcreteExtractor()

    def test_log_extraction_success(
        self, extractor: ConcreteExtractor
    ) -> None:
        """Test logging successful extraction."""
        with patch("app.extractors.base.audit_logger") as mock_audit:
            extractor._log_extraction(
                file_path=Path("test.html"),
                extraction_id="test-123",
                success=True,
                confidence=0.95,
            )

            mock_audit.log_extraction_started.assert_called_once_with(
                file_path="test.html",
                file_type="FORM",
                extraction_id="test-123",
            )
            mock_audit.log_extraction_completed.assert_called_once_with(
                extraction_id="test-123",
                success=True,
                confidence_score=0.95,
                error_message=None,
            )

    def test_log_extraction_failure(
        self, extractor: ConcreteExtractor
    ) -> None:
        """Test logging failed extraction."""
        with patch("app.extractors.base.audit_logger") as mock_audit:
            extractor._log_extraction(
                file_path=Path("bad.html"),
                extraction_id="test-456",
                success=False,
                error_message="Parse error",
            )

            mock_audit.log_extraction_completed.assert_called_once_with(
                extraction_id="test-456",
                success=False,
                confidence_score=None,
                error_message="Parse error",
            )


class TestValidation:
    """Tests for validate method."""

    @pytest.fixture
    def extractor(self) -> ConcreteExtractor:
        """Create extractor instance."""
        return ConcreteExtractor()

    def test_validate_valid_data(self, extractor: ConcreteExtractor) -> None:
        """Test validating valid data."""
        data = ContactFormData(
            full_name="Test User",
            email="test@example.com",
        )

        is_valid, messages = extractor.validate(data)

        assert is_valid is True
        assert messages == []

    def test_validate_valid_data_passes(self, extractor: ConcreteExtractor) -> None:
        """Test validating valid data passes validation."""
        data = ContactFormData(
            full_name="Valid Name",
            email="test@example.com",
        )

        is_valid, messages = extractor.validate(data)

        assert is_valid is True
        assert messages == []


class TestExtractMethod:
    """Tests for extract method."""

    @pytest.fixture
    def extractor(self) -> ConcreteExtractor:
        """Create extractor instance."""
        return ConcreteExtractor()

    @pytest.fixture
    def temp_file(self, tmp_path: Path) -> Path:
        """Create a temporary test file."""
        file = tmp_path / "form.html"
        file.write_text("<form>Test form</form>", encoding="utf-8")
        return file

    def test_extract_returns_result(
        self, extractor: ConcreteExtractor, temp_file: Path
    ) -> None:
        """Test extract method returns ExtractionResult."""
        result = extractor.extract(temp_file)

        assert isinstance(result, ExtractionResult)
        assert result.form_data is not None
        assert result.confidence_score == 0.95

    def test_extract_file_not_found(
        self, extractor: ConcreteExtractor
    ) -> None:
        """Test extract with missing file."""
        with pytest.raises(FileNotFoundError):
            extractor.extract(Path("/nonexistent/form.html"))
