"""
Tests for database repository layer.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4
from datetime import datetime, timezone

from app.db.repositories import RecordRepository
from app.db.models import ExtractionRecordDB


class TestRecordRepository:
    """Tests for RecordRepository class."""

    @pytest.fixture
    def mock_session(self) -> AsyncMock:
        """Create a mock async session."""
        session = AsyncMock()
        session.add = MagicMock()
        session.flush = AsyncMock()
        session.refresh = AsyncMock()
        session.delete = AsyncMock()
        session.execute = AsyncMock()
        return session

    @pytest.fixture
    def repository(self, mock_session: AsyncMock) -> RecordRepository:
        """Create a RecordRepository with mock session."""
        return RecordRepository(mock_session)

    @pytest.fixture
    def sample_record(self) -> ExtractionRecordDB:
        """Create a sample record for testing."""
        return ExtractionRecordDB(
            id=uuid4(),
            source_file="test.html",
            record_type="FORM",
            extracted_data={"full_name": "Test", "email": "test@example.com"},
            confidence_score=0.95,
            status="pending",
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )

    def test_repository_creation(self, repository: RecordRepository) -> None:
        """Test repository can be instantiated."""
        assert repository is not None
        assert repository.session is not None

    @pytest.mark.anyio
    async def test_create(
        self,
        repository: RecordRepository,
        mock_session: AsyncMock,
        sample_record: ExtractionRecordDB,
    ) -> None:
        """Test creating a record."""
        result = await repository.create(sample_record)

        mock_session.add.assert_called_once_with(sample_record)
        mock_session.flush.assert_called_once()
        mock_session.refresh.assert_called_once_with(sample_record)
        assert result == sample_record

    @pytest.mark.anyio
    async def test_get_by_id_found(
        self,
        repository: RecordRepository,
        mock_session: AsyncMock,
        sample_record: ExtractionRecordDB,
    ) -> None:
        """Test getting a record by ID when found."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = sample_record
        mock_session.execute.return_value = mock_result

        result = await repository.get_by_id(sample_record.id)

        assert result == sample_record
        mock_session.execute.assert_called_once()

    @pytest.mark.anyio
    async def test_get_by_id_not_found(
        self,
        repository: RecordRepository,
        mock_session: AsyncMock,
    ) -> None:
        """Test getting a record by ID when not found."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_result

        result = await repository.get_by_id(uuid4())

        assert result is None

    @pytest.mark.anyio
    async def test_list_records_no_filters(
        self,
        repository: RecordRepository,
        mock_session: AsyncMock,
        sample_record: ExtractionRecordDB,
    ) -> None:
        """Test listing records without filters."""
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = [sample_record]
        mock_result = MagicMock()
        mock_result.scalars.return_value = mock_scalars

        mock_count_result = MagicMock()
        mock_count_result.scalar_one.return_value = 1

        mock_session.execute.side_effect = [mock_result, mock_count_result]

        records, total = await repository.list_records()

        assert len(records) == 1
        assert total == 1

    @pytest.mark.anyio
    async def test_list_records_with_status_filter(
        self,
        repository: RecordRepository,
        mock_session: AsyncMock,
        sample_record: ExtractionRecordDB,
    ) -> None:
        """Test listing records with status filter."""
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = [sample_record]
        mock_result = MagicMock()
        mock_result.scalars.return_value = mock_scalars

        mock_count_result = MagicMock()
        mock_count_result.scalar_one.return_value = 1

        mock_session.execute.side_effect = [mock_result, mock_count_result]

        records, total = await repository.list_records(status="pending")

        assert len(records) == 1
        assert records[0].status == "pending"

    @pytest.mark.anyio
    async def test_list_records_with_type_filter(
        self,
        repository: RecordRepository,
        mock_session: AsyncMock,
        sample_record: ExtractionRecordDB,
    ) -> None:
        """Test listing records with record type filter."""
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = [sample_record]
        mock_result = MagicMock()
        mock_result.scalars.return_value = mock_scalars

        mock_count_result = MagicMock()
        mock_count_result.scalar_one.return_value = 1

        mock_session.execute.side_effect = [mock_result, mock_count_result]

        records, total = await repository.list_records(record_type="FORM")

        assert len(records) == 1
        assert records[0].record_type == "FORM"

    @pytest.mark.anyio
    async def test_list_records_with_pagination(
        self,
        repository: RecordRepository,
        mock_session: AsyncMock,
        sample_record: ExtractionRecordDB,
    ) -> None:
        """Test listing records with pagination."""
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = [sample_record]
        mock_result = MagicMock()
        mock_result.scalars.return_value = mock_scalars

        mock_count_result = MagicMock()
        mock_count_result.scalar_one.return_value = 50

        mock_session.execute.side_effect = [mock_result, mock_count_result]

        records, total = await repository.list_records(skip=10, limit=10)

        # Total should be 50 even though we got 1 page
        assert total == 50

    @pytest.mark.anyio
    async def test_update(
        self,
        repository: RecordRepository,
        mock_session: AsyncMock,
        sample_record: ExtractionRecordDB,
    ) -> None:
        """Test updating a record."""
        sample_record.status = "approved"

        result = await repository.update(sample_record)

        mock_session.flush.assert_called_once()
        mock_session.refresh.assert_called_once_with(sample_record)
        assert result == sample_record

    @pytest.mark.anyio
    async def test_delete(
        self,
        repository: RecordRepository,
        mock_session: AsyncMock,
        sample_record: ExtractionRecordDB,
    ) -> None:
        """Test deleting a record."""
        await repository.delete(sample_record)

        mock_session.delete.assert_called_once_with(sample_record)
        mock_session.flush.assert_called_once()

    @pytest.mark.anyio
    async def test_get_exportable_records_default(
        self,
        repository: RecordRepository,
        mock_session: AsyncMock,
        sample_record: ExtractionRecordDB,
    ) -> None:
        """Test getting exportable records with defaults."""
        sample_record.status = "approved"
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = [sample_record]
        mock_result = MagicMock()
        mock_result.scalars.return_value = mock_scalars
        mock_session.execute.return_value = mock_result

        records = await repository.get_exportable_records()

        assert len(records) == 1
        mock_session.execute.assert_called_once()

    @pytest.mark.anyio
    async def test_get_exportable_records_with_ids(
        self,
        repository: RecordRepository,
        mock_session: AsyncMock,
        sample_record: ExtractionRecordDB,
    ) -> None:
        """Test getting specific records for export."""
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = [sample_record]
        mock_result = MagicMock()
        mock_result.scalars.return_value = mock_scalars
        mock_session.execute.return_value = mock_result

        records = await repository.get_exportable_records(
            record_ids=[sample_record.id]
        )

        assert len(records) == 1

    @pytest.mark.anyio
    async def test_get_exportable_records_include_rejected(
        self,
        repository: RecordRepository,
        mock_session: AsyncMock,
        sample_record: ExtractionRecordDB,
    ) -> None:
        """Test getting exportable records including rejected."""
        sample_record.status = "rejected"
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = [sample_record]
        mock_result = MagicMock()
        mock_result.scalars.return_value = mock_scalars
        mock_session.execute.return_value = mock_result

        records = await repository.get_exportable_records(include_rejected=True)

        assert len(records) == 1

    @pytest.mark.anyio
    async def test_get_stats(
        self,
        repository: RecordRepository,
        mock_session: AsyncMock,
    ) -> None:
        """Test getting statistics."""
        # Mock status counts
        mock_status_result = MagicMock()
        mock_status_result.all.return_value = [
            ("pending", 5),
            ("approved", 10),
            ("rejected", 2),
        ]

        # Mock type counts
        mock_type_result = MagicMock()
        mock_type_result.all.return_value = [
            ("FORM", 8),
            ("EMAIL", 6),
            ("INVOICE", 3),
        ]

        mock_session.execute.side_effect = [mock_status_result, mock_type_result]

        stats = await repository.get_stats()

        assert stats["by_status"]["pending"] == 5
        assert stats["by_status"]["approved"] == 10
        assert stats["by_type"]["FORM"] == 8
        assert stats["by_type"]["EMAIL"] == 6

    @pytest.mark.anyio
    async def test_exists_true(
        self,
        repository: RecordRepository,
        mock_session: AsyncMock,
        sample_record: ExtractionRecordDB,
    ) -> None:
        """Test exists returns True when record exists."""
        mock_result = MagicMock()
        mock_result.scalar_one.return_value = 1
        mock_session.execute.return_value = mock_result

        result = await repository.exists(sample_record.id)

        assert result is True

    @pytest.mark.anyio
    async def test_exists_false(
        self,
        repository: RecordRepository,
        mock_session: AsyncMock,
    ) -> None:
        """Test exists returns False when record doesn't exist."""
        mock_result = MagicMock()
        mock_result.scalar_one.return_value = 0
        mock_session.execute.return_value = mock_result

        result = await repository.exists(uuid4())

        assert result is False

    @pytest.mark.anyio
    async def test_get_by_source_file_found(
        self,
        repository: RecordRepository,
        mock_session: AsyncMock,
        sample_record: ExtractionRecordDB,
    ) -> None:
        """Test getting record by source file when found."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = sample_record
        mock_session.execute.return_value = mock_result

        result = await repository.get_by_source_file("test.html")

        assert result == sample_record
        assert result.source_file == "test.html"

    @pytest.mark.anyio
    async def test_get_by_source_file_not_found(
        self,
        repository: RecordRepository,
        mock_session: AsyncMock,
    ) -> None:
        """Test getting record by source file when not found."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_result

        result = await repository.get_by_source_file("nonexistent.html")

        assert result is None


