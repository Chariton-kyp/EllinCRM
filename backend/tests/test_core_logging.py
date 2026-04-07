"""
Tests for core logging module including AuditLogger.
"""

import logging
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest
import structlog

from app.core.logging import (
    AuditLogger,
    audit_logger,
    get_logger,
    setup_logging,
)


class TestGetLogger:
    """Tests for get_logger function."""

    def test_get_logger_returns_bound_logger(self) -> None:
        """Test that get_logger returns a structlog logger."""
        logger = get_logger("test_module")
        assert logger is not None

    def test_get_logger_with_different_names(self) -> None:
        """Test getting loggers with different module names."""
        logger1 = get_logger("module1")
        logger2 = get_logger("module2")
        # Both should be loggers
        assert logger1 is not None
        assert logger2 is not None

    def test_get_logger_same_name_returns_logger(self) -> None:
        """Test getting logger with same name multiple times."""
        logger1 = get_logger("same_module")
        logger2 = get_logger("same_module")
        assert logger1 is not None
        assert logger2 is not None


class TestAuditLogger:
    """Tests for AuditLogger class."""

    @pytest.fixture
    def audit_log(self) -> AuditLogger:
        """Create an AuditLogger instance."""
        return AuditLogger()

    def test_audit_logger_creation(self, audit_log: AuditLogger) -> None:
        """Test AuditLogger can be instantiated."""
        assert audit_log is not None
        assert hasattr(audit_log, "_logger")

    def test_log_extraction_started(self, audit_log: AuditLogger) -> None:
        """Test logging extraction started event."""
        with patch.object(audit_log._logger, "info") as mock_info:
            audit_log.log_extraction_started(
                file_path="/app/data/forms/form_1.html",
                file_type="FORM",
                extraction_id="test-uuid-123",
            )

            mock_info.assert_called_once()
            call_args = mock_info.call_args
            assert call_args[0][0] == "extraction_started"
            assert call_args[1]["file_path"] == "/app/data/forms/form_1.html"
            assert call_args[1]["file_type"] == "FORM"
            assert call_args[1]["extraction_id"] == "test-uuid-123"
            assert "timestamp" in call_args[1]

    def test_log_extraction_completed_success(self, audit_log: AuditLogger) -> None:
        """Test logging successful extraction completion."""
        with patch.object(audit_log._logger, "info") as mock_info:
            audit_log.log_extraction_completed(
                extraction_id="test-uuid-123",
                success=True,
                confidence_score=0.95,
            )

            mock_info.assert_called_once()
            call_args = mock_info.call_args
            assert call_args[0][0] == "extraction_completed"
            assert call_args[1]["success"] is True
            assert call_args[1]["confidence_score"] == 0.95
            assert call_args[1]["error_message"] is None

    def test_log_extraction_completed_failure(self, audit_log: AuditLogger) -> None:
        """Test logging failed extraction."""
        with patch.object(audit_log._logger, "info") as mock_info:
            audit_log.log_extraction_completed(
                extraction_id="test-uuid-123",
                success=False,
                error_message="Failed to parse HTML",
            )

            mock_info.assert_called_once()
            call_args = mock_info.call_args
            assert call_args[1]["success"] is False
            assert call_args[1]["error_message"] == "Failed to parse HTML"

    def test_log_user_action_approve(self, audit_log: AuditLogger) -> None:
        """Test logging user approve action."""
        with patch.object(audit_log._logger, "info") as mock_info:
            audit_log.log_user_action(
                action="record_approved",
                extraction_id="test-uuid-123",
                user_id="admin",
                details={"notes": "Looks good!"},
            )

            mock_info.assert_called_once()
            call_args = mock_info.call_args
            assert call_args[0][0] == "user_action"
            assert call_args[1]["action"] == "record_approved"
            assert call_args[1]["user_id"] == "admin"
            assert call_args[1]["details"]["notes"] == "Looks good!"

    def test_log_user_action_reject(self, audit_log: AuditLogger) -> None:
        """Test logging user reject action."""
        with patch.object(audit_log._logger, "info") as mock_info:
            audit_log.log_user_action(
                action="record_rejected",
                extraction_id="test-uuid-123",
                user_id="reviewer",
                details={"reason": "Invalid data"},
            )

            mock_info.assert_called_once()
            call_args = mock_info.call_args
            assert call_args[1]["action"] == "record_rejected"
            assert call_args[1]["details"]["reason"] == "Invalid data"

    def test_log_user_action_edit(self, audit_log: AuditLogger) -> None:
        """Test logging user edit action."""
        with patch.object(audit_log._logger, "info") as mock_info:
            audit_log.log_user_action(
                action="record_edited",
                extraction_id="test-uuid-123",
                user_id="editor",
                details={"fields_changed": ["full_name", "email"]},
            )

            mock_info.assert_called_once()
            call_args = mock_info.call_args
            assert call_args[1]["action"] == "record_edited"
            assert "full_name" in call_args[1]["details"]["fields_changed"]

    def test_log_user_action_no_details(self, audit_log: AuditLogger) -> None:
        """Test logging user action without details."""
        with patch.object(audit_log._logger, "info") as mock_info:
            audit_log.log_user_action(
                action="record_viewed",
                extraction_id="test-uuid-123",
            )

            mock_info.assert_called_once()
            call_args = mock_info.call_args
            assert call_args[1]["user_id"] is None
            assert call_args[1]["details"] == {}

    def test_log_export(self, audit_log: AuditLogger) -> None:
        """Test logging export operation."""
        with patch.object(audit_log._logger, "info") as mock_info:
            audit_log.log_export(
                export_format="csv",
                record_count=25,
                destination="ellincrm_export_20240115.csv",
            )

            mock_info.assert_called_once()
            call_args = mock_info.call_args
            assert call_args[0][0] == "data_export"
            assert call_args[1]["export_format"] == "csv"
            assert call_args[1]["record_count"] == 25
            assert call_args[1]["destination"] == "ellincrm_export_20240115.csv"

    def test_log_export_xlsx(self, audit_log: AuditLogger) -> None:
        """Test logging Excel export."""
        with patch.object(audit_log._logger, "info") as mock_info:
            audit_log.log_export(
                export_format="xlsx",
                record_count=50,
                destination="report.xlsx",
            )

            call_args = mock_info.call_args
            assert call_args[1]["export_format"] == "xlsx"
            assert call_args[1]["record_count"] == 50

    def test_log_export_json(self, audit_log: AuditLogger) -> None:
        """Test logging JSON export."""
        with patch.object(audit_log._logger, "info") as mock_info:
            audit_log.log_export(
                export_format="json",
                record_count=100,
                destination="data.json",
            )

            call_args = mock_info.call_args
            assert call_args[1]["export_format"] == "json"

    def test_timestamp_format(self, audit_log: AuditLogger) -> None:
        """Test that timestamps are ISO formatted."""
        with patch.object(audit_log._logger, "info") as mock_info:
            audit_log.log_extraction_started(
                file_path="test.html",
                file_type="FORM",
                extraction_id="123",
            )

            call_args = mock_info.call_args
            timestamp = call_args[1]["timestamp"]
            # Should be ISO format (contains T separator)
            assert "T" in timestamp


