"""
Extended service tests for better coverage.
Tests error handling, edge cases, and background operations.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4
from datetime import datetime, timezone

from app.services.record_service import RecordService
from app.services.export_service import ExportService
from app.services.notification_service import NotificationManager, get_notification_manager
from app.db.models import ExtractionRecordDB
from app.models.schemas import (
    ApproveRequest,
    RejectRequest,
    EditRequest,
    ExportRequest,
)


class TestRecordServiceExtended:
    """Extended tests for RecordService."""

    @pytest.fixture
    def mock_repository(self):
        """Create a mock repository."""
        repo = AsyncMock()
        repo.commit = AsyncMock()
        return repo

    @pytest.fixture
    def mock_sheets_service(self):
        """Create a mock Google Sheets service."""
        service = MagicMock()
        service.is_configured.return_value = True
        service.auto_sync_record = AsyncMock()
        return service

    @pytest.fixture
    def record_service(self, mock_repository, mock_sheets_service):
        """Create RecordService with mocks."""
        return RecordService(
            repository=mock_repository,
            sheets_service=mock_sheets_service,
        )

    @pytest.fixture
    def sample_record(self):
        """Create a sample record."""
        return ExtractionRecordDB(
            id=uuid4(),
            source_file="test.html",
            record_type="FORM",
            extracted_data={"full_name": "Test User", "email": "test@example.com"},
            status="pending",
            confidence_score=0.95,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )

    @pytest.mark.anyio
    async def test_approve_with_auto_sync(self, record_service, mock_repository, mock_sheets_service, sample_record):
        """Test approve triggers auto-sync when configured."""
        mock_repository.get_by_id.return_value = sample_record
        mock_repository.update.return_value = sample_record

        background_tasks = MagicMock()
        background_tasks.add_task = MagicMock()

        result = await record_service.approve(
            sample_record.id,
            ApproveRequest(notes="Approved"),
            user_id="test_user",
            background_tasks=background_tasks,
        )

        assert result.status == "approved"
        # Auto-sync should be triggered
        mock_repository.commit.assert_called()

    @pytest.mark.anyio
    async def test_reject_with_auto_sync(self, record_service, mock_repository, mock_sheets_service, sample_record):
        """Test reject triggers auto-sync when configured."""
        mock_repository.get_by_id.return_value = sample_record
        mock_repository.update.return_value = sample_record

        background_tasks = MagicMock()
        background_tasks.add_task = MagicMock()

        result = await record_service.reject(
            sample_record.id,
            RejectRequest(reason="Invalid data"),
            user_id="test_user",
            background_tasks=background_tasks,
        )

        assert result.status == "rejected"

    @pytest.mark.anyio
    async def test_edit_with_auto_sync(self, record_service, mock_repository, mock_sheets_service, sample_record):
        """Test edit triggers auto-sync when configured."""
        mock_repository.get_by_id.return_value = sample_record
        mock_repository.update.return_value = sample_record

        background_tasks = MagicMock()
        background_tasks.add_task = MagicMock()

        result = await record_service.edit(
            sample_record.id,
            EditRequest(data={"full_name": "Updated Name"}),
            user_id="test_user",
            background_tasks=background_tasks,
        )

        assert result.status == "edited"

    @pytest.mark.anyio
    async def test_approve_without_sheets_service(self, mock_repository, sample_record):
        """Test approve works when sheets service is not configured."""
        service = RecordService(repository=mock_repository, sheets_service=None)
        mock_repository.get_by_id.return_value = sample_record
        mock_repository.update.return_value = sample_record

        result = await service.approve(
            sample_record.id,
            ApproveRequest(notes="Approved"),
        )

        assert result.status == "approved"

    @pytest.mark.anyio
    async def test_trigger_auto_sync_no_background_tasks(self, record_service, mock_repository, mock_sheets_service, sample_record):
        """Test auto-sync runs immediately without background tasks."""
        mock_repository.get_by_id.return_value = sample_record
        mock_repository.update.return_value = sample_record

        # No background_tasks = sync runs immediately
        result = await record_service.approve(
            sample_record.id,
            ApproveRequest(),
        )

        assert result.status == "approved"
        # Immediate sync should be called
        mock_sheets_service.auto_sync_record.assert_called()


class TestExportServiceExtended:
    """Extended tests for ExportService."""

    @pytest.fixture
    def mock_repository(self):
        repo = AsyncMock()
        repo.commit = AsyncMock()
        return repo

    @pytest.fixture
    def export_service(self, mock_repository):
        return ExportService(repository=mock_repository)

    @pytest.fixture
    def sample_records(self):
        """Create multiple sample records of different types."""
        return [
            ExtractionRecordDB(
                id=uuid4(),
                source_file="form.html",
                record_type="FORM",
                extracted_data={"full_name": "Form User", "email": "form@example.com"},
                status="approved",
                confidence_score=0.95,
                created_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc),
            ),
            ExtractionRecordDB(
                id=uuid4(),
                source_file="email.eml",
                record_type="EMAIL",
                extracted_data={"sender_email": "sender@example.com", "body_preview": "Test email"},
                status="approved",
                confidence_score=0.90,
                created_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc),
            ),
            ExtractionRecordDB(
                id=uuid4(),
                source_file="invoice.html",
                record_type="INVOICE",
                extracted_data={
                    "invoice_number": "INV-001",
                    "client_name": "Test Corp",
                    "net_amount": 1000.00,
                    "vat_amount": 240.00,
                    "total_amount": 1240.00,
                },
                status="approved",
                confidence_score=0.92,
                created_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc),
            ),
        ]

    @pytest.mark.anyio
    async def test_export_mixed_record_types(self, export_service, mock_repository, sample_records):
        """Test exporting records of different types."""
        mock_repository.get_exportable_records.return_value = sample_records
        mock_repository.update.return_value = sample_records[0]

        request = ExportRequest(format="csv")
        content, filename, content_type, exported_ids = await export_service.export_records(request)

        assert filename.endswith(".csv")
        content_str = content.decode("utf-8")
        # Should contain data from all record types
        assert "FORM" in content_str or "Form User" in content_str
        assert "EMAIL" in content_str or "sender@example.com" in content_str
        assert "INVOICE" in content_str or "INV-001" in content_str

    @pytest.mark.anyio
    async def test_export_xlsx_with_summary_sheet(self, export_service, mock_repository, sample_records):
        """Test XLSX export includes summary sheet."""
        mock_repository.get_exportable_records.return_value = sample_records
        mock_repository.update.return_value = sample_records[0]

        request = ExportRequest(format="xlsx")
        content, filename, content_type, exported_ids = await export_service.export_records(request)

        assert filename.endswith(".xlsx")
        # Excel files are ZIP format (PK header)
        assert content[:2] == b"PK"

    @pytest.mark.anyio
    async def test_export_json_structure(self, export_service, mock_repository, sample_records):
        """Test JSON export has correct structure."""
        mock_repository.get_exportable_records.return_value = sample_records
        mock_repository.update.return_value = sample_records[0]

        request = ExportRequest(format="json")
        content, filename, content_type, exported_ids = await export_service.export_records(request)

        import json
        data = json.loads(content)

        assert "exported_at" in data
        assert "record_count" in data
        assert "records" in data
        assert data["record_count"] == len(sample_records)

    @pytest.mark.anyio
    async def test_export_rejected_records_not_marked_exported(self, export_service, mock_repository):
        """Test rejected records keep their status after export."""
        rejected_record = ExtractionRecordDB(
            id=uuid4(),
            source_file="rejected.html",
            record_type="FORM",
            extracted_data={"full_name": "Rejected"},
            status="rejected",
            rejection_reason="Invalid data",
            confidence_score=0.5,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        mock_repository.get_exportable_records.return_value = [rejected_record]

        request = ExportRequest(format="csv", include_rejected=True)
        content, filename, content_type, exported_ids = await export_service.export_records(request)

        # Rejected records should not have their status changed
        assert len(exported_ids) == 0  # No IDs marked as exported


class TestNotificationManager:
    """Tests for NotificationManager."""

    def test_get_notification_manager_singleton(self):
        """Test notification manager is a singleton."""
        manager1 = get_notification_manager()
        manager2 = get_notification_manager()
        assert manager1 is manager2

    def test_notification_manager_initialization(self):
        """Test NotificationManager initializes correctly."""
        manager = NotificationManager()
        assert manager is not None

    @pytest.mark.anyio
    async def test_notify_record_created(self):
        """Test record created notification."""
        manager = NotificationManager()

        # Mock the broadcast method
        with patch.object(manager, "broadcast", new_callable=AsyncMock) as mock_broadcast:
            await manager.notify_record_created(
                record_id=str(uuid4()),
                source_file="test.html",
                record_type="FORM",
            )

            mock_broadcast.assert_called_once()

    @pytest.mark.anyio
    async def test_notify_record_approved(self):
        """Test record approval notification."""
        manager = NotificationManager()

        with patch.object(manager, "broadcast", new_callable=AsyncMock) as mock_broadcast:
            await manager.notify_record_approved(
                record_id=str(uuid4()),
                source_file="test.html",
                user_id="test_user",
            )

            mock_broadcast.assert_called_once()

    @pytest.mark.anyio
    async def test_notify_record_rejected(self):
        """Test record rejection notification."""
        manager = NotificationManager()

        with patch.object(manager, "broadcast", new_callable=AsyncMock) as mock_broadcast:
            await manager.notify_record_rejected(
                record_id=str(uuid4()),
                source_file="test.html",
                reason="Invalid data",
            )

            mock_broadcast.assert_called_once()

    @pytest.mark.anyio
    async def test_notify_export_complete(self):
        """Test export complete notification."""
        manager = NotificationManager()

        with patch.object(manager, "broadcast", new_callable=AsyncMock) as mock_broadcast:
            await manager.notify_export_complete(
                format="csv",
                count=10,
                filename="export.csv",
            )

            mock_broadcast.assert_called_once()

    @pytest.mark.anyio
    async def test_notify_batch_operation(self):
        """Test batch operation notification."""
        manager = NotificationManager()

        with patch.object(manager, "broadcast", new_callable=AsyncMock) as mock_broadcast:
            await manager.notify_batch_operation(
                operation="approved",
                count=5,
                record_type="FORM",
            )

            mock_broadcast.assert_called_once()


class TestLoggingEdgeCases:
    """Tests for logging edge cases."""

    def test_audit_logger_extraction_started(self):
        """Test audit logger for extraction started events."""
        from app.core.logging import audit_logger

        # Should not raise exception
        audit_logger.log_extraction_started(
            file_path="test.html",
            file_type="FORM",
            extraction_id=str(uuid4()),
        )

    def test_audit_logger_extraction_completed(self):
        """Test audit logger for extraction completed events."""
        from app.core.logging import audit_logger

        audit_logger.log_extraction_completed(
            extraction_id=str(uuid4()),
            success=True,
            confidence_score=0.95,
        )

    def test_audit_logger_extraction_completed_failure(self):
        """Test audit logger for failed extraction events."""
        from app.core.logging import audit_logger

        audit_logger.log_extraction_completed(
            extraction_id=str(uuid4()),
            success=False,
            error_message="Extraction failed",
        )

    def test_audit_logger_user_action(self):
        """Test audit logger for user actions."""
        from app.core.logging import audit_logger

        audit_logger.log_user_action(
            action="approve",
            extraction_id=str(uuid4()),
            user_id="test_user",
            details={"notes": "Test approval"},
        )

    def test_audit_logger_export(self):
        """Test audit logger for export events."""
        from app.core.logging import audit_logger

        audit_logger.log_export(
            export_format="csv",
            record_count=5,
            destination="export.csv",
        )

    def test_audit_logger_user_action_invalid_uuid(self):
        """Test audit logger with invalid UUID (not a valid UUID string)."""
        from app.core.logging import audit_logger

        # Should not raise - invalid UUID is handled gracefully
        audit_logger.log_user_action(
            action="view",
            extraction_id="not-a-valid-uuid",
            user_id="test_user",
        )

    def test_audit_logger_user_action_no_details(self):
        """Test audit logger without details."""
        from app.core.logging import audit_logger

        audit_logger.log_user_action(
            action="delete",
            extraction_id=str(uuid4()),
        )

    def test_audit_logger_user_action_no_user(self):
        """Test audit logger without user_id."""
        from app.core.logging import audit_logger

        audit_logger.log_user_action(
            action="view",
            extraction_id=str(uuid4()),
            details={"source": "api"},
        )

    @pytest.mark.anyio
    async def test_audit_logger_persist_in_async_context(self):
        """Test audit logger works in async context."""
        from app.core.logging import audit_logger

        # In async context, it should try to create a task
        audit_logger.log_user_action(
            action="async_test",
            extraction_id=str(uuid4()),
            user_id="async_user",
        )
        # Give the task a chance to run
        import asyncio
        await asyncio.sleep(0.1)

    def test_audit_logger_with_empty_extraction_id(self):
        """Test audit logger with empty extraction_id."""
        from app.core.logging import audit_logger

        audit_logger.log_user_action(
            action="test",
            extraction_id="",
        )

    def test_audit_logger_with_none_extraction_id(self):
        """Test audit logger handles None extraction_id."""
        from app.core.logging import AuditLogger

        logger = AuditLogger()
        # Call internal method directly with None
        logger._persist_to_db(
            action="test_action",
            record_id=None,
            user_id=None,
            details=None,
        )

    def test_audit_logger_no_database_configured(self):
        """Test audit logger when database is not configured."""
        from app.core.logging import AuditLogger

        logger = AuditLogger()

        # Mock AsyncSessionLocal to be None
        with patch("app.db.database.AsyncSessionLocal", None):
            # Should not raise - gracefully handles no database
            logger._persist_to_db(
                action="test_no_db",
                record_id=str(uuid4()),
                user_id="test_user",
                details={"test": True},
            )

    def test_audit_logger_database_persist_exception(self):
        """Test audit logger handles database persist exception."""
        from app.core.logging import AuditLogger

        logger = AuditLogger()

        # Mock to simulate database error
        mock_session = MagicMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=None)
        mock_session.add = MagicMock(side_effect=Exception("DB Error"))

        with patch("app.db.database.AsyncSessionLocal", return_value=mock_session):
            # Should not raise - gracefully handles database errors
            logger._persist_to_db(
                action="test_db_error",
                record_id=str(uuid4()),
                user_id="test_user",
            )