class TestRecordRepositoryIntegration:
    """Integration-style tests for common repository patterns."""

    @pytest.fixture
    def mock_session(self) -> AsyncMock:
        """Create a mock async session."""
        session = AsyncMock()
        session.add = MagicMock()
        session.flush = AsyncMock()
        session.refresh = AsyncMock()
        session.delete = AsyncMock()
        session.execute = AsyncMock()
        return session

    @pytest.fixture
    def repository(self, mock_session: AsyncMock) -> RecordRepository:
        """Create a RecordRepository with mock session."""
        return RecordRepository(mock_session)

    @pytest.mark.anyio
    async def test_create_and_get_workflow(
        self,
        repository: RecordRepository,
        mock_session: AsyncMock,
    ) -> None:
        """Test creating then getting a record."""
        record = ExtractionRecordDB(
            id=uuid4(),
            source_file="workflow_test.html",
            record_type="FORM",
            extracted_data={"test": "data"},
            status="pending",
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )

        # Create
        await repository.create(record)
        mock_session.add.assert_called_once()

        # Get
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = record
        mock_session.execute.return_value = mock_result

        fetched = await repository.get_by_id(record.id)
        assert fetched.id == record.id

    @pytest.mark.anyio
    async def test_update_status_workflow(
        self,
        repository: RecordRepository,
        mock_session: AsyncMock,
    ) -> None:
        """Test updating record status."""
        record = ExtractionRecordDB(
            id=uuid4(),
            source_file="status_test.html",
            record_type="INVOICE",
            extracted_data={"invoice_number": "INV-001"},
            status="pending",
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )

        # Update status
        record.status = "approved"
        record.reviewed_by = "admin"
        record.reviewed_at = datetime.now(timezone.utc)

        updated = await repository.update(record)

        assert updated.status == "approved"
        assert updated.reviewed_by == "admin"

    @pytest.mark.anyio
    async def test_list_with_multiple_filters(
        self,
        repository: RecordRepository,
        mock_session: AsyncMock,
    ) -> None:
        """Test listing with both status and type filters."""
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = []
        mock_result = MagicMock()
        mock_result.scalars.return_value = mock_scalars

        mock_count_result = MagicMock()
        mock_count_result.scalar_one.return_value = 0

        mock_session.execute.side_effect = [mock_result, mock_count_result]

        records, total = await repository.list_records(
            status="approved",
            record_type="INVOICE",
            skip=0,
            limit=50,
        )

        assert records == []
        assert total == 0
        # Two execute calls: one for records, one for count
        assert mock_session.execute.call_count == 2
