"""
Base extractor class defining the interface for all extractors.
"""

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Generic, TypeVar
from uuid import uuid4

from app.core.logging import audit_logger, get_logger
from app.models.schemas import ExtractionResult, RecordType

logger = get_logger(__name__)

T = TypeVar("T")


class BaseExtractor(ABC, Generic[T]):
    """
    Abstract base class for all data extractors.

    Each extractor is responsible for parsing a specific file type
    and returning structured data with confidence scores.
    """

    record_type: RecordType

    def __init__(self) -> None:
        self.logger = get_logger(self.__class__.__name__)

    @abstractmethod
    def extract(self, file_path: Path) -> ExtractionResult:
        """
        Extract data from a file.

        Args:
            file_path: Path to the file to extract data from.

        Returns:
            ExtractionResult containing the extracted data, confidence score,
            and any warnings or errors.
        """
        pass

    @abstractmethod
    def validate(self, data: T) -> tuple[bool, list[str]]:
        """
        Validate extracted data.

        Args:
            data: The extracted data to validate.

        Returns:
            Tuple of (is_valid, list of validation messages).
        """
        pass

    def read_file(self, file_path: Path) -> str:
        """
        Read file contents with UTF-8 encoding.

        Args:
            file_path: Path to the file to read.

        Returns:
            File contents as string.

        Raises:
            FileNotFoundError: If file doesn't exist.
            UnicodeDecodeError: If file encoding is not UTF-8.
        """
        if not file_path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")

        return file_path.read_text(encoding="utf-8")

    def _create_result(
        self,
        source_file: str,
        data: T | None = None,
        confidence: float = 1.0,
        warnings: list[str] | None = None,
        errors: list[str] | None = None,
    ) -> ExtractionResult:
        """
        Create an ExtractionResult with the appropriate data field set.

        Args:
            source_file: Path to the source file.
            data: The extracted data object.
            confidence: Confidence score (0.0 to 1.0).
            warnings: List of warning messages.
            errors: List of error messages.

        Returns:
            ExtractionResult with the data in the correct field.
        """
        from app.models.schemas import ContactFormData, EmailData, InvoiceData

        result = ExtractionResult(
            id=uuid4(),
            source_file=source_file,
            record_type=self.record_type,
            confidence_score=confidence,
            warnings=warnings or [],
            errors=errors or [],
        )

        # Set the appropriate data field based on type
        if isinstance(data, ContactFormData):
            result.form_data = data
        elif isinstance(data, EmailData):
            result.email_data = data
        elif isinstance(data, InvoiceData):
            result.invoice_data = data

        return result

    def _log_extraction(
        self,
        file_path: Path,
        extraction_id: str,
        success: bool,
        confidence: float | None = None,
        error_message: str | None = None,
    ) -> None:
        """Log extraction events for audit trail."""
        audit_logger.log_extraction_started(
            file_path=str(file_path),
            file_type=self.record_type.value,
            extraction_id=extraction_id,
        )
        audit_logger.log_extraction_completed(
            extraction_id=extraction_id,
            success=success,
            confidence_score=confidence,
            error_message=error_message,
        )
