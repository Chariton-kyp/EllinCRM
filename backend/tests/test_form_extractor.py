"""
Unit tests for FormExtractor.
"""

from datetime import datetime
from pathlib import Path
from tempfile import NamedTemporaryFile

import pytest

from app.extractors.form_extractor import FormExtractor
from app.models.schemas import Priority, RecordType


class TestFormExtractor:
    """Tests for the FormExtractor class."""

    @pytest.fixture
    def extractor(self) -> FormExtractor:
        """Create a FormExtractor instance."""
        return FormExtractor()

    def test_extract_from_sample_html(
        self, extractor: FormExtractor, sample_form_html: str
    ) -> None:
        """Test extraction from sample HTML content."""
        with NamedTemporaryFile(mode="w", suffix=".html", delete=False, encoding="utf-8") as f:
            f.write(sample_form_html)
            f.flush()
            file_path = Path(f.name)

        try:
            result = extractor.extract(file_path)

            assert result.record_type == RecordType.FORM
            assert not result.has_errors
            assert result.form_data is not None

            data = result.form_data
            assert data.full_name == "Τεστ Χρήστης"
            assert data.email == "test@example.gr"
            assert data.phone == "210-1234567"
            assert data.company == "Test Company"
            assert data.priority == Priority.HIGH
            assert result.confidence_score >= 0.8
        finally:
            file_path.unlink()

    def test_extract_from_real_form(
        self, extractor: FormExtractor, forms_path: Path
    ) -> None:
        """Test extraction from actual dummy data form."""
        form_file = forms_path / "contact_form_1.html"
        if not form_file.exists():
            pytest.skip("Dummy data not available")

        result = extractor.extract(form_file)

        assert result.record_type == RecordType.FORM
        assert not result.has_errors
        assert result.form_data is not None

        data = result.form_data
        assert data.full_name == "Νίκος Παπαδόπουλος"
        assert data.email == "nikos.papadopoulos@example.gr"
        assert data.phone == "210-1234567"
        assert data.company == "Digital Marketing Pro"

    def test_extract_all_forms(
        self, extractor: FormExtractor, forms_path: Path
    ) -> None:
        """Test extraction from all dummy data forms."""
        form_files = list(forms_path.glob("*.html"))
        if not form_files:
            pytest.skip("No form files found")

        for form_file in form_files:
            result = extractor.extract(form_file)

            assert not result.has_errors, f"Errors in {form_file.name}: {result.errors}"
            assert result.form_data is not None, f"No data extracted from {form_file.name}"
            assert result.confidence_score >= 0.5, f"Low confidence for {form_file.name}"

    def test_missing_file(self, extractor: FormExtractor) -> None:
        """Test extraction from non-existent file."""
        result = extractor.extract(Path("/nonexistent/file.html"))

        assert result.has_errors
        assert "not found" in result.errors[0].lower()
        assert result.confidence_score == 0.0

    def test_validate_valid_data(self, extractor: FormExtractor) -> None:
        """Test validation of valid form data."""
        from app.models.schemas import ContactFormData

        data = ContactFormData(
            full_name="Test User",
            email="test@example.gr",
            phone="210-1234567",
            company="Test Company",
        )

        is_valid, messages = extractor.validate(data)

        assert is_valid
        assert len(messages) == 0

    def test_validate_invalid_email(self, extractor: FormExtractor) -> None:
        """Test that Pydantic validates email format at model creation."""
        from pydantic import ValidationError

        from app.models.schemas import ContactFormData

        # Pydantic's EmailStr validates email at model creation
        with pytest.raises(ValidationError) as exc_info:
            ContactFormData(
                full_name="Test User",
                email="invalid@nodomain",  # Missing TLD
            )

        # Verify it's an email validation error
        assert "email" in str(exc_info.value).lower()

    def test_priority_mapping(self, extractor: FormExtractor) -> None:
        """Test priority mapping for Greek values."""
        assert extractor._parse_priority("υψηλή") == Priority.HIGH
        assert extractor._parse_priority("Υψηλή") == Priority.HIGH
        assert extractor._parse_priority("μεσαία") == Priority.MEDIUM
        assert extractor._parse_priority("χαμηλή") == Priority.LOW
        assert extractor._parse_priority("high") == Priority.HIGH
        assert extractor._parse_priority("unknown") is None

    def test_date_parsing(self, extractor: FormExtractor) -> None:
        """Test date parsing for various formats."""
        # HTML5 datetime-local format
        result = extractor._parse_date("2024-01-15T14:30")
        assert result is not None
        assert result.year == 2024
        assert result.month == 1
        assert result.day == 15

        # Greek date format
        result = extractor._parse_date("15/01/2024")
        assert result is not None
        assert result.day == 15

        # Invalid format
        result = extractor._parse_date("invalid")
        assert result is None
