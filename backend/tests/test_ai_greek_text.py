"""
Tests for Greek text processing module.
"""

import pytest

from app.ai.greek_text import (
    GREEK_ACCENT_MAP,
    GREEK_STOPWORDS,
    normalize_greek_text,
    tokenize_for_search,
    extract_search_text,
    create_search_vector_text,
)


class TestNormalizeGreekText:
    """Tests for normalize_greek_text function."""

    def test_normalize_accented_lowercase(self) -> None:
        """Test normalization of accented lowercase Greek."""
        assert normalize_greek_text("άέήίόύώ") == "αεηιουω"

    def test_normalize_accented_uppercase(self) -> None:
        """Test normalization of accented uppercase Greek."""
        assert normalize_greek_text("ΆΈΉΊΌΎΏ") == "αεηιουω"

    def test_normalize_mixed_case(self) -> None:
        """Test normalization of mixed case Greek."""
        result = normalize_greek_text("Δικηγορικό Γραφείο")
        assert result == "δικηγορικο γραφειο"

    def test_normalize_dialytika(self) -> None:
        """Test normalization of Greek dialytika."""
        assert normalize_greek_text("ϊΐϋΰ") == "ιιυυ"

    def test_normalize_empty_string(self) -> None:
        """Test normalization of empty string."""
        assert normalize_greek_text("") == ""

    def test_normalize_none_like(self) -> None:
        """Test normalization of falsy values."""
        assert normalize_greek_text("") == ""

    def test_normalize_english_text(self) -> None:
        """Test that English text is lowercased but otherwise unchanged."""
        assert normalize_greek_text("Hello World") == "hello world"

    def test_normalize_mixed_greek_english(self) -> None:
        """Test normalization of mixed Greek-English text."""
        result = normalize_greek_text("EllinCRM Λύσεις IT")
        assert result == "ellincrm λυσεις it"

    def test_normalize_special_characters(self) -> None:
        """Test that special characters are preserved."""
        result = normalize_greek_text("email@test.gr")
        assert result == "email@test.gr"

    def test_normalize_numbers(self) -> None:
        """Test that numbers are preserved."""
        result = normalize_greek_text("Τιμολόγιο 2024-001")
        assert result == "τιμολογιο 2024-001"


class TestTokenizeForSearch:
    """Tests for tokenize_for_search function."""

    def test_tokenize_basic(self) -> None:
        """Test basic tokenization."""
        result = tokenize_for_search("Δικηγορικό Γραφείο Μάντζιου")
        assert "δικηγορικο" in result
        assert "γραφειο" in result
        assert "μαντζιου" in result

    def test_tokenize_empty_string(self) -> None:
        """Test tokenization of empty string."""
        assert tokenize_for_search("") == []

    def test_tokenize_min_token_length(self) -> None:
        """Test minimum token length filtering."""
        result = tokenize_for_search("Ο Κ Μ test", min_token_length=2)
        # Single letters should be filtered
        assert "ο" not in result
        assert "κ" not in result

    def test_tokenize_with_stopwords_removal(self) -> None:
        """Test stopword removal."""
        result = tokenize_for_search(
            "ο Κώστας και η Μαρία",
            remove_stopwords=True
        )
        # "ο", "και", "η" should be removed
        assert "ο" not in result
        assert "και" not in result
        assert "η" not in result
        # Names should remain
        assert "κωστας" in result
        assert "μαρια" in result

    def test_tokenize_without_stopwords_removal(self) -> None:
        """Test that stopwords are kept when not removing."""
        result = tokenize_for_search(
            "και είναι",
            remove_stopwords=False,
            min_token_length=2
        )
        assert "και" in result
        assert "ειναι" in result

    def test_tokenize_special_characters(self) -> None:
        """Test that special characters split tokens."""
        result = tokenize_for_search("email@test.gr")
        assert "email" in result
        assert "test" in result


