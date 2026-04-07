"""
Tests for the notification service (WebSocket notifications).
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

from starlette.websockets import WebSocketState

from app.services.notification_service import (
    NotificationManager,
    get_notification_manager,
    notification_manager,
)


class TestNotificationManager:
    """Tests for NotificationManager class."""

    @pytest.fixture
    def manager(self) -> NotificationManager:
        """Create a fresh NotificationManager instance."""
        return NotificationManager()

    @pytest.fixture
    def mock_websocket(self) -> MagicMock:
        """Create a mock WebSocket connection."""
        ws = MagicMock()
        ws.accept = AsyncMock()
        ws.send_json = AsyncMock()
        ws.client_state = WebSocketState.CONNECTED
        return ws

    @pytest.fixture
    def disconnected_websocket(self) -> MagicMock:
        """Create a mock disconnected WebSocket."""
        ws = MagicMock()
        ws.client_state = WebSocketState.DISCONNECTED
        return ws

    def test_manager_creation(self, manager: NotificationManager) -> None:
        """Test NotificationManager can be instantiated."""
        assert manager is not None
        assert manager.active_connections == []

    @pytest.mark.anyio
    async def test_connect(self, manager: NotificationManager, mock_websocket: MagicMock) -> None:
        """Test connecting a WebSocket."""
        await manager.connect(mock_websocket)

        mock_websocket.accept.assert_called_once()
        assert mock_websocket in manager.active_connections
        assert len(manager.active_connections) == 1

    @pytest.mark.anyio
    async def test_connect_multiple(
        self, manager: NotificationManager, mock_websocket: MagicMock
    ) -> None:
        """Test connecting multiple WebSockets."""
        ws2 = MagicMock()
        ws2.accept = AsyncMock()
        ws2.client_state = WebSocketState.CONNECTED

        await manager.connect(mock_websocket)
        await manager.connect(ws2)

        assert len(manager.active_connections) == 2

    def test_disconnect(self, manager: NotificationManager, mock_websocket: MagicMock) -> None:
        """Test disconnecting a WebSocket."""
        manager.active_connections.append(mock_websocket)
        assert len(manager.active_connections) == 1

        manager.disconnect(mock_websocket)

        assert mock_websocket not in manager.active_connections
        assert len(manager.active_connections) == 0

    def test_disconnect_not_connected(
        self, manager: NotificationManager, mock_websocket: MagicMock
    ) -> None:
        """Test disconnecting a WebSocket that wasn't connected."""
        # Should not raise
        manager.disconnect(mock_websocket)
        assert len(manager.active_connections) == 0

    @pytest.mark.anyio
    async def test_send_personal_message(
        self, manager: NotificationManager, mock_websocket: MagicMock
    ) -> None:
        """Test sending a personal message."""
        message = {"type": "test", "data": "hello"}

        await manager.send_personal_message(message, mock_websocket)

        mock_websocket.send_json.assert_called_once_with(message)

    @pytest.mark.anyio
    async def test_send_personal_message_disconnected(
        self, manager: NotificationManager, disconnected_websocket: MagicMock
    ) -> None:
        """Test sending to disconnected WebSocket doesn't call send_json."""
        disconnected_websocket.send_json = AsyncMock()

        await manager.send_personal_message({"test": "data"}, disconnected_websocket)

        disconnected_websocket.send_json.assert_not_called()

    @pytest.mark.anyio
    async def test_broadcast(self, manager: NotificationManager, mock_websocket: MagicMock) -> None:
        """Test broadcasting to all connections."""
        ws2 = MagicMock()
        ws2.send_json = AsyncMock()
        ws2.client_state = WebSocketState.CONNECTED

        manager.active_connections = [mock_websocket, ws2]
        message = {"type": "broadcast", "data": "hello all"}

        await manager.broadcast(message)

        mock_websocket.send_json.assert_called_once_with(message)
        ws2.send_json.assert_called_once_with(message)

    @pytest.mark.anyio
    async def test_broadcast_handles_errors(
        self, manager: NotificationManager, mock_websocket: MagicMock
    ) -> None:
        """Test broadcast handles errors gracefully."""
        mock_websocket.send_json = AsyncMock(side_effect=Exception("Connection error"))
        manager.active_connections = [mock_websocket]

        # Should not raise
        await manager.broadcast({"test": "data"})

        # Connection should be removed
        assert mock_websocket not in manager.active_connections

    @pytest.mark.anyio
    async def test_notify_record_created(
        self, manager: NotificationManager, mock_websocket: MagicMock
    ) -> None:
        """Test notifying clients of record creation."""
        manager.active_connections = [mock_websocket]

        await manager.notify_record_created(
            record_id="uuid-123",
            source_file="form_1.html",
            record_type="FORM",
        )

        mock_websocket.send_json.assert_called_once()
        call_args = mock_websocket.send_json.call_args[0][0]
        assert call_args["type"] == "record_created"
        assert call_args["data"]["record_id"] == "uuid-123"
        assert call_args["data"]["source_file"] == "form_1.html"
        assert call_args["data"]["record_type"] == "FORM"
        assert "message" in call_args

    @pytest.mark.anyio
    async def test_notify_record_approved(
        self, manager: NotificationManager, mock_websocket: MagicMock
    ) -> None:
        """Test notifying clients of record approval."""
        manager.active_connections = [mock_websocket]

        await manager.notify_record_approved(
            record_id="uuid-123",
            source_file="invoice_001.html",
            user_id="admin",
        )

        call_args = mock_websocket.send_json.call_args[0][0]
        assert call_args["type"] == "record_approved"
        assert call_args["data"]["user_id"] == "admin"

    @pytest.mark.anyio
    async def test_notify_record_approved_no_user(
        self, manager: NotificationManager, mock_websocket: MagicMock
    ) -> None:
        """Test notifying approval without user ID."""
        manager.active_connections = [mock_websocket]

        await manager.notify_record_approved(
            record_id="uuid-123",
            source_file="form.html",
        )

        call_args = mock_websocket.send_json.call_args[0][0]
        assert call_args["data"]["user_id"] is None

    @pytest.mark.anyio
    async def test_notify_record_rejected(
        self, manager: NotificationManager, mock_websocket: MagicMock
    ) -> None:
        """Test notifying clients of record rejection."""
        manager.active_connections = [mock_websocket]

        await manager.notify_record_rejected(
            record_id="uuid-123",
            source_file="email_01.eml",
            reason="Invalid data format",
        )

        call_args = mock_websocket.send_json.call_args[0][0]
        assert call_args["type"] == "record_rejected"
        assert call_args["data"]["reason"] == "Invalid data format"

    @pytest.mark.anyio
    async def test_notify_batch_operation(
        self, manager: NotificationManager, mock_websocket: MagicMock
    ) -> None:
        """Test notifying clients of batch operation."""
        manager.active_connections = [mock_websocket]

        await manager.notify_batch_operation(
            operation="approved",
            count=5,
            record_type="FORM",
        )

        call_args = mock_websocket.send_json.call_args[0][0]
        assert call_args["type"] == "batch_approved"
        assert call_args["data"]["count"] == 5
        assert call_args["data"]["operation"] == "approved"

    @pytest.mark.anyio
    async def test_notify_batch_operation_no_type(
        self, manager: NotificationManager, mock_websocket: MagicMock
    ) -> None:
        """Test batch notification without record type."""
        manager.active_connections = [mock_websocket]

        await manager.notify_batch_operation(
            operation="rejected",
            count=3,
        )

        call_args = mock_websocket.send_json.call_args[0][0]
        assert call_args["data"]["record_type"] is None

    @pytest.mark.anyio
    async def test_notify_export_complete(
        self, manager: NotificationManager, mock_websocket: MagicMock
    ) -> None:
        """Test notifying clients of export completion."""
        manager.active_connections = [mock_websocket]

        await manager.notify_export_complete(
            format="csv",
            count=25,
            filename="export_20240115.csv",
        )

        call_args = mock_websocket.send_json.call_args[0][0]
        assert call_args["type"] == "export_complete"
        assert call_args["data"]["format"] == "csv"
        assert call_args["data"]["count"] == 25
        assert call_args["data"]["filename"] == "export_20240115.csv"

    @pytest.mark.anyio
    async def test_notify_export_xlsx(
        self, manager: NotificationManager, mock_websocket: MagicMock
    ) -> None:
        """Test Excel export notification."""
        manager.active_connections = [mock_websocket]

        await manager.notify_export_complete(
            format="xlsx",
            count=100,
            filename="report.xlsx",
        )

        call_args = mock_websocket.send_json.call_args[0][0]
        assert "XLSX" in call_args["message"]

    @pytest.mark.anyio
    async def test_notify_google_sheets_sync(
        self, manager: NotificationManager, mock_websocket: MagicMock
    ) -> None:
        """Test notifying clients of Google Sheets sync."""
        manager.active_connections = [mock_websocket]

        await manager.notify_google_sheets_sync(
            synced_count=15,
            spreadsheet_url="https://docs.google.com/spreadsheets/d/123",
        )

        call_args = mock_websocket.send_json.call_args[0][0]
        assert call_args["type"] == "sheets_sync_complete"
        assert call_args["data"]["synced_count"] == 15
        assert call_args["data"]["spreadsheet_url"] == "https://docs.google.com/spreadsheets/d/123"

    @pytest.mark.anyio
    async def test_notify_error(
        self, manager: NotificationManager, mock_websocket: MagicMock
    ) -> None:
        """Test notifying clients of an error."""
        manager.active_connections = [mock_websocket]

        await manager.notify_error(
            error_type="extraction_failed",
            message="Failed to parse invoice PDF",
        )

        call_args = mock_websocket.send_json.call_args[0][0]
        assert call_args["type"] == "error"
        assert call_args["data"]["error_type"] == "extraction_failed"
        assert call_args["message"] == "Failed to parse invoice PDF"

    @pytest.mark.anyio
    async def test_notification_includes_id(
        self, manager: NotificationManager, mock_websocket: MagicMock
    ) -> None:
        """Test that notifications include unique IDs."""
        manager.active_connections = [mock_websocket]

        await manager.notify_record_created("uuid-1", "file.html", "FORM")

        call_args = mock_websocket.send_json.call_args[0][0]
        assert "id" in call_args
        # ID should be a valid UUID string
        assert len(call_args["id"]) == 36

    @pytest.mark.anyio
    async def test_notification_includes_timestamp(
        self, manager: NotificationManager, mock_websocket: MagicMock
    ) -> None:
        """Test that notifications include timestamps."""
        manager.active_connections = [mock_websocket]

        await manager.notify_record_approved("uuid-1", "file.html")

        call_args = mock_websocket.send_json.call_args[0][0]
        assert "timestamp" in call_args
        # Timestamp should be ISO format
        assert "T" in call_args["timestamp"]


