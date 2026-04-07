"""
WebSocket notification service for real-time updates.
"""

from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from fastapi import WebSocket
from starlette.websockets import WebSocketState

from app.core.logging import get_logger

logger = get_logger(__name__)


class NotificationManager:
    """
    Manages WebSocket connections and broadcasts notifications.

    Handles:
    - Connection management (connect/disconnect)
    - Broadcasting notifications to all clients
    - Message formatting and delivery
    """

    def __init__(self):
        """Initialize the notification manager."""
        self.active_connections: list[WebSocket] = []

    async def connect(self, websocket: WebSocket) -> None:
        """
        Accept and register a new WebSocket connection.

        Args:
            websocket: The WebSocket connection to register.
        """
        await websocket.accept()
        self.active_connections.append(websocket)
        logger.info(
            "websocket_connected",
            total_connections=len(self.active_connections),
        )

    def disconnect(self, websocket: WebSocket) -> None:
        """
        Remove a WebSocket connection from active connections.

        Args:
            websocket: The WebSocket connection to remove.
        """
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
            logger.info(
                "websocket_disconnected",
                total_connections=len(self.active_connections),
            )

    async def send_personal_message(
        self, message: dict[str, Any], websocket: WebSocket
    ) -> None:
        """
        Send a message to a specific WebSocket connection.

        Args:
            message: The message dictionary to send.
            websocket: The target WebSocket connection.
        """
        if websocket.client_state == WebSocketState.CONNECTED:
            await websocket.send_json(message)

    async def broadcast(self, message: dict[str, Any]) -> None:
        """
        Broadcast a message to all active WebSocket connections.

        Args:
            message: The message dictionary to broadcast.
        """
        disconnected = []
        for connection in self.active_connections:
            try:
                if connection.client_state == WebSocketState.CONNECTED:
                    await connection.send_json(message)
            except Exception as e:
                logger.warning(
                    "websocket_broadcast_error",
                    error=str(e),
                )
                disconnected.append(connection)

        # Clean up disconnected connections
        for conn in disconnected:
            self.disconnect(conn)

    async def notify_record_created(
        self, record_id: str, source_file: str, record_type: str
    ) -> None:
        """
        Notify all clients that a new record was created.

        Args:
            record_id: UUID of the created record.
            source_file: Source file name.
            record_type: Type of record (FORM, EMAIL, INVOICE).
        """
        await self.broadcast({
            "type": "record_created",
            "id": str(uuid4()),
            "timestamp": datetime.now(UTC).isoformat(),
            "data": {
                "record_id": record_id,
                "source_file": source_file,
                "record_type": record_type,
            },
            "message": f"New {record_type.lower()} extracted from {source_file}",
        })

    async def notify_record_approved(
        self, record_id: str, source_file: str, user_id: str | None = None
    ) -> None:
        """
        Notify all clients that a record was approved.

        Args:
            record_id: UUID of the approved record.
            source_file: Source file name.
            user_id: User who approved (if available).
        """
        await self.broadcast({
            "type": "record_approved",
            "id": str(uuid4()),
            "timestamp": datetime.now(UTC).isoformat(),
            "data": {
                "record_id": record_id,
                "source_file": source_file,
                "user_id": user_id,
            },
            "message": f"Record approved: {source_file}",
        })

    async def notify_record_rejected(
        self, record_id: str, source_file: str, reason: str
    ) -> None:
        """
        Notify all clients that a record was rejected.

        Args:
            record_id: UUID of the rejected record.
            source_file: Source file name.
            reason: Rejection reason.
        """
        await self.broadcast({
            "type": "record_rejected",
            "id": str(uuid4()),
            "timestamp": datetime.now(UTC).isoformat(),
            "data": {
                "record_id": record_id,
                "source_file": source_file,
                "reason": reason,
            },
            "message": f"Record rejected: {source_file}",
        })

    async def notify_batch_operation(
        self, operation: str, count: int, record_type: str | None = None
    ) -> None:
        """
        Notify all clients about a batch operation.

        Args:
            operation: Operation type (approved, rejected, extracted).
            count: Number of records affected.
            record_type: Type of records (optional).
        """
        await self.broadcast({
            "type": f"batch_{operation}",
            "id": str(uuid4()),
            "timestamp": datetime.now(UTC).isoformat(),
            "data": {
                "operation": operation,
                "count": count,
                "record_type": record_type,
            },
            "message": f"Batch {operation}: {count} records",
        })

    async def notify_export_complete(
        self, format: str, count: int, filename: str
    ) -> None:
        """
        Notify all clients that an export was completed.

        Args:
            format: Export format (csv, xlsx, json).
            count: Number of records exported.
            filename: Generated filename.
        """
        await self.broadcast({
            "type": "export_complete",
            "id": str(uuid4()),
            "timestamp": datetime.now(UTC).isoformat(),
            "data": {
                "format": format,
                "count": count,
                "filename": filename,
            },
            "message": f"Export complete: {count} records to {format.upper()}",
        })

    async def notify_google_sheets_sync(
        self, synced_count: int, spreadsheet_url: str
    ) -> None:
        """
        Notify all clients that Google Sheets sync completed.

        Args:
            synced_count: Number of records synced.
            spreadsheet_url: URL to the spreadsheet.
        """
        await self.broadcast({
            "type": "sheets_sync_complete",
            "id": str(uuid4()),
            "timestamp": datetime.now(UTC).isoformat(),
            "data": {
                "synced_count": synced_count,
                "spreadsheet_url": spreadsheet_url,
            },
            "message": f"Google Sheets synced: {synced_count} records",
        })

    async def notify_error(self, error_type: str, message: str) -> None:
        """
        Notify all clients about an error.

        Args:
            error_type: Type of error.
            message: Error message.
        """
        await self.broadcast({
            "type": "error",
            "id": str(uuid4()),
            "timestamp": datetime.now(UTC).isoformat(),
            "data": {
                "error_type": error_type,
            },
            "message": message,
        })


# Global notification manager instance
notification_manager = NotificationManager()


def get_notification_manager() -> NotificationManager:
    """
    Get the global notification manager instance.

    Returns:
        NotificationManager singleton instance.
    """
    return notification_manager
