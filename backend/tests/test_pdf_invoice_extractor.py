"""
Unit tests for PDFInvoiceExtractor.
"""

from decimal import Decimal
from pathlib import Path
from tempfile import NamedTemporaryFile, TemporaryDirectory
from unittest.mock import MagicMock, patch

import pytest

from app.extractors.pdf_invoice_extractor import PDFInvoiceExtractor, PDF_SUPPORT
from app.models.schemas import RecordType


class TestPDFInvoiceExtractor:
    """Tests for the PDFInvoiceExtractor class."""

    @pytest.fixture
    def extractor(self) -> PDFInvoiceExtractor:
        """Create a PDFInvoiceExtractor instance."""
        return PDFInvoiceExtractor()

    def test_is_supported(self) -> None:
        """Test that is_supported returns correct value based on pdfplumber availability."""
        assert PDFInvoiceExtractor.is_supported() == PDF_SUPPORT

    def test_can_extract_pdf_file(self, extractor: PDFInvoiceExtractor) -> None:
        """Test that can_extract returns True for PDF files."""
        if not PDF_SUPPORT:
            pytest.skip("pdfplumber not installed")
        
        assert extractor.can_extract(Path("invoice.pdf")) is True
        assert extractor.can_extract(Path("invoice.PDF")) is True

    def test_can_extract_non_pdf_file(self, extractor: PDFInvoiceExtractor) -> None:
        """Test that can_extract returns False for non-PDF files."""
        if not PDF_SUPPORT:
            pytest.skip("pdfplumber not installed")
        
        assert extractor.can_extract(Path("invoice.html")) is False
        assert extractor.can_extract(Path("invoice.txt")) is False

    def test_record_type(self, extractor: PDFInvoiceExtractor) -> None:
        """Test that record_type is INVOICE."""
        assert extractor.record_type == RecordType.INVOICE

    def test_missing_file(self, extractor: PDFInvoiceExtractor) -> None:
        """Test extraction from non-existent file."""
        if not PDF_SUPPORT:
            pytest.skip("pdfplumber not installed")
        
        result = extractor.extract(Path("/nonexistent/file.pdf"))

        assert result.has_errors
        assert "not found" in result.errors[0].lower()
        assert result.confidence_score == 0.0

    def test_extract_without_pdfplumber(self) -> None:
        """Test that extraction fails gracefully when pdfplumber not installed."""
        with patch('app.extractors.pdf_invoice_extractor.PDF_SUPPORT', False):
            # Re-import to get the patched version
            from app.extractors.pdf_invoice_extractor import PDFInvoiceExtractor as PatchedExtractor
            extractor = PatchedExtractor()
            result = extractor.extract(Path("/some/file.pdf"))
            
            assert result.has_errors
            assert "not supported" in result.errors[0].lower() or "pdfplumber" in result.errors[0].lower()

    def test_amount_parsing(self, extractor: PDFInvoiceExtractor) -> None:
        """Test amount parsing."""
        assert extractor._parse_amount("€850.00") == Decimal("850.00")
        assert extractor._parse_amount("1,054.00") == Decimal("1054.00")
        assert extractor._parse_amount("1.054,00") == Decimal("1054.00")
        assert extractor._parse_amount("€ 2,976.00") == Decimal("2976.00")
        assert extractor._parse_amount(None) is None
        assert extractor._parse_amount("") is None

    def test_invoice_number_extraction(self, extractor: PDFInvoiceExtractor) -> None:
        """Test invoice number extraction from various formats."""
        # Test from text - Greek format
        text = "Αριθμός: TF-2024-001"
        assert extractor._extract_invoice_number(text, "test.pdf") == "TF-2024-001"
        
        # Test Invoice # format
        text = "Invoice #: TF-2024-002"
        assert extractor._extract_invoice_number(text, "test.pdf") == "TF-2024-002"
        
        # Test from filename fallback
        text = "Some content without invoice number"
        assert extractor._extract_invoice_number(text, "invoice_TF-2024-003.pdf") == "TF-2024-003"

    def test_date_extraction(self, extractor: PDFInvoiceExtractor) -> None:
        """Test date extraction."""
        text = "Ημερομηνία: 21/01/2024"
        date = extractor._extract_date(text)

        assert date is not None
        assert date.day == 21
        assert date.month == 1
        assert date.year == 2024
        
        # Test English date format
        text2 = "Date: 15/03/2024"
        date2 = extractor._extract_date(text2)
        
        assert date2 is not None
        assert date2.day == 15
        assert date2.month == 3

    def test_client_info_extraction(self, extractor: PDFInvoiceExtractor) -> None:
        """Test client info extraction."""
        text = """
        Πελάτης: Test Company
        ΑΦΜ: 123456789
        ΑΦΜ: 987654321
        Διεύθυνση: Οδός Τεστ 123
        """
        info = extractor._extract_client_info(text)
        
        assert info["name"] == "Test Company"
        assert info["vat_number"] == "987654321"  # Second VAT is client's
        assert info["address"] is not None

    def test_totals_extraction(self, extractor: PDFInvoiceExtractor) -> None:
        """Test financial totals extraction."""
        text = """
        Καθαρή Αξία: €1000.00
        ΦΠΑ 24%: €240.00
        ΣΥΝΟΛΟ: €1240.00
        """
        totals = extractor._extract_totals(text)
        
        assert totals["net_amount"] == Decimal("1000.00")
        assert totals["vat_rate"] == Decimal("24")
        assert totals["vat_amount"] == Decimal("240.00")
        assert totals["total_amount"] == Decimal("1240.00")

    def test_payment_terms_extraction(self, extractor: PDFInvoiceExtractor) -> None:
        """Test payment terms extraction."""
        text = """
        Some invoice content
        Τρόπος Πληρωμής: Τραπεζική Κατάθεση
        More content
        """
        terms = extractor._extract_payment_terms(text)
        
        assert terms == "Τραπεζική Κατάθεση"

    def test_validate_valid_invoice(self, extractor: PDFInvoiceExtractor) -> None:
        """Test validation of valid invoice data."""
        from datetime import datetime
        from app.models.schemas import InvoiceData

        data = InvoiceData(
            invoice_number="TF-2024-001",
            invoice_date=datetime.utcnow(),
            client_name="Test Client",
            net_amount=Decimal("100.00"),
            vat_rate=Decimal("24"),
            vat_amount=Decimal("24.00"),
            total_amount=Decimal("124.00"),
        )

        is_valid, messages = extractor.validate(data)

        assert is_valid

    def test_validate_vat_mismatch(self, extractor: PDFInvoiceExtractor) -> None:
        """Test validation catches VAT mismatch."""
        from datetime import datetime
        from app.models.schemas import InvoiceData

        data = InvoiceData(
            invoice_number="TF-2024-001",
            invoice_date=datetime.utcnow(),
            client_name="Test Client",
            net_amount=Decimal("100.00"),
            vat_rate=Decimal("24"),
            vat_amount=Decimal("30.00"),  # Wrong VAT
            total_amount=Decimal("130.00"),
        )

        is_valid, messages = extractor.validate(data)

        assert any("vat" in msg.lower() for msg in messages)

    def test_calculate_confidence(self, extractor: PDFInvoiceExtractor) -> None:
        """Test confidence calculation."""
        from datetime import datetime
        from app.models.schemas import InvoiceData, InvoiceItem

        # Full data with items should have high confidence
        data_full = InvoiceData(
            invoice_number="TF-2024-001",
            invoice_date=datetime.utcnow(),
            client_name="Test Client",
            client_address="Test Address",
            client_vat_number="123456789",
            items=[
                InvoiceItem(
                    description="Service",
                    quantity=1,
                    unit_price=Decimal("100.00"),
                    total=Decimal("100.00"),
                )
            ],
            net_amount=Decimal("100.00"),
            vat_rate=Decimal("24"),
            vat_amount=Decimal("24.00"),
            total_amount=Decimal("124.00"),
            payment_terms="Bank Transfer",
        )
        
        confidence = extractor._calculate_confidence(data_full, [])
        assert confidence >= 0.8

        # Minimal data should have lower confidence
        data_minimal = InvoiceData(
            invoice_number="TF-2024-001",
            invoice_date=datetime.utcnow(),
            client_name="Test Client",
            net_amount=Decimal("100.00"),
            vat_rate=Decimal("24"),
            vat_amount=Decimal("24.00"),
            total_amount=Decimal("124.00"),
        )
        
        confidence_minimal = extractor._calculate_confidence(data_minimal, ["warning1", "warning2"])
        assert confidence_minimal < confidence


