"""
Unit tests for InvoiceExtractor.
"""

from decimal import Decimal
from pathlib import Path
from tempfile import NamedTemporaryFile

import pytest

from app.extractors.invoice_extractor import InvoiceExtractor
from app.models.schemas import RecordType


class TestInvoiceExtractor:
    """Tests for the InvoiceExtractor class."""

    @pytest.fixture
    def extractor(self) -> InvoiceExtractor:
        """Create an InvoiceExtractor instance."""
        return InvoiceExtractor()

    def test_extract_from_sample_html(
        self, extractor: InvoiceExtractor, sample_invoice_html: str
    ) -> None:
        """Test extraction from sample HTML content."""
        with NamedTemporaryFile(mode="w", suffix=".html", delete=False, encoding="utf-8") as f:
            f.write(sample_invoice_html)
            f.flush()
            file_path = Path(f.name)

        try:
            result = extractor.extract(file_path)

            assert result.record_type == RecordType.INVOICE
            assert not result.has_errors, f"Errors: {result.errors}"
            assert result.invoice_data is not None

            data = result.invoice_data
            assert data.invoice_number == "TF-2024-999"
            assert data.net_amount == Decimal("100.00")
            assert data.vat_amount == Decimal("24.00")
            assert data.total_amount == Decimal("124.00")
            assert result.confidence_score >= 0.7
        finally:
            file_path.unlink()

    def test_extract_from_real_invoice(
        self, extractor: InvoiceExtractor, invoices_path: Path
    ) -> None:
        """Test extraction from actual dummy data invoice."""
        invoice_file = invoices_path / "invoice_TF-2024-001.html"
        if not invoice_file.exists():
            pytest.skip("Dummy data not available")

        result = extractor.extract(invoice_file)

        assert result.record_type == RecordType.INVOICE
        assert not result.has_errors, f"Errors: {result.errors}"
        assert result.invoice_data is not None

        data = result.invoice_data
        assert data.invoice_number == "TF-2024-001"
        assert data.client_name == "Office Solutions Ltd"
        assert data.net_amount == Decimal("850.00")
        assert data.vat_rate == Decimal("24")
        assert data.vat_amount == Decimal("204.00")
        assert data.total_amount == Decimal("1054.00")

    def test_extract_all_invoices(
        self, extractor: InvoiceExtractor, invoices_path: Path
    ) -> None:
        """Test extraction from all dummy data invoices."""
        invoice_files = list(invoices_path.glob("*.html"))
        if not invoice_files:
            pytest.skip("No invoice files found")

        for invoice_file in invoice_files:
            result = extractor.extract(invoice_file)

            assert not result.has_errors, f"Errors in {invoice_file.name}: {result.errors}"
            assert result.invoice_data is not None, f"No data from {invoice_file.name}"
            assert result.confidence_score >= 0.5, f"Low confidence for {invoice_file.name}"

            # Verify VAT calculation (24%)
            data = result.invoice_data
            expected_vat = data.net_amount * Decimal("24") / Decimal("100")
            assert abs(data.vat_amount - expected_vat) < Decimal("1"), \
                f"VAT mismatch in {invoice_file.name}"

    def test_missing_file(self, extractor: InvoiceExtractor) -> None:
        """Test extraction from non-existent file."""
        result = extractor.extract(Path("/nonexistent/file.html"))

        assert result.has_errors
        assert "not found" in result.errors[0].lower()
        assert result.confidence_score == 0.0

    def test_invoice_number_extraction(self, extractor: InvoiceExtractor) -> None:
        """Test invoice number extraction from various formats."""
        from bs4 import BeautifulSoup

        # Test from text
        html = "<html><body>Αριθμός: TF-2024-001</body></html>"
        soup = BeautifulSoup(html, "html.parser")
        assert extractor._extract_invoice_number(soup, "test.html") == "TF-2024-001"

        # Test from filename
        html = "<html><body>Some content</body></html>"
        soup = BeautifulSoup(html, "html.parser")
        assert extractor._extract_invoice_number(
            soup, "invoice_TF-2024-002.html"
        ) == "TF-2024-002"

    def test_date_extraction(self, extractor: InvoiceExtractor) -> None:
        """Test date extraction."""
        from bs4 import BeautifulSoup

        html = "<html><body>Ημερομηνία: 21/01/2024</body></html>"
        soup = BeautifulSoup(html, "html.parser")
        date = extractor._extract_date(soup)

        assert date is not None
        assert date.day == 21
        assert date.month == 1
        assert date.year == 2024

    def test_amount_parsing(self, extractor: InvoiceExtractor) -> None:
        """Test amount parsing."""
        assert extractor._parse_amount("€850.00") == Decimal("850.00")
        assert extractor._parse_amount("1,054.00") == Decimal("1054.00")
        assert extractor._parse_amount("1.054,00") == Decimal("1054.00")
        assert extractor._parse_amount("€ 2,976.00") == Decimal("2976.00")
        assert extractor._parse_amount(None) is None
        assert extractor._parse_amount("") is None

    def test_line_items_extraction(self, extractor: InvoiceExtractor) -> None:
        """Test line items extraction from table."""
        from bs4 import BeautifulSoup

        html = '''
        <table class="invoice-table">
            <thead><tr><th>Περιγραφή</th><th>Qty</th><th>Price</th><th>Total</th></tr></thead>
            <tbody>
                <tr><td>Item A</td><td>5</td><td>€10.00</td><td>€50.00</td></tr>
                <tr><td>Item B</td><td>3</td><td>€20.00</td><td>€60.00</td></tr>
            </tbody>
        </table>
        '''
        soup = BeautifulSoup(html, "html.parser")
        items = extractor._extract_line_items(soup)

        assert len(items) == 2
        assert items[0].description == "Item A"
        assert items[0].quantity == 5
        assert items[0].unit_price == Decimal("10.00")
        assert items[0].total == Decimal("50.00")

    def test_validate_valid_invoice(self, extractor: InvoiceExtractor) -> None:
        """Test validation of valid invoice data."""
        from app.models.schemas import InvoiceData

        data = InvoiceData(
            invoice_number="TF-2024-001",
            invoice_date=extractor._extract_date.__func__.__globals__["datetime"].utcnow(),
            client_name="Test Client",
            net_amount=Decimal("100.00"),
            vat_rate=Decimal("24"),
            vat_amount=Decimal("24.00"),
            total_amount=Decimal("124.00"),
        )

        is_valid, messages = extractor.validate(data)

        assert is_valid

    def test_validate_vat_mismatch(self, extractor: InvoiceExtractor) -> None:
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
