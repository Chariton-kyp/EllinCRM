"""
Tests for service layer (RecordService, ExportService).
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4
from datetime import datetime, timezone

from app.services.record_service import RecordService
from app.services.export_service import ExportService
from app.db.models import ExtractionRecordDB
from app.models.schemas import (
    ApproveRequest,
    RejectRequest,
    EditRequest,
    ExportRequest,
    ExtractionResult,
    RecordType,
)


@pytest.fixture
def mock_repository():
    """Create a mock repository."""
    return AsyncMock()


@pytest.fixture
def record_service(mock_repository):
    """Create RecordService with mock repository."""
    return RecordService(repository=mock_repository)


@pytest.fixture
def export_service(mock_repository):
    """Create ExportService with mock repository."""
    return ExportService(repository=mock_repository)


@pytest.fixture
def sample_record():
    """Create a sample extraction record."""
    return ExtractionRecordDB(
        id=uuid4(),
        source_file="/app/data/forms/contact_form_1.html",
        record_type="FORM",
        extracted_data={
            "full_name": "Test User",
            "email": "test@example.com",
            "phone": "123-456-7890",
            "company": "Test Company",
            "service_interest": "web_development",
            "message": "Test message",
            "priority": "high",
        },
        confidence_score=0.95,
        warnings=[],
        errors=[],
        status="pending",
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )


@pytest.fixture
def sample_invoice_record():
    """Create a sample invoice record."""
    return ExtractionRecordDB(
        id=uuid4(),
        source_file="/app/data/invoices/invoice_001.html",
        record_type="INVOICE",
        extracted_data={
            "invoice_number": "INV-001",
            "client_name": "Test Client",
            "net_amount": 1000.00,
            "vat_amount": 240.00,
            "total_amount": 1240.00,
            "notes": "Test invoice",
        },
        confidence_score=0.92,
        warnings=[],
        errors=[],
        status="approved",
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )


@pytest.fixture
def sample_email_record():
    """Create a sample email record."""
    return ExtractionRecordDB(
        id=uuid4(),
        source_file="/app/data/emails/email_01.eml",
        record_type="EMAIL",
        extracted_data={
            "sender_name": "John Doe",
            "sender_email": "john@example.com",
            "body": "This is a test email body.",
            "service_interest": "consulting",
        },
        confidence_score=0.88,
        warnings=[],
        errors=[],
        status="pending",
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )


class TestRecordService:
    """Tests for RecordService."""

    @pytest.mark.anyio
    async def test_get_record_found(self, record_service, mock_repository, sample_record):
        """Test getting an existing record."""
        mock_repository.get_by_id.return_value = sample_record

        result = await record_service.get_record(sample_record.id)

        assert result == sample_record
        mock_repository.get_by_id.assert_called_once_with(sample_record.id)

    @pytest.mark.anyio
    async def test_get_record_not_found(self, record_service, mock_repository):
        """Test getting a non-existent record."""
        mock_repository.get_by_id.return_value = None
        record_id = uuid4()

        result = await record_service.get_record(record_id)

        assert result is None
        mock_repository.get_by_id.assert_called_once_with(record_id)

    @pytest.mark.anyio
    async def test_list_records(self, record_service, mock_repository, sample_record):
        """Test listing records with pagination."""
        mock_repository.list_records.return_value = ([sample_record], 1)

        records, total = await record_service.list_records(
            status="pending", record_type="FORM", skip=0, limit=10
        )

        assert len(records) == 1
        assert total == 1
        mock_repository.list_records.assert_called_once_with(
            status="pending", record_type="FORM", skip=0, limit=10
        )

    @pytest.mark.anyio
    async def test_approve_pending_record(self, record_service, mock_repository, sample_record):
        """Test approving a pending record."""
        mock_repository.get_by_id.return_value = sample_record
        mock_repository.update.return_value = sample_record

        request = ApproveRequest(notes="Looks good!")
        result = await record_service.approve(sample_record.id, request, user_id="test_user")

        assert result.status == "approved"
        assert result.reviewed_by == "test_user"
        mock_repository.update.assert_called_once()

    @pytest.mark.anyio
    async def test_approve_edited_record(self, record_service, mock_repository, sample_record):
        """Test approving an edited record."""
        sample_record.status = "edited"
        mock_repository.get_by_id.return_value = sample_record
        mock_repository.update.return_value = sample_record

        request = ApproveRequest(notes="Approved after edit")
        result = await record_service.approve(sample_record.id, request)

        assert result.status == "approved"
        mock_repository.update.assert_called_once()

    @pytest.mark.anyio
    async def test_approve_not_found(self, record_service, mock_repository):
        """Test approving a non-existent record."""
        mock_repository.get_by_id.return_value = None

        with pytest.raises(ValueError, match="Record not found"):
            await record_service.approve(uuid4(), ApproveRequest())

    @pytest.mark.anyio
    async def test_approve_invalid_status(self, record_service, mock_repository, sample_record):
        """Test approving a record with invalid status."""
        sample_record.status = "rejected"
        mock_repository.get_by_id.return_value = sample_record

        with pytest.raises(ValueError, match="Cannot approve record with status"):
            await record_service.approve(sample_record.id, ApproveRequest())

    @pytest.mark.anyio
    async def test_reject_pending_record(self, record_service, mock_repository, sample_record):
        """Test rejecting a pending record."""
        mock_repository.get_by_id.return_value = sample_record
        mock_repository.update.return_value = sample_record

        request = RejectRequest(reason="Data is incorrect")
        result = await record_service.reject(sample_record.id, request, user_id="test_user")

        assert result.status == "rejected"
        assert result.rejection_reason == "Data is incorrect"
        mock_repository.update.assert_called_once()

    @pytest.mark.anyio
    async def test_reject_not_found(self, record_service, mock_repository):
        """Test rejecting a non-existent record."""
        mock_repository.get_by_id.return_value = None

        with pytest.raises(ValueError, match="Record not found"):
            await record_service.reject(uuid4(), RejectRequest(reason="Test"))

    @pytest.mark.anyio
    async def test_reject_invalid_status(self, record_service, mock_repository, sample_record):
        """Test rejecting a record with invalid status."""
        sample_record.status = "approved"
        mock_repository.get_by_id.return_value = sample_record

        with pytest.raises(ValueError, match="Cannot reject record with status"):
            await record_service.reject(sample_record.id, RejectRequest(reason="Test"))

    @pytest.mark.anyio
    async def test_edit_pending_record(self, record_service, mock_repository, sample_record):
        """Test editing a pending record."""
        mock_repository.get_by_id.return_value = sample_record
        mock_repository.update.return_value = sample_record

        new_data = {"full_name": "Updated Name", "email": "updated@example.com"}
        request = EditRequest(data=new_data, notes="Fixed name")
        result = await record_service.edit(sample_record.id, request, user_id="test_user")

        assert result.status == "edited"
        assert result.edited_data == new_data
        mock_repository.update.assert_called_once()

    @pytest.mark.anyio
    async def test_edit_already_edited_record(self, record_service, mock_repository, sample_record):
        """Test editing an already edited record."""
        sample_record.status = "edited"
        mock_repository.get_by_id.return_value = sample_record
        mock_repository.update.return_value = sample_record

        new_data = {"full_name": "Another Update"}
        request = EditRequest(data=new_data)
        result = await record_service.edit(sample_record.id, request)

        assert result.status == "edited"
        mock_repository.update.assert_called_once()

    @pytest.mark.anyio
    async def test_edit_not_found(self, record_service, mock_repository):
        """Test editing a non-existent record."""
        mock_repository.get_by_id.return_value = None

        with pytest.raises(ValueError, match="Record not found"):
            await record_service.edit(uuid4(), EditRequest(data={"test": "data"}))

    @pytest.mark.anyio
    async def test_edit_invalid_status(self, record_service, mock_repository, sample_record):
        """Test editing a record with invalid status."""
        sample_record.status = "approved"
        mock_repository.get_by_id.return_value = sample_record

        with pytest.raises(ValueError, match="Cannot edit record with status"):
            await record_service.edit(sample_record.id, EditRequest(data={"test": "data"}))

    @pytest.mark.anyio
    async def test_get_stats(self, record_service, mock_repository):
        """Test getting dashboard statistics."""
        mock_repository.get_stats.return_value = {
            "by_status": {"pending": 5, "approved": 10, "rejected": 2, "edited": 3, "exported": 1},
            "by_type": {"FORM": 8, "EMAIL": 7, "INVOICE": 6},
        }

        stats = await record_service.get_stats()

        assert stats["total"] == 21
        assert stats["pending_count"] == 5
        assert stats["approved_count"] == 13  # approved + edited
        assert stats["rejected_count"] == 2
        assert stats["exported_count"] == 1


class TestExportService:
    """Tests for ExportService."""

    @pytest.mark.anyio
    async def test_export_csv(self, export_service, mock_repository, sample_record):
        """Test exporting records to CSV."""
        sample_record.status = "approved"
        mock_repository.get_exportable_records.return_value = [sample_record]
        mock_repository.update.return_value = sample_record

        request = ExportRequest(format="csv")
        content, filename, content_type, exported_ids = await export_service.export_records(request)

        assert filename.endswith(".csv")
        assert content_type == "text/csv; charset=utf-8"
        assert b"Client_Name" in content  # Header present
        assert b"Test User" in content  # Data present
        mock_repository.update.assert_called()  # Record marked as exported

    @pytest.mark.anyio
    async def test_export_json(self, export_service, mock_repository, sample_record):
        """Test exporting records to JSON."""
        sample_record.status = "approved"
        mock_repository.get_exportable_records.return_value = [sample_record]
        mock_repository.update.return_value = sample_record

        request = ExportRequest(format="json")
        content, filename, content_type, _ = await export_service.export_records(request)

        assert filename.endswith(".json")
        assert content_type == "application/json; charset=utf-8"
        import json
        data = json.loads(content)
        assert "records" in data
        assert data["record_count"] == 1

    @pytest.mark.anyio
    async def test_export_xlsx(self, export_service, mock_repository, sample_record):
        """Test exporting records to Excel."""
        sample_record.status = "approved"
        mock_repository.get_exportable_records.return_value = [sample_record]
        mock_repository.update.return_value = sample_record

        request = ExportRequest(format="xlsx")
        content, filename, content_type, _ = await export_service.export_records(request)

        assert filename.endswith(".xlsx")
        assert "spreadsheetml" in content_type
        # Excel files start with PK (zip format)
        assert content[:2] == b"PK"

    @pytest.mark.anyio
    async def test_export_no_records(self, export_service, mock_repository):
        """Test exporting when no records available."""
        mock_repository.get_exportable_records.return_value = []

        request = ExportRequest(format="csv")
        with pytest.raises(ValueError, match="No records to export"):
            await export_service.export_records(request)

    @pytest.mark.anyio
    async def test_export_invoice_record(self, export_service, mock_repository, sample_invoice_record):
        """Test exporting invoice records."""
        mock_repository.get_exportable_records.return_value = [sample_invoice_record]
        mock_repository.update.return_value = sample_invoice_record

        request = ExportRequest(format="csv")
        content, filename, _, _ = await export_service.export_records(request)

        content_str = content.decode("utf-8")
        assert "INV-001" in content_str
        assert "1000" in content_str or "1000.0" in content_str

    @pytest.mark.anyio
    async def test_export_email_record(self, export_service, mock_repository, sample_email_record):
        """Test exporting email records."""
        sample_email_record.status = "approved"
        mock_repository.get_exportable_records.return_value = [sample_email_record]
        mock_repository.update.return_value = sample_email_record

        request = ExportRequest(format="csv")
        content, filename, _, _ = await export_service.export_records(request)

        content_str = content.decode("utf-8")
        assert "john@example.com" in content_str

    @pytest.mark.anyio
    async def test_export_with_specific_ids(self, export_service, mock_repository, sample_record):
        """Test exporting specific records by ID."""
        sample_record.status = "approved"
        mock_repository.get_exportable_records.return_value = [sample_record]
        mock_repository.update.return_value = sample_record

        record_ids = [sample_record.id]  # Use UUID objects directly
        request = ExportRequest(format="csv", record_ids=record_ids)
        content, _, _, _ = await export_service.export_records(request)

        mock_repository.get_exportable_records.assert_called_once_with(
            record_ids=record_ids, include_rejected=False
        )

    @pytest.mark.anyio
    async def test_export_include_rejected(self, export_service, mock_repository, sample_record):
        """Test exporting with rejected records included."""
        sample_record.status = "rejected"
        mock_repository.get_exportable_records.return_value = [sample_record]
        # Rejected records shouldn't be updated to exported
        mock_repository.update.return_value = sample_record

        request = ExportRequest(format="csv", include_rejected=True)
        content, _, _, _ = await export_service.export_records(request)

        mock_repository.get_exportable_records.assert_called_once_with(
            record_ids=None, include_rejected=True
        )
        # update should not be called for rejected records
        mock_repository.update.assert_not_called()

    def test_truncate_text_short(self, export_service):
        """Test truncating text shorter than max length."""
        result = export_service._truncate_text("Short text", 100)
        assert result == "Short text"

    def test_truncate_text_long(self, export_service):
        """Test truncating text longer than max length."""
        long_text = "A" * 100
        result = export_service._truncate_text(long_text, 50)
        assert len(result) == 50
        assert result.endswith("...")

    def test_truncate_text_none(self, export_service):
        """Test truncating None text."""
        result = export_service._truncate_text(None, 100)
        assert result is None

    def test_flatten_form_record(self, export_service, sample_record):
        """Test flattening a form record."""
        flat = export_service._flatten_record(sample_record)

        assert flat["Type"] == "FORM"
        assert flat["Client_Name"] == "Test User"
        assert flat["Email"] == "test@example.com"
        assert flat["Priority"] == "high"
        assert flat["Invoice_Number"] is None

    def test_flatten_invoice_record(self, export_service, sample_invoice_record):
        """Test flattening an invoice record."""
        flat = export_service._flatten_record(sample_invoice_record)

        assert flat["Type"] == "INVOICE"
        assert flat["Client_Name"] == "Test Client"
        assert flat["Invoice_Number"] == "INV-001"
        assert flat["Amount"] == 1000.00
        assert flat["VAT"] == 240.00
        assert flat["Priority"] is None

    def test_flatten_email_record(self, export_service, sample_email_record):
        """Test flattening an email record."""
        flat = export_service._flatten_record(sample_email_record)

        assert flat["Type"] == "EMAIL"
        assert flat["Client_Name"] == "John Doe"
        assert flat["Email"] == "john@example.com"
        assert "test email body" in flat["Message"]