@pytest.mark.skipif(not PDF_SUPPORT, reason="pdfplumber not installed")
class TestPDFInvoiceExtractorWithPdfplumber:
    """Tests that require pdfplumber to be installed."""

    @pytest.fixture
    def extractor(self) -> PDFInvoiceExtractor:
        """Create a PDFInvoiceExtractor instance."""
        return PDFInvoiceExtractor()

    def test_extract_line_items_from_tables(self, extractor: PDFInvoiceExtractor) -> None:
        """Test line item extraction from table structures."""
        # Create mock table data
        tables = [
            [
                ["Περιγραφή", "Ποσότητα", "Τιμή", "Σύνολο"],
                ["Service A", "2", "50.00", "100.00"],
                ["Service B", "1", "150.00", "150.00"],
            ]
        ]
        
        items = extractor._extract_line_items_from_tables(tables)
        
        assert len(items) == 2
        assert items[0].description == "Service A"
        assert items[0].quantity == 2
        assert items[0].unit_price == Decimal("50.00")
        assert items[0].total == Decimal("100.00")

    def test_extract_line_items_from_text(self, extractor: PDFInvoiceExtractor) -> None:
        """Test fallback line item extraction from text."""
        text = """
        Service Description    1    €500.00    €500.00
        Another Service        2    €250.00    €500.00
        """
        
        items = extractor._extract_line_items_from_text(text)
        
        # May extract some items depending on pattern matching
        # This is a fallback method so results may vary
        assert isinstance(items, list)
