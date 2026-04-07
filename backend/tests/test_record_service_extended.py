"""
Extended tests for RecordService to increase coverage.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4
from datetime import datetime, timezone

from app.services.record_service import RecordService
from app.db.models import ExtractionRecordDB
from app.models.schemas import (
    ApproveRequest,
    RejectRequest,
    EditRequest,
    ExtractionResult,
    ContactFormData,
    RecordType,
)


@pytest.fixture
def mock_repository():
    """Create a mock repository."""
    repo = AsyncMock()
    repo.session = AsyncMock()
    return repo


@pytest.fixture
def record_service(mock_repository):
    """Create RecordService with mock repository."""
    return RecordService(repository=mock_repository)


@pytest.fixture
def sample_record():
    """Create a sample extraction record."""
    return ExtractionRecordDB(
        id=uuid4(),
        source_file="/app/data/forms/form_1.html",
        record_type="FORM",
        extracted_data={
            "full_name": "Test User",
            "email": "test@example.com",
        },
        confidence_score=0.95,
        warnings=[],
        errors=[],
        status="pending",
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )


class TestRecordServiceSetters:
    """Test service setter methods."""

    def test_set_similarity_service(self, record_service):
        """Test setting similarity service."""
        mock_similarity = MagicMock()
        record_service.set_similarity_service(mock_similarity)
        assert record_service.similarity_service is mock_similarity

    def test_set_sheets_service(self, record_service):
        """Test setting sheets service."""
        mock_sheets = MagicMock()
        record_service.set_sheets_service(mock_sheets)
        assert record_service.sheets_service is mock_sheets

    def test_similarity_service_property(self, record_service):
        """Test similarity service property returns None by default."""
        assert record_service.similarity_service is None

    def test_sheets_service_property(self, record_service):
        """Test sheets service property returns None by default."""
        assert record_service.sheets_service is None


class TestApproveWithNotifications:
    """Test approve with notification handling."""

    @pytest.mark.anyio
    async def test_approve_with_notify_false(
        self, record_service, mock_repository, sample_record
    ):
        """Test approve without sending notification."""
        mock_repository.get_by_id.return_value = sample_record
        mock_repository.update.return_value = sample_record

        with patch("app.services.record_service.get_notification_manager") as mock_nm:
            mock_manager = AsyncMock()
            mock_nm.return_value = mock_manager

            result = await record_service.approve(
                sample_record.id,
                ApproveRequest(),
                notify=False,
            )

            # Notification should not be called
            mock_manager.notify_record_approved.assert_not_called()


class TestRejectWithNotifications:
    """Test reject with notification handling."""

    @pytest.mark.anyio
    async def test_reject_with_notify_false(
        self, record_service, mock_repository, sample_record
    ):
        """Test reject without sending notification."""
        mock_repository.get_by_id.return_value = sample_record
        mock_repository.update.return_value = sample_record

        with patch("app.services.record_service.get_notification_manager") as mock_nm:
            mock_manager = AsyncMock()
            mock_nm.return_value = mock_manager

            result = await record_service.reject(
                sample_record.id,
                RejectRequest(reason="Test"),
                notify=False,
            )

            # Notification should not be called
            mock_manager.notify_record_rejected.assert_not_called()


class TestBatchOperationsExtended:
    """Extended tests for batch operations."""

    @pytest.mark.anyio
    async def test_approve_batch_with_errors(
        self, record_service, mock_repository, sample_record
    ):
        """Test batch approve handling errors."""
        # First call succeeds, second fails
        mock_repository.get_by_id.side_effect = [
            sample_record,
            None,  # This will cause ValueError
        ]
        mock_repository.update.return_value = sample_record

        record_ids = [sample_record.id, uuid4()]

        with patch("app.services.record_service.get_notification_manager") as mock_nm:
            mock_manager = AsyncMock()
            mock_nm.return_value = mock_manager

            result = await record_service.approve_batch(
                record_ids,
                ApproveRequest(),
            )

            assert result["approved_count"] == 1
            assert result["error_count"] == 1

    @pytest.mark.anyio
    async def test_reject_batch_with_errors(
        self, record_service, mock_repository, sample_record
    ):
        """Test batch reject handling errors."""
        mock_repository.get_by_id.side_effect = [
            sample_record,
            None,
        ]
        mock_repository.update.return_value = sample_record

        record_ids = [sample_record.id, uuid4()]

        with patch("app.services.record_service.get_notification_manager") as mock_nm:
            mock_manager = AsyncMock()
            mock_nm.return_value = mock_manager

            result = await record_service.reject_batch(
                record_ids,
                RejectRequest(reason="Batch reject"),
            )

            assert result["rejected_count"] == 1
            assert result["error_count"] == 1


class TestCreateFromExtraction:
    """Tests for create_from_extraction method."""

    @pytest.mark.anyio
    async def test_create_from_extraction_basic(
        self, record_service, mock_repository
    ):
        """Test basic record creation from extraction."""
        form_data = ContactFormData(
            full_name="Test User",
            email="test@example.com",
        )

        extraction = ExtractionResult(
            id=uuid4(),
            source_file="form.html",
            record_type=RecordType.FORM,
            form_data=form_data,
            confidence_score=0.95,
        )

        mock_record = ExtractionRecordDB(
            id=extraction.id,
            source_file="form.html",
            record_type="FORM",
            extracted_data={"full_name": "Test User", "email": "test@example.com"},
            confidence_score=0.95,
            status="pending",
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        mock_repository.create.return_value = mock_record

        with patch("app.services.record_service.get_notification_manager") as mock_nm:
            mock_manager = AsyncMock()
            mock_nm.return_value = mock_manager

            result = await record_service.create_from_extraction(
                extraction,
                generate_embedding=False,
            )

            assert result is not None
            mock_repository.create.assert_called_once()

    @pytest.mark.anyio
    async def test_create_from_extraction_with_embedding(
        self, record_service, mock_repository
    ):
        """Test record creation with embedding generation."""
        form_data = ContactFormData(
            full_name="Test",
            email="test@example.com",
        )

        extraction = ExtractionResult(
            id=uuid4(),
            source_file="form.html",
            record_type=RecordType.FORM,
            form_data=form_data,
            confidence_score=0.95,
        )

        mock_record = ExtractionRecordDB(
            id=extraction.id,
            source_file="form.html",
            record_type="FORM",
            extracted_data={},
            confidence_score=0.95,
            status="pending",
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        mock_repository.create.return_value = mock_record

        # Add mock similarity service
        mock_similarity = AsyncMock()
        record_service.set_similarity_service(mock_similarity)

        with patch("app.services.record_service.get_notification_manager") as mock_nm:
            mock_manager = AsyncMock()
            mock_nm.return_value = mock_manager

            result = await record_service.create_from_extraction(
                extraction,
                generate_embedding=True,
            )

            # Similarity service should be called
            mock_similarity.create_embedding.assert_called_once()

    @pytest.mark.anyio
    async def test_create_from_extraction_embedding_fails(
        self, record_service, mock_repository
    ):
        """Test record creation when embedding fails (should not fail creation)."""
        form_data = ContactFormData(
            full_name="Test",
            email="test@example.com",
        )

        extraction = ExtractionResult(
            id=uuid4(),
            source_file="form.html",
            record_type=RecordType.FORM,
            form_data=form_data,
            confidence_score=0.95,
        )

        mock_record = ExtractionRecordDB(
            id=extraction.id,
            source_file="form.html",
            record_type="FORM",
            extracted_data={},
            confidence_score=0.95,
            status="pending",
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        mock_repository.create.return_value = mock_record

        # Add mock similarity service that fails
        mock_similarity = AsyncMock()
        mock_similarity.create_embedding.side_effect = Exception("Embedding failed")
        record_service.set_similarity_service(mock_similarity)

        with patch("app.services.record_service.get_notification_manager") as mock_nm:
            mock_manager = AsyncMock()
            mock_nm.return_value = mock_manager

            # Should not raise despite embedding failure
            result = await record_service.create_from_extraction(
                extraction,
                generate_embedding=True,
            )

            assert result is not None


class TestTriggerAutoSync:
    """Tests for auto-sync triggering."""

    @pytest.mark.anyio
    async def test_trigger_auto_sync_with_sheets_service(
        self, record_service, mock_repository, sample_record
    ):
        """Test auto-sync triggers when sheets service is configured."""
        mock_sheets = AsyncMock()
        record_service.set_sheets_service(mock_sheets)

        await record_service._trigger_auto_sync(sample_record, "approved")

        mock_sheets.auto_sync_record.assert_called_once_with(sample_record, "approved")

    @pytest.mark.anyio
    async def test_trigger_auto_sync_without_sheets_service(
        self, record_service, mock_repository, sample_record
    ):
        """Test auto-sync does nothing when no sheets service."""
        # No sheets service set
        await record_service._trigger_auto_sync(sample_record, "approved")
        # Should complete without error

    @pytest.mark.anyio
    async def test_trigger_auto_sync_handles_error(
        self, record_service, mock_repository, sample_record
    ):
        """Test auto-sync handles errors gracefully."""
        mock_sheets = AsyncMock()
        mock_sheets.auto_sync_record.side_effect = Exception("Sync failed")
        record_service.set_sheets_service(mock_sheets)

        # Should not raise
        await record_service._trigger_auto_sync(sample_record, "approved")


class TestGetStats:
    """Tests for get_stats method."""

    @pytest.mark.anyio
    async def test_get_stats_empty(self, record_service, mock_repository):
        """Test stats with no records."""
        mock_repository.get_stats.return_value = {
            "by_status": {},
            "by_type": {},
        }

        stats = await record_service.get_stats()

        assert stats["total"] == 0
        assert stats["pending_count"] == 0
        assert stats["approved_count"] == 0

    @pytest.mark.anyio
    async def test_get_stats_with_exported(self, record_service, mock_repository):
        """Test stats includes exported count."""
        mock_repository.get_stats.return_value = {
            "by_status": {"pending": 5, "approved": 3, "exported": 10},
            "by_type": {"FORM": 10, "EMAIL": 8},
        }

        stats = await record_service.get_stats()

        assert stats["exported_count"] == 10
        assert stats["total"] == 18
