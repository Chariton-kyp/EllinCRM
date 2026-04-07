"""
WebSocket router for real-time notifications.
"""

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.core.logging import get_logger
from app.services.notification_service import get_notification_manager

logger = get_logger(__name__)

router = APIRouter(tags=["notifications"])


@router.websocket("/ws/notifications")
async def websocket_notifications(websocket: WebSocket):
    """
    WebSocket endpoint for real-time notifications.

    Clients connect to this endpoint to receive real-time updates about:
    - New record extractions
    - Record approvals/rejections
    - Batch operations
    - Export completions
    - Google Sheets sync status
    - Errors

    Message format:
    {
        "type": "record_created" | "record_approved" | etc.,
        "id": "unique-message-id",
        "timestamp": "ISO-8601 timestamp",
        "data": { ... },
        "message": "Human-readable message"
    }
    """
    manager = get_notification_manager()
    await manager.connect(websocket)

    try:
        while True:
            # Keep connection alive and handle incoming messages
            data = await websocket.receive_json()

            # Handle client messages (e.g., heartbeat)
            if data.get("type") == "ping":
                await manager.send_personal_message(
                    {"type": "pong", "timestamp": data.get("timestamp")},
                    websocket,
                )
            elif data.get("type") == "subscribe":
                # Could implement channel subscription here
                await manager.send_personal_message(
                    {"type": "subscribed", "channel": data.get("channel", "all")},
                    websocket,
                )

    except WebSocketDisconnect:
        manager.disconnect(websocket)
        logger.info("websocket_client_disconnected")
    except Exception as e:
        logger.error("websocket_error", error=str(e))
        manager.disconnect(websocket)


@router.get("/api/v1/notifications/status")
async def get_notification_status():
    """
    Get the current notification service status.

    Returns:
        Dictionary with connection count and service status.
    """
    manager = get_notification_manager()
    return {
        "status": "active",
        "active_connections": len(manager.active_connections),
    }
