"""
Record service for business logic operations.
Handles workflow actions: create, approve, reject, edit.
Integrates with AI embedding service for semantic search.
Integrates with Google Sheets for auto-sync on record changes.
"""

from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any
from uuid import UUID

from fastapi import BackgroundTasks

from app.core.logging import audit_logger, get_logger
from app.db.models import ExtractionRecordDB
from app.db.repositories import RecordRepository
from app.models.schemas import (
    ApproveRequest,
    EditRequest,
    ExtractionResult,
    RejectRequest,
)

if TYPE_CHECKING:
    from app.ai.similarity import SimilaritySearchService
    from app.services.google_sheets_service import (
        GoogleSheetsService,
        GoogleSheetsServiceFallback,
    )

from app.db.database import AsyncSessionLocal
from app.services.google_sheets_service import GoogleSheetsService
from app.services.notification_service import get_notification_manager


async def background_sync_worker(record_id: UUID, action: str) -> None:
    """
    Background worker to sync record with fresh DB session.
    Prevents DetachedInstanceError by avoiding reuse of closed request sessions.
    """
    if not AsyncSessionLocal:
        return

    async with AsyncSessionLocal() as session:
        try:
            # Re-initialize services with fresh session
            repo = RecordRepository(session)
            sheets_service = GoogleSheetsService(repo)

            record = await repo.get_by_id(record_id)
            if record:
                # We need to manually check if configured as we don't have settings here easily
                # or assume Service handles it. GoogleSheetsService checks settings internally.
                if sheets_service.is_configured():
                    await sheets_service.auto_sync_record(record, action)

        except Exception as e:
            logger.error(
                "background_sync_failed",
                record_id=str(record_id),
                action=action,
                error=str(e)
            )


async def background_export_sync_worker(record_ids: list[str]) -> None:
    """
    Background worker to sync multiple exported records with fresh DB session.
    Called after export to update Google Sheets with new 'exported' status.
    """
    if not AsyncSessionLocal:
        return

    async with AsyncSessionLocal() as session:
        try:
            repo = RecordRepository(session)
            sheets_service = GoogleSheetsService(repo)

            if not sheets_service.is_configured():
                return

            # Sync each exported record
            for record_id_str in record_ids:
                try:
                    record_id = UUID(record_id_str)
                    record = await repo.get_by_id(record_id)
                    if record and record.status == "exported":
                        await sheets_service.auto_sync_record(record, "exported")
                except Exception as e:
                    logger.warning(
                        "background_export_sync_record_failed",
                        record_id=record_id_str,
                        error=str(e)
                    )

            logger.info(
                "background_export_sync_completed",
                record_count=len(record_ids)
            )

        except Exception as e:
            logger.error(
                "background_export_sync_failed",
                record_count=len(record_ids),
                error=str(e)
            )

logger = get_logger(__name__)


