"""
Records router for CRUD operations and approval workflow.
Implements human-in-the-loop controls for data extraction.
"""

from typing import Any
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.db.database import get_db
from app.db.repositories import RecordRepository
from app.models.schemas import (
    ApproveRequest,
    BatchApproveRequest,
    BatchRejectRequest,
    EditRequest,
    ExportRequest,
    ExtractionRecord,
    ExtractionStatus,
    RecordType,
    RejectRequest,
)
from app.services.export_service import ExportService
from app.services.google_sheets_service import get_google_sheets_service
from app.services.record_service import RecordService, background_export_sync_worker

logger = get_logger(__name__)

router = APIRouter(prefix="/records", tags=["records"])


def extract_spreadsheet_id(input_value: str) -> str:
    """
    Extract spreadsheet ID from a Google Sheets URL or return the input if it's already an ID.

    Supports formats:
    - https://docs.google.com/spreadsheets/d/SPREADSHEET_ID/edit
    - https://docs.google.com/spreadsheets/d/SPREADSHEET_ID/edit?gid=0#gid=0
    - docs.google.com/spreadsheets/d/SPREADSHEET_ID/edit
    - SPREADSHEET_ID (already an ID)

    Args:
        input_value: URL or spreadsheet ID.

    Returns:
        The extracted spreadsheet ID.
    """
    import re

    if not input_value:
        return ""

    trimmed = input_value.strip()

    # If it doesn't look like a URL, assume it's already an ID
    if "/" not in trimmed and "." not in trimmed:
        return trimmed

    # Try to extract ID from URL pattern: /spreadsheets/d/[ID]/
    match = re.search(r"/spreadsheets/d/([a-zA-Z0-9_-]+)", trimmed)
    if match:
        return match.group(1)

    # If no match found, return the original input (will fail gracefully in API)
    return trimmed


# Dependencies
async def get_record_service(db: AsyncSession = Depends(get_db)) -> RecordService:
    """Get RecordService with database session and Google Sheets integration."""
    repository = RecordRepository(db)
    sheets_service = get_google_sheets_service(repository)
    return RecordService(
        repository=repository,
        sheets_service=sheets_service,
    )


async def get_export_service(db: AsyncSession = Depends(get_db)) -> ExportService:
    """Get ExportService with database session."""
    return ExportService(RecordRepository(db))


# --- LIST / READ ---


@router.get("")
async def list_records(
    status: ExtractionStatus | None = Query(None, description="Filter by status"),
    record_type: RecordType | None = Query(None, description="Filter by record type"),
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(100, ge=1, le=500, description="Maximum records to return"),
    service: RecordService = Depends(get_record_service),
) -> dict[str, Any]:
    """
    List extraction records with filtering and pagination.

    Args:
        status: Filter by workflow status (pending, approved, etc.).
        record_type: Filter by record type (FORM, EMAIL, INVOICE).
        skip: Pagination offset.
        limit: Maximum records to return.
        service: RecordService dependency.

    Returns:
        Paginated list of records with total count.
    """
    records, total = await service.list_records(
        status=status.value if status else None,
        record_type=record_type.value if record_type else None,
        skip=skip,
        limit=limit,
    )

    return {
        "records": [r.to_pydantic() for r in records],
        "total": total,
        "skip": skip,
        "limit": limit,
        "has_more": skip + len(records) < total,
    }


@router.get("/stats")
async def get_stats(
    service: RecordService = Depends(get_record_service),
) -> dict[str, Any]:
    """
    Get summary statistics for the dashboard.

    Returns:
        Counts by status and type, plus totals.
    """
    return await service.get_stats()


@router.get("/{record_id}")
async def get_record(
    record_id: UUID,
    service: RecordService = Depends(get_record_service),
) -> ExtractionRecord:
    """
    Get a single record by ID.

    Args:
        record_id: UUID of the record.
        service: RecordService dependency.

    Returns:
        ExtractionRecord with full details.
    """
    record = await service.get_record(record_id)

    if not record:
        raise HTTPException(status_code=404, detail=f"Record not found: {record_id}")

    return record.to_pydantic()


# --- WORKFLOW ---


@router.post("/{record_id}/approve")
async def approve_record(
    record_id: UUID,
    request: ApproveRequest,
    background_tasks: BackgroundTasks,
    service: RecordService = Depends(get_record_service),
) -> ExtractionRecord:
    """
    Approve a pending extraction record.

    This marks the extracted data as verified and ready for export.

    Args:
        record_id: UUID of the record to approve.
        request: Optional notes for approval.
        service: RecordService dependency.

    Returns:
        Updated ExtractionRecord with approved status.
    """
    try:
        record = await service.approve(record_id, request, background_tasks=background_tasks)
        return record.to_pydantic()
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/{record_id}/reject")
async def reject_record(
    record_id: UUID,
    request: RejectRequest,
    background_tasks: BackgroundTasks,
    service: RecordService = Depends(get_record_service),
) -> ExtractionRecord:
    """
    Reject a pending extraction record.

    This marks the extracted data as invalid and excludes it from export.

    Args:
        record_id: UUID of the record to reject.
        request: Reason for rejection (required).
        service: RecordService dependency.

    Returns:
        Updated ExtractionRecord with rejected status.
    """
    try:
        record = await service.reject(record_id, request, background_tasks=background_tasks)
        return record.to_pydantic()
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.put("/{record_id}")
async def edit_record(
    record_id: UUID,
    request: EditRequest,
    background_tasks: BackgroundTasks,
    service: RecordService = Depends(get_record_service),
) -> ExtractionRecord:
    """
    Edit a record's extracted data before approval.

    This allows human correction of extraction errors.

    Args:
        record_id: UUID of the record to edit.
        request: New data and optional notes.
        service: RecordService dependency.

    Returns:
        Updated ExtractionRecord with edited status.
    """
    try:
        record = await service.edit(record_id, request, background_tasks=background_tasks)
        return record.to_pydantic()
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# --- EXPORT ---


