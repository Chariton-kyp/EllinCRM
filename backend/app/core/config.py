"""
Application configuration using Pydantic Settings.
All configuration is loaded from environment variables with sensible defaults.
"""

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, PostgresDsn, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


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
        default=None,
        description="PostgreSQL connection string"
    )
    db_pool_size: int = Field(default=5, ge=1, le=20)
    db_max_overflow: int = Field(default=10, ge=0, le=50)

    # Paths
    data_path: Path = Field(default=Path("/app/data"))
    output_path: Path = Field(default=Path("/app/output"))

    # Extraction settings
    extraction_confidence_threshold: float = Field(
        default=0.8,
        ge=0.0,
        le=1.0,
        description="Minimum confidence score for auto-approval"
    )

    # AI/ML settings
    enable_ai_extraction: bool = Field(
        default=True,
        description="Enable AI-enhanced extraction features"
    )
    embedding_model: str = Field(
        default="google/embeddinggemma-300m",
        description="Primary embedding model (requires HuggingFace token if gated)"
    )
    fallback_embedding_model: str = Field(
        default="paraphrase-multilingual-mpnet-base-v2",
        description="Fallback model if primary fails (no auth required)"
    )
    huggingface_token: str | None = Field(
        default=None,
        description="HuggingFace access token for gated models"
    )

    # LLM API Keys (for LiteLLM Router)
    google_api_key: str = ""
    anthropic_api_key: str = ""

    # Google Sheets Integration
    google_credentials_path: Path | None = Field(
        default=None,
        description="Path to Google Service Account credentials JSON file"
    )
    google_spreadsheet_id: str | None = Field(
        default=None,
        description="Default Google Spreadsheet ID for syncing"
    )
    google_sheets_auto_sync: bool = Field(
        default=True,
        description="Automatically sync records to Google Sheets on approve/reject/edit"
    )
    google_sheets_auto_sync_include_rejected: bool = Field(
        default=False,
        description="Include rejected records in auto-sync to Google Sheets"
    )
    google_sheets_multi_sheet: bool = Field(
        default=True,
        description="Organize data in multiple sheets (Summary, Forms, Emails, Invoices)"
    )
    google_drive_folder_id: str | None = Field(
        default=None,
        description="Optional: Google Drive Folder ID to create sheets in (bypasses Service Account storage limits)"
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


@lru_cache
def get_settings() -> Settings:
    """Get cached application settings."""
    return Settings()


settings = get_settings()