class RecordService:
    """
    Service for managing extraction records workflow.

    Provides business logic for:
    - Creating records from extractions
    - Approving/rejecting records
    - Editing record data
    - Generating embeddings for semantic search
    - Auto-syncing to Google Sheets on record changes
    """

    def __init__(
        self,
        repository: RecordRepository,
        similarity_service: "SimilaritySearchService | None" = None,
        sheets_service: "GoogleSheetsService | GoogleSheetsServiceFallback | None" = None,
    ):
        """
        Initialize service with repository.

        Args:
            repository: RecordRepository for data access.
            similarity_service: Optional SimilaritySearchService for embeddings.
            sheets_service: Optional GoogleSheetsService for auto-sync.
        """
        self.repository = repository
        self._similarity_service = similarity_service
        self._sheets_service = sheets_service

    @property
    def similarity_service(self) -> "SimilaritySearchService | None":
        """Get the similarity service if available."""
        return self._similarity_service

    @property
    def sheets_service(self) -> "GoogleSheetsService | GoogleSheetsServiceFallback | None":
        """Get the Google Sheets service if available."""
        return self._sheets_service

    def set_similarity_service(self, service: "SimilaritySearchService") -> None:
        """Set the similarity service for embedding generation."""
        self._similarity_service = service

    def set_sheets_service(
        self,
        service: "GoogleSheetsService | GoogleSheetsServiceFallback",
    ) -> None:
        """Set the Google Sheets service for auto-sync."""
        self._sheets_service = service

    async def _trigger_auto_sync(
        self,
        record: ExtractionRecordDB,
        action: str,
        background_tasks: BackgroundTasks | None = None,
    ) -> None:
        """
        Trigger auto-sync to Google Sheets if configured.

        If background_tasks is provided, the sync runs in the background.
        Otherwise, it runs immediately (waiting for completion).

        IMPORTANT: When using background tasks, we commit the transaction first
        to ensure the background worker (which uses a new session) can see the changes.

        Args:
            record: The record that was updated.
            action: The action performed (approved, rejected, edited, created).
            background_tasks: Optional FastAPI background tasks.
        """
        if self._sheets_service:
            if background_tasks:
                # Commit the transaction BEFORE scheduling background task
                # This ensures the background worker can see the changes
                await self.repository.commit()

                # Run in background with FRESH session (pass ID, not object)
                background_tasks.add_task(
                    background_sync_worker,
                    record.id,
                    action
                )
                logger.debug(
                    "auto_sync_queued_background",
                    record_id=str(record.id),
                    action=action
                )
            else:
                # Run immediately (waiting)
                try:
                    await self._sheets_service.auto_sync_record(record, action)
                except Exception as e:
                    # Log but don't fail - auto-sync is best-effort
                    logger.warning(
                        "auto_sync_trigger_failed",
                        record_id=str(record.id),
                        action=action,
                        error=str(e),
                    )

    async def create_from_extraction(
        self,
        extraction: ExtractionResult,
        generate_embedding: bool = True,
    ) -> ExtractionRecordDB:
        """
        Create a new record from an extraction result.

        Args:
            extraction: ExtractionResult from extractor.
            generate_embedding: Whether to generate semantic embedding.

        Returns:
            Created ExtractionRecordDB.

        Raises:
            ValueError: If extraction has no data.
        """
        record = ExtractionRecordDB.from_extraction_result(extraction)
        created = await self.repository.create(record)

        audit_logger.log_user_action(
            action="record_created",
            extraction_id=str(created.id),
            details={
                "source_file": extraction.source_file,
                "record_type": extraction.record_type.value,
                "confidence_score": extraction.confidence_score,
            },
        )

        logger.info(
            "record_created",
            record_id=str(created.id),
            source_file=extraction.source_file,
        )

        # Notify clients
        await get_notification_manager().notify_record_created(
            str(created.id),
            extraction.source_file,
            extraction.record_type.value,
        )

        # Generate embedding for semantic search (async, non-blocking)
        if generate_embedding and self._similarity_service:
            try:
                await self._similarity_service.create_embedding(created)
                logger.info(
                    "embedding_generated",
                    record_id=str(created.id),
                )
            except Exception as e:
                # Don't fail record creation if embedding fails
                logger.warning(
                    "embedding_generation_failed",
                    record_id=str(created.id),
                    error=str(e),
                )

        return created

    async def get_record(self, record_id: UUID) -> ExtractionRecordDB | None:
        """
        Get a record by ID.

        Args:
            record_id: UUID of the record.

        Returns:
            ExtractionRecordDB if found, None otherwise.
        """
        return await self.repository.get_by_id(record_id)

    async def list_records(
        self,
        status: str | None = None,
        record_type: str | None = None,
        skip: int = 0,
        limit: int = 100,
    ) -> tuple[list[ExtractionRecordDB], int]:
        """
        List records with filtering.

        Args:
            status: Filter by status.
            record_type: Filter by type.
            skip: Pagination offset.
            limit: Pagination limit.

        Returns:
            Tuple of (records list, total count).
        """
        return await self.repository.list_records(
            status=status,
            record_type=record_type,
            skip=skip,
            limit=limit,
        )

    async def approve(
        self,
        record_id: UUID,
        request: ApproveRequest,
        user_id: str | None = None,
        notify: bool = True,
        background_tasks: BackgroundTasks | None = None,
        skip_sync: bool = False,
    ) -> ExtractionRecordDB:
        """
        Approve a pending record.

        Args:
            record_id: UUID of the record to approve.
            request: ApproveRequest with optional notes.
            user_id: ID of user performing action.
            notify: Whether to broadcast a real-time notification.

        Returns:
            Updated ExtractionRecordDB.

        Raises:
            ValueError: If record not found or invalid status.
        """
        record = await self.repository.get_by_id(record_id)
        if not record:
            raise ValueError(f"Record not found: {record_id}")

        if record.status not in ("pending", "edited"):
            raise ValueError(f"Cannot approve record with status: {record.status}")

        record.status = "approved"
        record.reviewed_by = user_id
        record.reviewed_at = datetime.now(UTC)
        record.review_notes = request.notes
        record.updated_at = datetime.now(UTC)

        updated = await self.repository.update(record)

        audit_logger.log_user_action(
            action="record_approved",
            extraction_id=str(record_id),
            user_id=user_id,
            details={"notes": request.notes},
        )

        logger.info("record_approved", record_id=str(record_id), user_id=user_id)

        if notify:
            # Notify clients
            await get_notification_manager().notify_record_approved(
                str(record_id),
                record.source_file,
                user_id,
            )

        # Trigger auto-sync to Google Sheets
        if not skip_sync:
            await self._trigger_auto_sync(updated, "approved", background_tasks)

        return updated

    async def reject(
        self,
        record_id: UUID,
        request: RejectRequest,
        user_id: str | None = None,
        notify: bool = True,
        background_tasks: BackgroundTasks | None = None,
        skip_sync: bool = False,
    ) -> ExtractionRecordDB:
        """
        Reject a pending record.

        Args:
            record_id: UUID of the record to reject.
            request: RejectRequest with reason.
            user_id: ID of user performing action.
            notify: Whether to broadcast a real-time notification.

        Returns:
            Updated ExtractionRecordDB.

        Raises:
            ValueError: If record not found or invalid status.
        """
        record = await self.repository.get_by_id(record_id)
        if not record:
            raise ValueError(f"Record not found: {record_id}")

        if record.status not in ("pending", "edited"):
            raise ValueError(f"Cannot reject record with status: {record.status}")

        record.status = "rejected"
        record.reviewed_by = user_id
        record.reviewed_at = datetime.now(UTC)
        record.rejection_reason = request.reason
        record.updated_at = datetime.now(UTC)

        updated = await self.repository.update(record)

        audit_logger.log_user_action(
            action="record_rejected",
            extraction_id=str(record_id),
            user_id=user_id,
            details={"reason": request.reason},
        )

        logger.info("record_rejected", record_id=str(record_id), user_id=user_id)

        if notify:
            # Notify clients
            await get_notification_manager().notify_record_rejected(
                str(record_id),
                record.source_file,
                request.reason,
            )

        # Trigger auto-sync to Google Sheets
        if not skip_sync:
            await self._trigger_auto_sync(updated, "rejected", background_tasks)

        return updated

    async def edit(
        self,
        record_id: UUID,
        request: EditRequest,
        user_id: str | None = None,
        background_tasks: BackgroundTasks | None = None,
    ) -> ExtractionRecordDB:
        """
        Edit a record's data before approval.

        Args:
            record_id: UUID of the record to edit.
            request: EditRequest with new data and optional notes.
            user_id: ID of user performing action.

        Returns:
            Updated ExtractionRecordDB.

        Raises:
            ValueError: If record not found or invalid status.
        """
        record = await self.repository.get_by_id(record_id)
        if not record:
            raise ValueError(f"Record not found: {record_id}")

        if record.status not in ("pending", "edited"):
            raise ValueError(f"Cannot edit record with status: {record.status}")

        record.edited_data = request.data
        record.status = "edited"
        record.reviewed_by = user_id
        record.reviewed_at = datetime.now(UTC)
        record.review_notes = request.notes
        record.updated_at = datetime.now(UTC)

        updated = await self.repository.update(record)

        audit_logger.log_user_action(
            action="record_edited",
            extraction_id=str(record_id),
            user_id=user_id,
            details={
                "notes": request.notes,
                "fields_changed": list(request.data.keys()),
            },
        )

        logger.info(
            "record_edited",
            record_id=str(record_id),
            user_id=user_id,
            fields=list(request.data.keys()),
        )

        # Trigger auto-sync to Google Sheets
        await self._trigger_auto_sync(updated, "edited", background_tasks)

        return updated

    async def get_stats(self) -> dict:
        """
        Get statistics for dashboard.

        Returns:
            Dictionary with status and type counts.
        """
        stats = await self.repository.get_stats()

        # Calculate totals
        total = sum(stats["by_status"].values())
        # Each status is separate for consistency with the chart
        pending = stats["by_status"].get("pending", 0)
        edited = stats["by_status"].get("edited", 0)
        approved = stats["by_status"].get("approved", 0)
        rejected = stats["by_status"].get("rejected", 0)
        exported = stats["by_status"].get("exported", 0)

        return {
            "by_status": stats["by_status"],
            "by_type": stats["by_type"],
            "total": total,
            "pending_count": pending,
            "edited_count": edited,
            "approved_count": approved + edited,  # Include edited as "ready for approval"
            "rejected_count": rejected,
            "exported_count": exported,
        }

    async def approve_batch(
        self,
        record_ids: list[UUID],
        request: ApproveRequest,
        user_id: str | None = None,
        background_tasks: BackgroundTasks | None = None,
    ) -> dict[str, Any]:
        """
        Approve multiple records with a single batch notification.
        """
        approved = []
        errors = []

        logger.info("approve_batch_start", record_ids=[str(id) for id in record_ids])

        for record_id in record_ids:
            try:
                # Approve without individual notification
                record = await self.approve(
                    record_id,
                    request,
                    user_id,
                    notify=False,
                    background_tasks=background_tasks,
                    skip_sync=True
                )
                approved.append(str(record.id))
            except Exception as e:
                logger.error("approve_batch_error", record_id=str(record_id), error=str(e))
                errors.append({"record_id": str(record_id), "error": str(e)})

        if approved:
            await get_notification_manager().notify_batch_operation(
                "approved", len(approved), "records"
            )

        # Trigger single auto-sync for the batch if successes exist
        if approved and self._sheets_service:
             # Use the first approved ID (or any) to trigger the worker
             # The worker performs a full sync anyway
             first_id = UUID(approved[0])
             # We can reuse the background worker logic
             if background_tasks:
                 background_tasks.add_task(
                     background_sync_worker,
                     first_id,
                     "batch_approved"
                 )

        # Explicitly commit to ensure background worker sees the updates
        await self.repository.session.commit()

        return {
            "approved_count": len(approved),
            "approved_ids": approved,
            "error_count": len(errors),
            "errors": errors if errors else None,
        }

    async def reject_batch(
        self,
        record_ids: list[UUID],
        request: RejectRequest,
        user_id: str | None = None,
        background_tasks: BackgroundTasks | None = None,
    ) -> dict[str, Any]:
        """
        Reject multiple records with a single batch notification.
        """
        rejected = []
        errors = []

        for record_id in record_ids:
            try:
                # Reject without individual notification
                record = await self.reject(
                    record_id,
                    request,
                    user_id,
                    notify=False,
                    background_tasks=background_tasks,
                    skip_sync=True
                )
                rejected.append(str(record.id))
            except Exception as e:
                logger.error("reject_batch_error", record_id=str(record_id), error=str(e))
                errors.append({"record_id": str(record_id), "error": str(e)})

        if rejected:
            await get_notification_manager().notify_batch_operation(
                "rejected", len(rejected), "records"
            )

        # Trigger single auto-sync for the batch
        if rejected and self._sheets_service:
             first_id = UUID(rejected[0])
             if background_tasks:
                 background_tasks.add_task(
                     background_sync_worker,
                     first_id,
                     "batch_rejected"
                 )

        # Explicitly commit to ensure background worker sees the updates
        await self.repository.session.commit()

        return {
            "rejected_count": len(rejected),
            "rejected_ids": rejected,
            "error_count": len(errors),
            "errors": errors if errors else None,
        }