class TestGetNotificationManager:
    """Tests for get_notification_manager function."""

    def test_returns_global_instance(self) -> None:
        """Test that get_notification_manager returns the global instance."""
        manager = get_notification_manager()
        assert manager is notification_manager

    def test_returns_same_instance(self) -> None:
        """Test that multiple calls return the same instance."""
        manager1 = get_notification_manager()
        manager2 = get_notification_manager()
        assert manager1 is manager2


class TestGlobalNotificationManager:
    """Tests for the global notification_manager instance."""

    def test_global_instance_exists(self) -> None:
        """Test that global notification_manager is available."""
        assert notification_manager is not None
        assert isinstance(notification_manager, NotificationManager)

    def test_global_instance_has_methods(self) -> None:
        """Test global instance has all required methods."""
        assert hasattr(notification_manager, "connect")
        assert hasattr(notification_manager, "disconnect")
        assert hasattr(notification_manager, "broadcast")
        assert hasattr(notification_manager, "notify_record_created")
        assert hasattr(notification_manager, "notify_record_approved")
        assert hasattr(notification_manager, "notify_record_rejected")
        assert hasattr(notification_manager, "notify_batch_operation")
        assert hasattr(notification_manager, "notify_export_complete")
        assert hasattr(notification_manager, "notify_google_sheets_sync")
        assert hasattr(notification_manager, "notify_error")
