"""
Runtime settings that can be modified at runtime without restart.

These settings override the static configuration from environment variables
and can be updated via API endpoints.
"""

from threading import Lock
from typing import Any

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)


class RuntimeSettings:
    """
    Thread-safe runtime settings store.

    Settings here override the static configuration and can be
    modified through the API without requiring a server restart.
    """

    def __init__(self):
        self._lock = Lock()
        self._settings: dict[str, Any] = {}

    def get(self, key: str, default: Any = None) -> Any:
        """Get a runtime setting value."""
        with self._lock:
            return self._settings.get(key, default)

    def set(self, key: str, value: Any) -> None:
        """Set a runtime setting value."""
        with self._lock:
            old_value = self._settings.get(key)
            self._settings[key] = value
            logger.info(
                "runtime_setting_updated",
                key=key,
                old_value=old_value,
                new_value=value,
            )

    def get_all(self) -> dict[str, Any]:
        """Get all runtime settings."""
        with self._lock:
            return self._settings.copy()

    def reset(self, key: str | None = None) -> None:
        """Reset runtime setting(s) to use static config values."""
        with self._lock:
            if key:
                if key in self._settings:
                    del self._settings[key]
                    logger.info("runtime_setting_reset", key=key)
            else:
                self._settings.clear()
                logger.info("all_runtime_settings_reset")


# Singleton instance
_runtime_settings = RuntimeSettings()


def get_auto_sync_include_rejected() -> bool:
    """
    Get the auto_sync_include_rejected setting.

    Checks runtime settings first, falls back to static config.
    """
    runtime_value = _runtime_settings.get("auto_sync_include_rejected")
    if runtime_value is not None:
        return runtime_value
    return settings.google_sheets_auto_sync_include_rejected


def set_auto_sync_include_rejected(value: bool) -> None:
    """Set the auto_sync_include_rejected setting at runtime."""
    _runtime_settings.set("auto_sync_include_rejected", value)


def get_runtime_settings_status() -> dict[str, Any]:
    """Get current runtime settings status for API response."""
    return {
        "auto_sync_include_rejected": get_auto_sync_include_rejected(),
        "auto_sync_include_rejected_source": (
            "runtime" if _runtime_settings.get("auto_sync_include_rejected") is not None
            else "environment"
        ),
    }
