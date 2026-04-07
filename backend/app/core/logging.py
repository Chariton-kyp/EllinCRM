"""
Logging configuration with structured JSON output for production.
Provides comprehensive audit trail for all extraction operations.

Audit logs are persisted to the database for permanent storage and querying.
"""

import asyncio
import logging
import sys
import uuid
from datetime import UTC, datetime
from typing import Any

import structlog
from structlog.processors import JSONRenderer, TimeStamper
from structlog.stdlib import BoundLogger

from app.core.config import settings


def setup_logging() -> None:
    """Configure structured logging for the application."""

    # Determine log level from settings
    log_level = getattr(logging, settings.log_level.upper(), logging.INFO)

    # Shared processors for structlog
    shared_processors: list[Any] = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.PositionalArgumentsFormatter(),
        TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.UnicodeDecoder(),
    ]

    # Configure structlog
    if settings.is_production:
        # JSON output for production (easier to parse by log aggregators)
        structlog.configure(
            processors=shared_processors + [
                structlog.processors.format_exc_info,
                JSONRenderer(),
            ],
            wrapper_class=BoundLogger,
            context_class=dict,
            logger_factory=structlog.stdlib.LoggerFactory(),
            cache_logger_on_first_use=True,
        )
    else:
        # Pretty output for development
        structlog.configure(
            processors=shared_processors + [
                structlog.processors.format_exc_info,
                structlog.dev.ConsoleRenderer(colors=True),
            ],
            wrapper_class=BoundLogger,
            context_class=dict,
            logger_factory=structlog.stdlib.LoggerFactory(),
            cache_logger_on_first_use=True,
        )

    # Configure standard logging
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=log_level,
    )

    # Set levels for noisy libraries
    logging.getLogger("uvicorn.access").setLevel(logging.INFO)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)


def get_logger(name: str) -> structlog.stdlib.BoundLogger:
    """Get a structured logger instance."""
    return structlog.get_logger(name)


class AuditLogger:
    """
    Specialized logger for audit trail of extraction operations.
    Logs all user actions and system events for compliance.

    Logs are written to:
    1. stdout (structlog) - for real-time monitoring
    2. database (audit_logs table) - for permanent storage and querying
    """

    def __init__(self) -> None:
        self._logger = get_logger("audit")

    def _persist_to_db(
        self,
        action: str,
        record_id: str | None = None,
        user_id: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        """
        Persist audit log to database asynchronously.

        Uses fire-and-forget pattern to avoid blocking the main operation.
        Falls back gracefully if database is not available.
        """
        try:
            # Import here to avoid circular imports
            from app.db.database import AsyncSessionLocal
            from app.db.models import AuditLogDB

            # Skip if database is not configured
            if AsyncSessionLocal is None:
                return

            async def _save_log() -> None:
                try:
                    # Try to parse record_id as UUID, fall back to None
                    parsed_record_id = None
                    if record_id:
                        try:
                            parsed_record_id = uuid.UUID(record_id)
                        except (ValueError, AttributeError):
                            # Not a valid UUID - store original in details
                            pass

                    # Include original identifier in details if not a valid UUID
                    final_details = details.copy() if details else {}
                    if record_id and parsed_record_id is None:
                        final_details["identifier"] = record_id

                    async with AsyncSessionLocal() as session:
                        log_entry = AuditLogDB(
                            action=action,
                            record_id=parsed_record_id,
                            user_id=user_id,
                            details=final_details if final_details else None,
                        )
                        session.add(log_entry)
                        await session.commit()
                except Exception as e:
                    # Don't fail the main operation if audit logging fails
                    self._logger.warning(
                        "audit_db_persist_failed",
                        action=action,
                        error=str(e),
                    )

            # Try to get the running event loop
            try:
                loop = asyncio.get_running_loop()
                # If we're in an async context, create a task
                loop.create_task(_save_log())
            except RuntimeError:
                # No running loop - we're in sync context, skip DB persist
                # The log still goes to stdout via structlog
                pass

        except Exception as e:
            # Graceful fallback - don't crash if import fails
            self._logger.warning(
                "audit_db_import_failed",
                action=action,
                error=str(e),
            )

    def log_extraction_started(
        self,
        file_path: str,
        file_type: str,
        extraction_id: str,
    ) -> None:
        """Log when an extraction process starts."""
        details = {
            "file_path": file_path,
            "file_type": file_type,
        }

        # Log to stdout
        self._logger.info(
            "extraction_started",
            extraction_id=extraction_id,
            **details,
            timestamp=datetime.now(UTC).isoformat(),
        )

        # Persist to database
        self._persist_to_db(
            action="extraction_started",
            record_id=extraction_id,
            details=details,
        )

    def log_extraction_completed(
        self,
        extraction_id: str,
        success: bool,
        confidence_score: float | None = None,
        error_message: str | None = None,
    ) -> None:
        """Log when an extraction process completes."""
        details = {
            "success": success,
            "confidence_score": confidence_score,
            "error_message": error_message,
        }

        # Log to stdout
        self._logger.info(
            "extraction_completed",
            extraction_id=extraction_id,
            **details,
            timestamp=datetime.now(UTC).isoformat(),
        )

        # Persist to database
        self._persist_to_db(
            action="extraction_completed",
            record_id=extraction_id,
            details=details,
        )

    def log_user_action(
        self,
        action: str,
        extraction_id: str,
        user_id: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        """Log user actions (approve, reject, edit)."""
        # Log to stdout
        self._logger.info(
            "user_action",
            action=action,
            extraction_id=extraction_id,
            user_id=user_id,
            details=details or {},
            timestamp=datetime.now(UTC).isoformat(),
        )

        # Persist to database
        self._persist_to_db(
            action=action,
            record_id=extraction_id,
            user_id=user_id,
            details=details,
        )

    def log_export(
        self,
        export_format: str,
        record_count: int,
        destination: str,
    ) -> None:
        """Log data export operations."""
        details = {
            "export_format": export_format,
            "record_count": record_count,
            "destination": destination,
        }

        # Log to stdout
        self._logger.info(
            "data_export",
            **details,
            timestamp=datetime.now(UTC).isoformat(),
        )

        # Persist to database
        self._persist_to_db(
            action="data_export",
            details=details,
        )


# Global audit logger instance
audit_logger = AuditLogger()
