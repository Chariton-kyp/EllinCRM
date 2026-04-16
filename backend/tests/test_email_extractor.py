"""
Unit tests for EmailExtractor.
"""

from datetime import datetime, UTC
from pathlib import Path
from tempfile import NamedTemporaryFile

import pytest

from app.extractors.email_extractor import EmailExtractor
from app.models.schemas import EmailType, RecordType


class TestEmailExtractor:
    """Tests for the EmailExtractor class."""

    @pytest.fixture
    def extractor(self) -> EmailExtractor:
        """Create an EmailExtractor instance."""
        return EmailExtractor()

    def test_extract_from_sample_eml(
        self, extractor: EmailExtractor, sample_email_eml: str
    ) -> None:
        """Test extraction from sample EML content."""
        with NamedTemporaryFile(mode="w", suffix=".eml", delete=False, encoding="utf-8") as f:
            f.write(sample_email_eml)
            f.flush()
            file_path = Path(f.name)

        try:
            result = extractor.extract(file_path)

            assert result.record_type == RecordType.EMAIL
            assert not result.has_errors
            assert result.email_data is not None

            data = result.email_data
            assert data.sender_email == "test@example.gr"
            assert data.email_type == EmailType.CLIENT_INQUIRY
            assert "Test User" in (data.sender_name or "")
            assert result.confidence_score >= 0.7
        finally:
            file_path.unlink()

    def test_extract_client_inquiry(self, extractor: EmailExtractor, emails_path: Path) -> None:
        """Test extraction from a client inquiry email."""
        email_file = emails_path / "email_01.eml"
        if not email_file.exists():
            pytest.skip("Dummy data not available")

        result = extractor.extract(email_file)

        assert result.record_type == RecordType.EMAIL
        assert not result.has_errors
        assert result.email_data is not None

        data = result.email_data
        assert data.email_type == EmailType.CLIENT_INQUIRY
        assert "nikos@tavernaparadeisos.gr" in data.sender_email
        # Company might be extracted from body or not, depending on format
        # The important thing is extraction succeeded without errors

    def test_extract_invoice_notification(
        self, extractor: EmailExtractor, emails_path: Path
    ) -> None:
        """Test the invoice-notification classification path using synthetic input.

        The shipped dummy-data email set now models 10 Greek-business inbound
        client inquiries only (post-rebrand), so no file in dummy_data/emails
        should classify as INVOICE_NOTIFICATION. This test instead verifies the
        classifier on a minimal synthetic EML, which keeps coverage of the
        branch without depending on fixture content.
        """
        synthetic = (
            "From: sender@vendor.gr\n"
            "To: info@ellincrm.gr\n"
            "Subject: Τιμολόγιο #EC-2025-777 — Πληρωμή απαιτείται\n"
            "Date: Mon, 20 Jan 2025 10:00:00 +0200\n"
            "Content-Type: text/plain; charset=UTF-8\n"
            "\n"
            "Αριθμός: EC-2025-777\n"
            "Καθαρή Αξία: €1,000.00\n"
            "Σύνολο: €1,240.00\n"
        )
        with NamedTemporaryFile(mode="w", suffix=".eml", delete=False, encoding="utf-8") as f:
            f.write(synthetic)
            f.flush()
            file_path = Path(f.name)
        try:
            result = extractor.extract(file_path)

            assert result.record_type == RecordType.EMAIL
            assert result.email_data is not None
            assert result.email_data.email_type == EmailType.INVOICE_NOTIFICATION
        finally:
            file_path.unlink()

    def test_extract_all_emails(self, extractor: EmailExtractor, emails_path: Path) -> None:
        """Test extraction from all dummy data emails."""
        email_files = list(emails_path.glob("*.eml"))
        if not email_files:
            pytest.skip("No email files found")

        inquiry_count = 0
        invoice_count = 0

        for email_file in email_files:
            result = extractor.extract(email_file)

            assert not result.has_errors, f"Errors in {email_file.name}: {result.errors}"
            assert result.email_data is not None, f"No data extracted from {email_file.name}"

            if result.email_data.email_type == EmailType.CLIENT_INQUIRY:
                inquiry_count += 1
            else:
                invoice_count += 1

        # Post-rebrand, the shipped dummy-data set is 10 Greek inbound
        # client inquiries; the invoice-notification classification path is
        # exercised separately in test_extract_invoice_notification.
        total = len(email_files)
        assert inquiry_count + invoice_count == total
        assert inquiry_count > 0, "No client inquiries found"

    def test_missing_file(self, extractor: EmailExtractor) -> None:
        """Test extraction from non-existent file."""
        result = extractor.extract(Path("/nonexistent/file.eml"))

        assert result.has_errors
        assert "not found" in result.errors[0].lower()
        assert result.confidence_score == 0.0

    def test_email_classification(self, extractor: EmailExtractor) -> None:
        """Test email classification logic."""
        # Invoice keywords
        assert (
            extractor._classify_email(
                "Τιμολόγιο #TF-2024-001", "Παρακαλώ βρείτε συνημμένο το τιμολόγιο. Ποσό: €1,000"
            )
            == EmailType.INVOICE_NOTIFICATION
        )

        # Client inquiry
        assert (
            extractor._classify_email(
                "Αίτημα για CRM", "Χρειαζόμαστε σύστημα CRM. Στοιχεία επικοινωνίας..."
            )
            == EmailType.CLIENT_INQUIRY
        )

    def test_amount_parsing(self, extractor: EmailExtractor) -> None:
        """Test amount string parsing."""
        from decimal import Decimal

        assert extractor._parse_amount("1,234.56") == Decimal("1234.56")
        assert extractor._parse_amount("1.234,56") == Decimal("1234.56")
        assert extractor._parse_amount("€100.00") == Decimal("100.00")
        assert extractor._parse_amount("2,976.00") == Decimal("2976.00")
        assert extractor._parse_amount("") is None
        assert extractor._parse_amount(None) is None

    def test_service_interest_extraction(self, extractor: EmailExtractor) -> None:
        """Test service interest extraction."""
        assert (
            extractor._extract_service_interest("CRM Request", "We need a CRM system")
            == "CRM System"
        )

        assert (
            extractor._extract_service_interest("Website", "Θέλουμε ιστοσελίδα")
            == "Web Development"
        )

        assert extractor._extract_service_interest("General", "Some random text") is None

    def test_validate_valid_email(self, extractor: EmailExtractor) -> None:
        """Test validation of valid email data."""
        from app.models.schemas import EmailData

        data = EmailData(
            email_type=EmailType.CLIENT_INQUIRY,
            sender_email="test@example.gr",
            recipient_email="info@ellincrm.gr",
            subject="Test Subject",
            date_sent=datetime.now(UTC).replace(tzinfo=None),
            body="Test body",
            company="Test Company",
        )

        is_valid, messages = extractor.validate(data)

        assert is_valid