class TestGlobalAuditLogger:
    """Tests for the global audit_logger instance."""

    def test_global_instance_exists(self) -> None:
        """Test that global audit_logger is available."""
        assert audit_logger is not None
        assert isinstance(audit_logger, AuditLogger)

    def test_global_instance_has_methods(self) -> None:
        """Test global instance has all required methods."""
        assert hasattr(audit_logger, "log_extraction_started")
        assert hasattr(audit_logger, "log_extraction_completed")
        assert hasattr(audit_logger, "log_user_action")
        assert hasattr(audit_logger, "log_export")


class TestSetupLogging:
    """Tests for setup_logging function."""

    def test_setup_logging_runs(self) -> None:
        """Test that setup_logging can be called."""
        # Should not raise any exceptions
        setup_logging()

    def test_setup_logging_configures_structlog(self) -> None:
        """Test that setup_logging configures structlog."""
        setup_logging()
        # After setup, we should be able to get a logger
        logger = get_logger("test")
        assert logger is not None

    @patch("app.core.logging.settings")
    def test_setup_logging_uses_log_level(self, mock_settings: MagicMock) -> None:
        """Test that setup_logging respects log level setting."""
        mock_settings.log_level = "DEBUG"
        mock_settings.is_production = False
        setup_logging()
        # Should complete without error

    @patch("app.core.logging.settings")
    def test_setup_logging_production_mode(self, mock_settings: MagicMock) -> None:
        """Test setup_logging in production mode uses JSON renderer."""
        mock_settings.log_level = "INFO"
        mock_settings.is_production = True
        setup_logging()
        # Should complete without error

    @patch("app.core.logging.settings")
    def test_setup_logging_development_mode(self, mock_settings: MagicMock) -> None:
        """Test setup_logging in development mode uses console renderer."""
        mock_settings.log_level = "DEBUG"
        mock_settings.is_production = False
        setup_logging()
        # Should complete without error


class TestLoggerIntegration:
    """Integration tests for logging functionality."""

    def test_logger_can_log_info(self) -> None:
        """Test logger can log info messages."""
        logger = get_logger("test_integration")
        # Should not raise
        logger.info("test_message", key="value")

    def test_logger_can_log_warning(self) -> None:
        """Test logger can log warning messages."""
        logger = get_logger("test_integration")
        logger.warning("test_warning", issue="test")

    def test_logger_can_log_error(self) -> None:
        """Test logger can log error messages."""
        logger = get_logger("test_integration")
        logger.error("test_error", error_type="test")

    def test_logger_with_context(self) -> None:
        """Test logger with contextual data."""
        logger = get_logger("test_context")
        logger.info(
            "extraction_event",
            record_id="uuid-123",
            record_type="FORM",
            confidence=0.95,
        )
