"""
Tests for search router and models.
"""

import pytest
from pydantic import ValidationError

from app.routers.search import (
    SearchRequest,
    SearchResult,
    SearchResponse,
    EmbeddingStatsResponse,
    GenerateEmbeddingsRequest,
    GenerateEmbeddingsResponse,
    SimilarRecordsResponse,
    _get_highlight,
)


class TestSearchRequest:
    """Tests for SearchRequest model."""

    def test_valid_request(self) -> None:
        """Test creating valid search request."""
        request = SearchRequest(query="test query")
        assert request.query == "test query"
        assert request.limit == 10  # default
        assert request.min_similarity == 0.3  # default
        assert request.search_mode == "hybrid"  # default

    def test_request_with_all_params(self) -> None:
        """Test request with all parameters."""
        request = SearchRequest(
            query="CRM system",
            limit=20,
            min_similarity=0.5,
            record_type="FORM",
            status="pending",
            search_mode="semantic",
        )
        assert request.query == "CRM system"
        assert request.limit == 20
        assert request.min_similarity == 0.5
        assert request.record_type == "FORM"
        assert request.status == "pending"
        assert request.search_mode == "semantic"

    def test_empty_query_fails(self) -> None:
        """Test that empty query fails validation."""
        with pytest.raises(ValidationError):
            SearchRequest(query="")

    def test_query_max_length(self) -> None:
        """Test query max length validation."""
        long_query = "x" * 1001
        with pytest.raises(ValidationError):
            SearchRequest(query=long_query)

    def test_limit_bounds(self) -> None:
        """Test limit boundary validation."""
        # Below minimum
        with pytest.raises(ValidationError):
            SearchRequest(query="test", limit=0)

        # Above maximum
        with pytest.raises(ValidationError):
            SearchRequest(query="test", limit=101)

    def test_similarity_bounds(self) -> None:
        """Test similarity threshold bounds."""
        # Below minimum
        with pytest.raises(ValidationError):
            SearchRequest(query="test", min_similarity=-0.1)

        # Above maximum
        with pytest.raises(ValidationError):
            SearchRequest(query="test", min_similarity=1.1)

    def test_search_mode_validation(self) -> None:
        """Test search mode validation."""
        # Valid modes
        for mode in ["hybrid", "semantic", "keyword"]:
            request = SearchRequest(query="test", search_mode=mode)
            assert request.search_mode == mode

        # Invalid mode
        with pytest.raises(ValidationError):
            SearchRequest(query="test", search_mode="invalid")


class TestSearchResponse:
    """Tests for SearchResponse model."""

    def test_empty_results(self) -> None:
        """Test response with no results."""
        response = SearchResponse(
            query="test",
            results=[],
            total=0,
            model="test-model",
        )
        assert response.total == 0
        assert len(response.results) == 0


class TestEmbeddingStatsResponse:
    """Tests for EmbeddingStatsResponse model."""

    def test_valid_stats(self) -> None:
        """Test valid stats response."""
        stats = EmbeddingStatsResponse(
            total_embeddings=100,
            records_without_embeddings=5,
            embedding_dimension=768,
            model="gemma-embedding",
        )
        assert stats.total_embeddings == 100
        assert stats.records_without_embeddings == 5
        assert stats.embedding_dimension == 768


class TestGenerateEmbeddingsRequest:
    """Tests for GenerateEmbeddingsRequest model."""

    def test_empty_request(self) -> None:
        """Test request without record IDs (generate all missing)."""
        request = GenerateEmbeddingsRequest()
        assert request.record_ids is None

    def test_with_record_ids(self) -> None:
        """Test request with specific record IDs."""
        from uuid import uuid4

        ids = [uuid4(), uuid4()]
        request = GenerateEmbeddingsRequest(record_ids=ids)
        assert len(request.record_ids) == 2


class TestGenerateEmbeddingsResponse:
    """Tests for GenerateEmbeddingsResponse model."""

    def test_valid_response(self) -> None:
        """Test valid response."""
        response = GenerateEmbeddingsResponse(
            generated=10,
            message="Successfully generated 10 embeddings",
        )
        assert response.generated == 10
        assert "10" in response.message


class TestSimilarRecordsResponse:
    """Tests for SimilarRecordsResponse model."""

    def test_valid_response(self) -> None:
        """Test valid similar records response."""
        response = SimilarRecordsResponse(
            record_id="test-uuid",
            similar=[],
            total=0,
        )
        assert response.record_id == "test-uuid"
        assert response.total == 0


class TestGetHighlight:
    """Tests for _get_highlight helper function."""

    def test_highlight_form_record(self) -> None:
        """Test highlight for form record."""

        class MockRecord:
            record_type = "FORM"

            @property
            def final_data(self):
                return {
                    "message": "Χρειαζόμαστε CRM σύστημα",
                    "service_interest": "CRM System",
                }

        record = MockRecord()
        highlight = _get_highlight(record, "CRM")
        assert highlight is not None
        assert "CRM" in highlight

    def test_highlight_email_record(self) -> None:
        """Test highlight for email record."""

        class MockRecord:
            record_type = "EMAIL"

            @property
            def final_data(self):
                return {
                    "subject": "Αίτημα για πληροφορίες",
                    "body": "Καλησπέρα, θα ήθελα πληροφορίες για τις υπηρεσίες σας.",
                }

        record = MockRecord()
        highlight = _get_highlight(record, "πληροφορίες")
        assert highlight is not None

    def test_highlight_invoice_record(self) -> None:
        """Test highlight for invoice record."""

        class MockRecord:
            record_type = "INVOICE"

            @property
            def final_data(self):
                return {
                    "client_name": "Office Solutions Ltd",
                    "notes": "Πληρωμή εντός 30 ημερών",
                }

        record = MockRecord()
        highlight = _get_highlight(record, "Office")
        assert highlight is not None
        assert "Office" in highlight

    def test_highlight_empty_data(self) -> None:
        """Test highlight with empty data."""

        class MockRecord:
            record_type = "FORM"

            @property
            def final_data(self):
                return {}

        record = MockRecord()
        highlight = _get_highlight(record, "test")
        assert highlight is None

    def test_highlight_truncation(self) -> None:
        """Test that long content is handled properly."""

        class MockRecord:
            record_type = "EMAIL"

            @property
            def final_data(self):
                return {
                    "body": "x" * 300,
                }

        record = MockRecord()
        highlight = _get_highlight(record, "test")
        assert highlight is not None
        # Function slices body to 200 chars, then may add "..." if total > 200
        # So the result should be <= 203 characters
        assert len(highlight) <= 203
