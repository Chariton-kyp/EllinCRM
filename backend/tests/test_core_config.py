"""
Tests for configuration module.
"""

import os
from pathlib import Path
from unittest.mock import patch

import pytest

from app.core.config import Settings


@pytest.fixture(autouse=True)
def _isolate_settings_from_dotenv(monkeypatch: pytest.MonkeyPatch) -> None:
    """Ensure Settings() in these tests ignores the developer's local .env file.

    Without this, any value present in ``backend/.env`` would leak into tests
    that try to assert "no value is configured" semantics, because pydantic-
    settings reads the env file regardless of ``patch.dict(os.environ, ...)``.
    """
    # Clearing the env_file on the class-level ``model_config`` makes new
    # Settings() instantiations within the test session use env vars only.
    monkeypatch.setitem(Settings.model_config, "env_file", None)


class TestSettings:
    """Tests for Settings class."""

    def test_default_values(self) -> None:
        """Test that settings have sensible defaults."""
        with patch.dict(os.environ, {}, clear=True):
            settings = Settings()

            assert settings.app_name == "EllinCRM"
            assert settings.app_env == "development"
            assert settings.debug is False
            assert settings.log_level == "INFO"
            assert settings.api_v1_prefix == "/api/v1"

    def test_environment_detection_development(self) -> None:
        """Test development environment detection."""
        with patch.dict(os.environ, {"APP_ENV": "development"}, clear=True):
            settings = Settings()

            assert settings.is_development is True
            assert settings.is_production is False

    def test_environment_detection_production(self) -> None:
        """Test production environment detection."""
        with patch.dict(os.environ, {"APP_ENV": "production"}, clear=True):
            settings = Settings()

            assert settings.is_development is False
            assert settings.is_production is True

    def test_cors_origins_default(self) -> None:
        """Test default CORS origins."""
        with patch.dict(os.environ, {}, clear=True):
            settings = Settings()
            assert "http://localhost:7002" in settings.cors_origins

    def test_database_url_optional(self) -> None:
        """Test that database URL is optional."""
        with patch.dict(os.environ, {}, clear=True):
            settings = Settings()
            assert settings.database_url is None

    def test_path_validation_string(self) -> None:
        """Test path validation converts strings to Path."""
        with patch.dict(os.environ, {"DATA_PATH": "/custom/path"}, clear=True):
            settings = Settings()
            assert isinstance(settings.data_path, Path)
            assert str(settings.data_path) == "/custom/path"

    def test_path_validation_none(self) -> None:
        """Test path validation handles None."""
        with patch.dict(os.environ, {}, clear=True):
            settings = Settings()
            assert settings.google_credentials_path is None

    def test_extraction_confidence_threshold(self) -> None:
        """Test extraction confidence threshold default."""
        with patch.dict(os.environ, {}, clear=True):
            settings = Settings()
            assert settings.extraction_confidence_threshold == 0.8
            assert 0.0 <= settings.extraction_confidence_threshold <= 1.0

    def test_ai_settings_defaults(self) -> None:
        """Test AI/ML settings defaults."""
        with patch.dict(os.environ, {}, clear=True):
            settings = Settings()

            assert settings.enable_ai_extraction is True
            assert (
                "gemma" in settings.embedding_model.lower()
                or "embedding" in settings.embedding_model.lower()
            )

    def test_fallback_embedding_model(self) -> None:
        """Test fallback embedding model is set."""
        with patch.dict(os.environ, {}, clear=True):
            settings = Settings()
            assert settings.fallback_embedding_model is not None
            assert len(settings.fallback_embedding_model) > 0

    def test_google_sheets_defaults(self) -> None:
        """Test Google Sheets integration defaults."""
        with patch.dict(os.environ, {}, clear=True):
            settings = Settings()

            assert settings.google_sheets_auto_sync is True
            assert settings.google_sheets_auto_sync_include_rejected is False
            assert settings.google_sheets_multi_sheet is True

    def test_db_pool_settings(self) -> None:
        """Test database pool settings."""
        with patch.dict(os.environ, {}, clear=True):
            settings = Settings()

            assert settings.db_pool_size == 5
            assert settings.db_max_overflow == 10

    def test_environment_override(self) -> None:
        """Test that environment variables override defaults."""
        env_vars = {
            "APP_NAME": "Custom App",
            "APP_ENV": "production",
            "DEBUG": "true",
            "LOG_LEVEL": "DEBUG",
        }
        with patch.dict(os.environ, env_vars, clear=True):
            settings = Settings()

            assert settings.app_name == "Custom App"
            assert settings.app_env == "production"
            assert settings.debug is True
            assert settings.log_level == "DEBUG"

    def test_log_level_validation(self) -> None:
        """Test that log level accepts valid values."""
        for level in ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]:
            with patch.dict(os.environ, {"LOG_LEVEL": level}, clear=True):
                settings = Settings()
                assert settings.log_level == level

    def test_huggingface_token_optional(self) -> None:
        """Test HuggingFace token is optional and defaults to None."""
        with patch.dict(os.environ, {}, clear=True):
            settings = Settings()
            # huggingface_token is a SecretStr | None; when not set, both the
            # SecretStr field and the _value accessor are None.
            assert settings.huggingface_token is None
            assert settings.huggingface_token_value is None

    def test_huggingface_token_from_env(self) -> None:
        """Test HuggingFace token is loaded from the environment, wrapped in SecretStr."""
        with patch.dict(os.environ, {"HUGGINGFACE_TOKEN": "hf_test123"}, clear=True):
            settings = Settings()
            # SecretStr.get_secret_value() or the `_value` accessor returns the raw token;
            # repr-ing settings never leaks it.
            assert settings.huggingface_token_value == "hf_test123"
            assert "hf_test123" not in repr(settings)
