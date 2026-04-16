"""
Application configuration using Pydantic Settings.
All configuration is loaded from environment variables with sensible defaults.
"""

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, PostgresDsn, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


def _secret_or_none(value: SecretStr | None) -> str | None:
    """Return the underlying string of a SecretStr, or None if unset/empty."""
    if value is None:
        return None
    raw = value.get_secret_value()
    return raw or None


class Settings(BaseSettings):
    """Application settings with environment variable support."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Application
    app_name: str = "EllinCRM"
    app_env: Literal["development", "production", "testing"] = "development"
    debug: bool = Field(default=False)
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"

    # API
    api_v1_prefix: str = "/api/v1"
    cors_origins: list[str] = Field(default=["http://localhost:7002"])

    # Database
    database_url: PostgresDsn | None = Field(
        default=None, description="PostgreSQL connection string"
    )
    db_pool_size: int = Field(default=5, ge=1, le=20)
    db_max_overflow: int = Field(default=10, ge=0, le=50)

    # Read-only database (chat agent tools — defense in depth)
    # If unset, falls back to DATABASE_URL with a runtime SET LOCAL statement_timeout.
    # Prod deployments should provision a dedicated `ellincrm_readonly` Postgres role
    # (see Alembic migration 006) and set READONLY_DATABASE_URL explicitly.
    readonly_database_url: PostgresDsn | None = Field(
        default=None, description="Dedicated read-only PostgreSQL URL for chat agent tools"
    )
    readonly_db_password: SecretStr | None = Field(
        default=None,
        description="Password for the ellincrm_readonly role (used when rewriting DATABASE_URL)",
    )

    # Paths
    data_path: Path = Field(default=Path("/app/data"))
    output_path: Path = Field(default=Path("/app/output"))

    # Extraction settings
    extraction_confidence_threshold: float = Field(
        default=0.8, ge=0.0, le=1.0, description="Minimum confidence score for auto-approval"
    )

    # AI/ML settings
    enable_ai_extraction: bool = Field(
        default=True, description="Enable AI-enhanced extraction features"
    )
    embedding_model: str = Field(
        default="google/embeddinggemma-300m",
        description="Primary embedding model (requires HuggingFace token if gated)",
    )
    fallback_embedding_model: str = Field(
        default="paraphrase-multilingual-mpnet-base-v2",
        description="Fallback model if primary fails (no auth required)",
    )
    huggingface_token: SecretStr | None = Field(
        default=None, description="HuggingFace access token for gated models"
    )

    # LLM API Keys (for any-llm router).
    # SecretStr ensures repr/logging show `**********` instead of the raw value;
    # callers obtain the real string via `get_secret_value()` or the
    # helpers below (``google_api_key_value``, ``anthropic_api_key_value``, ...).
    google_api_key: SecretStr = Field(default=SecretStr(""))
    anthropic_api_key: SecretStr = Field(default=SecretStr(""))

    # Google Sheets Integration
    google_credentials_path: Path | None = Field(
        default=None, description="Path to Google Service Account credentials JSON file"
    )
    google_spreadsheet_id: str | None = Field(
        default=None, description="Default Google Spreadsheet ID for syncing"
    )
    google_sheets_auto_sync: bool = Field(
        default=True,
        description="Automatically sync records to Google Sheets on approve/reject/edit",
    )
    google_sheets_auto_sync_include_rejected: bool = Field(
        default=False, description="Include rejected records in auto-sync to Google Sheets"
    )
    google_sheets_multi_sheet: bool = Field(
        default=True,
        description="Organize data in multiple sheets (Summary, Forms, Emails, Invoices)",
    )
    google_drive_folder_id: str | None = Field(
        default=None,
        description="Optional: Google Drive Folder ID to create sheets in (bypasses Service Account storage limits)",
    )

    @field_validator("data_path", "output_path", "google_credentials_path", mode="before")
    @classmethod
    def validate_paths(cls, v: str | Path | None) -> Path | None:
        """Convert string paths to Path objects."""
        if v is None:
            return None
        return Path(v) if isinstance(v, str) else v

    @property
    def is_development(self) -> bool:
        """Check if running in development mode."""
        return self.app_env == "development"

    @property
    def is_production(self) -> bool:
        """Check if running in production mode."""
        return self.app_env == "production"

    # --- Secret accessors --------------------------------------------------
    # These return the raw string value of a SecretStr field (or None when
    # unset/empty) without exposing the secret in repr/logs. Call these
    # inside code paths that need to authenticate to a third-party API.

    @property
    def anthropic_api_key_value(self) -> str | None:
        return _secret_or_none(self.anthropic_api_key)

    @property
    def google_api_key_value(self) -> str | None:
        return _secret_or_none(self.google_api_key)

    @property
    def huggingface_token_value(self) -> str | None:
        return _secret_or_none(self.huggingface_token)

    @property
    def readonly_db_password_value(self) -> str | None:
        return _secret_or_none(self.readonly_db_password)


@lru_cache
def get_settings() -> Settings:
    """Get cached application settings."""
    return Settings()


settings = get_settings()