class TestExtractSearchText:
    """Tests for extract_search_text function."""

    def test_extract_from_form_data(self) -> None:
        """Test extracting text from form data."""
        record = {
            "form_data": {
                "full_name": "Νίκος Παπαδόπουλος",
                "company": "EllinCRM",
                "email": "nikos@example.gr",
                "message": "Χρειαζόμαστε CRM",
                "service_interest": "CRM System",
            }
        }
        result = extract_search_text(record)
        assert "Νίκος Παπαδόπουλος" in result
        assert "EllinCRM" in result
        assert "nikos@example.gr" in result

    def test_extract_from_email_data(self) -> None:
        """Test extracting text from email data."""
        record = {
            "email_data": {
                "sender_name": "Μαρία Κώστα",
                "sender_email": "maria@test.gr",
                "subject": "Αίτημα για πληροφορίες",
                "body": "Καλησπέρα, θα ήθελα πληροφορίες...",
                "company": "Test Company",
            }
        }
        result = extract_search_text(record)
        assert "Μαρία Κώστα" in result
        assert "maria@test.gr" in result
        assert "Αίτημα για πληροφορίες" in result

    def test_extract_from_invoice_data(self) -> None:
        """Test extracting text from invoice data."""
        record = {
            "invoice_data": {
                "client_name": "Office Solutions Ltd",
                "invoice_number": "TF-2024-001",
                "client_address": "Βας. Σοφίας 45",
                "notes": "Πληρωμή σε 30 ημέρες",
                "items": [
                    {"description": "Χαρτί Α4"},
                    {"description": "Στυλό"},
                ],
            }
        }
        result = extract_search_text(record)
        assert "Office Solutions Ltd" in result
        assert "TF-2024-001" in result
        assert "Χαρτί Α4" in result
        assert "Στυλό" in result

    def test_extract_from_empty_record(self) -> None:
        """Test extracting text from empty record."""
        result = extract_search_text({})
        assert result == ""


class TestCreateSearchVectorText:
    """Tests for create_search_vector_text function."""

    def test_creates_normalized_text(self) -> None:
        """Test that output is normalized."""
        record = {
            "form_data": {
                "full_name": "Νίκος ΠΑΠΑΔΌΠΟΥΛΟΣ",
                "company": "EllinCRM Λύσεις",
            }
        }
        result = create_search_vector_text(record)
        # Should be lowercase and without accents
        assert "νικος" in result
        assert "παπαδοπουλος" in result
        assert "λυσεις" in result

    def test_handles_empty_record(self) -> None:
        """Test handling of empty record."""
        result = create_search_vector_text({})
        assert result == ""


class TestGreekAccentMap:
    """Tests for GREEK_ACCENT_MAP constant."""

    def test_accent_map_coverage(self) -> None:
        """Test that accent map covers common accented characters."""
        # Lowercase accents
        assert "ά" in GREEK_ACCENT_MAP
        assert "έ" in GREEK_ACCENT_MAP
        assert "ή" in GREEK_ACCENT_MAP
        assert "ί" in GREEK_ACCENT_MAP
        assert "ό" in GREEK_ACCENT_MAP
        assert "ύ" in GREEK_ACCENT_MAP
        assert "ώ" in GREEK_ACCENT_MAP

        # Uppercase accents
        assert "Ά" in GREEK_ACCENT_MAP
        assert "Ώ" in GREEK_ACCENT_MAP

    def test_accent_map_values(self) -> None:
        """Test that accent map values are correct."""
        assert GREEK_ACCENT_MAP["ά"] == "α"
        assert GREEK_ACCENT_MAP["Ώ"] == "ω"


class TestGreekStopwords:
    """Tests for GREEK_STOPWORDS constant."""

    def test_contains_articles(self) -> None:
        """Test that stopwords contain Greek articles."""
        assert "ο" in GREEK_STOPWORDS
        assert "η" in GREEK_STOPWORDS
        assert "το" in GREEK_STOPWORDS

    def test_contains_prepositions(self) -> None:
        """Test that stopwords contain Greek prepositions."""
        assert "σε" in GREEK_STOPWORDS
        assert "από" in GREEK_STOPWORDS
        assert "για" in GREEK_STOPWORDS

    def test_contains_english_stopwords(self) -> None:
        """Test that stopwords contain common English words."""
        assert "the" in GREEK_STOPWORDS
        assert "and" in GREEK_STOPWORDS
        assert "is" in GREEK_STOPWORDS
