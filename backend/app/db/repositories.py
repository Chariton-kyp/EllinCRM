"""
Repository layer for database operations.
Implements data access patterns with async SQLAlchemy.
"""

from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import ExtractionRecordDB


class RecordRepository:
    """
    Repository for ExtractionRecord database operations.

    Provides async CRUD operations and specialized queries
    for the extraction records workflow.
    """

    def __init__(self, session: AsyncSession):
        """
        Initialize repository with database session.

        Args:
            session: AsyncSession from SQLAlchemy.
        """
        self.session = session

    async def commit(self) -> None:
        """
        Commit the current transaction.

        Use this when you need to ensure changes are persisted
        before triggering background tasks that use a new session.
        """
        await self.session.commit()

    async def create(self, record: ExtractionRecordDB) -> ExtractionRecordDB:
        """
        Create a new extraction record.

        Args:
            record: ExtractionRecordDB to create.

        Returns:
            Created record with generated ID.
        """
        self.session.add(record)
        await self.session.flush()
        await self.session.refresh(record)
        return record

    async def get_by_id(self, record_id: UUID) -> ExtractionRecordDB | None:
        """
        Get a record by its ID.

        Args:
            record_id: UUID of the record.

        Returns:
            ExtractionRecordDB if found, None otherwise.
        """
        stmt = select(ExtractionRecordDB).where(ExtractionRecordDB.id == record_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_records(
        self,
        status: str | None = None,
        record_type: str | None = None,
        skip: int = 0,
        limit: int = 100,
    ) -> tuple[list[ExtractionRecordDB], int]:
        """
        List records with filtering and pagination.

        Args:
            status: Filter by status (pending, approved, etc.).
            record_type: Filter by record type (FORM, EMAIL, INVOICE).
            skip: Number of records to skip.
            limit: Maximum records to return.

        Returns:
            Tuple of (list of records, total count).
        """
        # Build base query
        stmt = select(ExtractionRecordDB)
        count_stmt = select(func.count()).select_from(ExtractionRecordDB)

        # Apply filters
        if status:
            stmt = stmt.where(ExtractionRecordDB.status == status)
            count_stmt = count_stmt.where(ExtractionRecordDB.status == status)
        if record_type:
            stmt = stmt.where(ExtractionRecordDB.record_type == record_type)
            count_stmt = count_stmt.where(ExtractionRecordDB.record_type == record_type)

        # Order by created_at descending (newest first)
        stmt = stmt.order_by(ExtractionRecordDB.created_at.desc())

        # Apply pagination
        stmt = stmt.offset(skip).limit(limit)

        # Execute queries
        result = await self.session.execute(stmt)
        count_result = await self.session.execute(count_stmt)

        return list(result.scalars().all()), count_result.scalar_one()

    async def update(self, record: ExtractionRecordDB) -> ExtractionRecordDB:
        """
        Update an existing record.

        Args:
            record: Record with updated fields.

        Returns:
            Updated record.
        """
        await self.session.flush()
        await self.session.refresh(record)
        return record

    async def delete(self, record: ExtractionRecordDB) -> None:
        """
        Delete a record.

        Args:
            record: Record to delete.
        """
        await self.session.delete(record)
        await self.session.flush()

    async def get_exportable_records(
        self,
        record_ids: list[UUID] | None = None,
        include_rejected: bool = False,
    ) -> list[ExtractionRecordDB]:
        """
        Get records ready for export.

        Args:
            record_ids: Specific IDs to export (None = all exportable).
            include_rejected: Include rejected records in export.

        Returns:
            List of records to export.
        """
        stmt = select(ExtractionRecordDB)

        if record_ids:
            # Export specific records
            stmt = stmt.where(ExtractionRecordDB.id.in_(record_ids))
        else:
            # Export all approved/edited records
            allowed_statuses = ["approved", "edited", "exported"]
            if include_rejected:
                allowed_statuses.append("rejected")
            stmt = stmt.where(ExtractionRecordDB.status.in_(allowed_statuses))

        stmt = stmt.order_by(ExtractionRecordDB.created_at.asc())

        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_stats(self) -> dict[str, dict[str, int]]:
        """
        Get statistics for dashboard.

        Returns:
            Dictionary with counts by status and type.
        """
        # Count by status
        status_query = select(
            ExtractionRecordDB.status, func.count(ExtractionRecordDB.id)
        ).group_by(ExtractionRecordDB.status)

        status_result = await self.session.execute(status_query)
        status_counts = dict(status_result.all())

        # Count by type
        type_query = select(
            ExtractionRecordDB.record_type, func.count(ExtractionRecordDB.id)
        ).group_by(ExtractionRecordDB.record_type)

        type_result = await self.session.execute(type_query)
        type_counts = dict(type_result.all())

        return {
            "by_status": status_counts,
            "by_type": type_counts,
        }

    async def exists(self, record_id: UUID) -> bool:
        """
        Check if a record exists.

        Args:
            record_id: UUID of the record.

        Returns:
            True if record exists.
        """
        stmt = select(func.count()).where(ExtractionRecordDB.id == record_id)
        result = await self.session.execute(stmt)
        return result.scalar_one() > 0

    async def get_by_source_file(self, source_file: str) -> ExtractionRecordDB | None:
        """
        Get a record by source file name.

        Args:
            source_file: Name of the source file.

        Returns:
            ExtractionRecordDB if found, None otherwise.
        """
        stmt = select(ExtractionRecordDB).where(
            ExtractionRecordDB.source_file == source_file
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()