@router.post("/export")
async def export_records(
    request: ExportRequest,
    background_tasks: BackgroundTasks,
    service: ExportService = Depends(get_export_service),
) -> Response:
    """
    Export records to CSV, Excel, or JSON.

    By default, exports all approved and edited records.
    Specify record_ids to export specific records.
    After export, triggers auto-sync to Google Sheets if configured.

    Args:
        request: Export format and filters.
        background_tasks: FastAPI background tasks for async sync.
        service: ExportService dependency.

    Returns:
        File download response.
    """
    try:
        content, filename, content_type, exported_ids = await service.export_records(request)

        # Schedule Google Sheets sync for exported records
        if exported_ids:
            background_tasks.add_task(background_export_sync_worker, exported_ids)
            logger.info(
                "export_sync_scheduled",
                record_count=len(exported_ids),
            )

        return Response(
            content=content,
            media_type=content_type,
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# --- BATCH OPERATIONS ---


@router.post("/approve-batch")
async def approve_batch(
    request: BatchApproveRequest,
    background_tasks: BackgroundTasks,
    service: RecordService = Depends(get_record_service),
) -> dict[str, Any]:
    """
    Approve multiple records at once.

    Args:
        request: Batch approval request containing record IDs and notes.
        service: RecordService dependency.

    Returns:
        Summary of approved records and any errors.
    """
    approve_req = ApproveRequest(notes=request.notes)
    return await service.approve_batch(
        request.record_ids,
        approve_req,
        None,
        background_tasks=background_tasks
    )


@router.post("/reject-batch")
async def reject_batch(
    request: BatchRejectRequest,
    background_tasks: BackgroundTasks,
    service: RecordService = Depends(get_record_service),
) -> dict[str, Any]:
    """
    Reject multiple records at once.

    Args:
        request: Batch rejection request containing record IDs and reason.
        service: RecordService dependency.

    Returns:
        Summary of rejected records and any errors.
    """
    reject_req = RejectRequest(reason=request.reason)
    return await service.reject_batch(
        request.record_ids,
        reject_req,
        None,
        background_tasks=background_tasks
    )


# --- GOOGLE SHEETS INTEGRATION ---


async def get_sheets_service(db: AsyncSession = Depends(get_db)):
    """Get GoogleSheetsService with database session."""
    return get_google_sheets_service(RecordRepository(db))


@router.get("/sheets/status")
async def get_sheets_status(
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """
    Check if Google Sheets integration is configured.

    Returns:
        Configuration status including auto-sync and multi-sheet settings.
    """
    from app.core.config import settings
    from app.core.runtime_settings import get_auto_sync_include_rejected

    service = get_google_sheets_service(RecordRepository(db))
    configured = service.is_configured()

    return {
        "configured": configured,
        "auto_sync_enabled": settings.google_sheets_auto_sync,
        "auto_sync_include_rejected": get_auto_sync_include_rejected(),
        "multi_sheet_enabled": settings.google_sheets_multi_sheet,
        "spreadsheet_id": settings.google_spreadsheet_id,
        "message": (
            "Google Sheets integration is ready"
            if configured
            else "Google Sheets not configured. Set GOOGLE_CREDENTIALS_PATH environment variable."
        ),
    }


@router.post("/sheets/settings")
async def update_sheets_settings(
    auto_sync_include_rejected: bool | None = Query(
        None, description="Include rejected records in auto-sync"
    ),
) -> dict[str, Any]:
    """
    Update Google Sheets runtime settings.

    These settings can be changed without restarting the server.

    Args:
        auto_sync_include_rejected: Whether to include rejected records in auto-sync.

    Returns:
        Updated settings values.
    """
    from app.core.runtime_settings import (
        get_auto_sync_include_rejected,
        set_auto_sync_include_rejected,
    )

    if auto_sync_include_rejected is not None:
        set_auto_sync_include_rejected(auto_sync_include_rejected)

    return {
        "auto_sync_include_rejected": get_auto_sync_include_rejected(),
        "message": "Settings updated successfully",
    }


@router.post("/sheets/create")
async def create_spreadsheet(
    title: str | None = Query(None, description="Spreadsheet title"),
    service=Depends(get_sheets_service),
) -> dict[str, Any]:
    """
    Create a new Google Spreadsheet for EllinCRM data.

    Args:
        title: Optional custom title for the spreadsheet.
        service: GoogleSheetsService dependency.

    Returns:
        Spreadsheet ID and URL.
    """
    try:
        result = await service.create_spreadsheet(title)
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        error_str = str(e)
        logger.error("create_spreadsheet_failed", error=error_str)

        # Check for quota exceeded error and provide helpful message
        if "storageQuotaExceeded" in error_str or "quota" in error_str.lower():
            raise HTTPException(
                status_code=400,
                detail=(
                    "Cannot create new spreadsheet due to Google account restrictions. "
                    "Please create a spreadsheet manually in your Google Drive, "
                    "share it with the service account email "
                    "as Editor, then use 'Sync to Existing' with that spreadsheet's ID."
                )
            )

        raise HTTPException(status_code=500, detail=f"Failed to create spreadsheet: {e}")


@router.post("/sheets/sync")
async def sync_to_sheets(
    spreadsheet_id: str = Query(..., description="Target spreadsheet ID or full URL"),
    include_rejected: bool = Query(False, description="Include rejected records"),
    service=Depends(get_sheets_service),
) -> dict[str, Any]:
    """
    Sync all exportable records to a Google Spreadsheet.

    This will clear existing data and write all current records.
    Accepts either a spreadsheet ID or a full Google Sheets URL.

    Args:
        spreadsheet_id: Target Google Spreadsheet ID or full URL.
        include_rejected: Whether to include rejected records.
        service: GoogleSheetsService dependency.

    Returns:
        Sync statistics and spreadsheet URL.
    """
    # Extract ID from URL if a full URL was provided
    actual_id = extract_spreadsheet_id(spreadsheet_id)

    if not actual_id:
        raise HTTPException(
            status_code=400,
            detail="Invalid spreadsheet ID or URL. Please provide a valid Google Sheets ID or URL.",
        )

    logger.info(
        "sync_to_sheets_request",
        original_input=spreadsheet_id[:50] + "..." if len(spreadsheet_id) > 50 else spreadsheet_id,
        extracted_id=actual_id,
    )

    try:
        result = await service.sync_records(actual_id, include_rejected=include_rejected)
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error("sync_to_sheets_failed", error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to sync to spreadsheet: {e}")


# --- AUDIT LOGS ---


@router.get("/audit/logs")
async def get_audit_logs(
    record_id: UUID | None = Query(None, description="Filter by record ID"),
    action: str | None = Query(None, description="Filter by action type"),
    limit: int = Query(100, ge=1, le=500, description="Maximum logs to return"),
    skip: int = Query(0, ge=0, description="Number of logs to skip"),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """
    Get audit logs for compliance and debugging.

    Provides a queryable history of all user actions and system events.

    Args:
        record_id: Filter by specific record.
        action: Filter by action type (e.g., 'record_approved', 'data_export').
        limit: Maximum logs to return.
        skip: Pagination offset.
        db: Database session dependency.

    Returns:
        Paginated list of audit log entries.
    """
    from sqlalchemy import desc, func, select

    from app.db.models import AuditLogDB

    # Build query
    query = select(AuditLogDB)

    if record_id:
        query = query.where(AuditLogDB.record_id == record_id)
    if action:
        query = query.where(AuditLogDB.action == action)

    # Count total
    count_query = select(func.count()).select_from(AuditLogDB)
    if record_id:
        count_query = count_query.where(AuditLogDB.record_id == record_id)
    if action:
        count_query = count_query.where(AuditLogDB.action == action)

    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0

    # Get logs with pagination, ordered by newest first
    query = query.order_by(desc(AuditLogDB.timestamp)).offset(skip).limit(limit)
    result = await db.execute(query)
    logs = result.scalars().all()

    return {
        "logs": [
            {
                "id": str(log.id),
                "action": log.action,
                "record_id": str(log.record_id) if log.record_id else None,
                "user_id": log.user_id,
                "details": log.details,
                "timestamp": log.timestamp.isoformat() if log.timestamp else None,
            }
            for log in logs
        ],
        "total": total,
        "skip": skip,
        "limit": limit,
        "has_more": skip + len(logs) < total,
    }


@router.get("/audit/logs/{record_id}")
async def get_record_audit_history(
    record_id: UUID,
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """
    Get complete audit history for a specific record.

    Shows all actions taken on a record in chronological order.

    Args:
        record_id: UUID of the record.
        db: Database session dependency.

    Returns:
        List of all audit log entries for the record.
    """
    from sqlalchemy import asc, select

    from app.db.models import AuditLogDB

    query = (
        select(AuditLogDB)
        .where(AuditLogDB.record_id == record_id)
        .order_by(asc(AuditLogDB.timestamp))
    )

    result = await db.execute(query)
    logs = result.scalars().all()

    return {
        "record_id": str(record_id),
        "history": [
            {
                "id": str(log.id),
                "action": log.action,
                "user_id": log.user_id,
                "details": log.details,
                "timestamp": log.timestamp.isoformat() if log.timestamp else None,
            }
            for log in logs
        ],
        "total_actions": len(logs),
    }
