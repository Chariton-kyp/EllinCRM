"""
Form Extractor for HTML contact forms.
Uses BeautifulSoup for reliable HTML parsing.
"""

from datetime import datetime
from pathlib import Path

from bs4 import BeautifulSoup

from app.core.logging import get_logger
from app.extractors.base import BaseExtractor
from app.models.schemas import (
    ContactFormData,
    ExtractionResult,
    Priority,
    RecordType,
)

logger = get_logger(__name__)

# Mapping of Greek priority values to enum
PRIORITY_MAP = {
    "υψηλή": Priority.HIGH,
    "υψηλη": Priority.HIGH,
    "high": Priority.HIGH,
    "μεσαία": Priority.MEDIUM,
    "μεσαια": Priority.MEDIUM,
    "medium": Priority.MEDIUM,
    "χαμηλή": Priority.LOW,
    "χαμηλη": Priority.LOW,
    "low": Priority.LOW,
}

# Mapping of Greek service names to standardized values
SERVICE_MAP = {
    "web_development": "Ανάπτυξη Website",
    "ανάπτυξη website": "Ανάπτυξη Website",
    "e-commerce": "E-commerce",
    "crm": "CRM System",
    "erp": "ERP Integration",
    "database": "Διαχείριση Βάσης Δεδομένων",
    "διαχείριση βάσης δεδομένων": "Διαχείριση Βάσης Δεδομένων",
    "cloud": "Cloud Services",
    "security": "Cybersecurity",
    "support": "IT Support",
    "other": "Άλλο",
}


class FormExtractor(BaseExtractor[ContactFormData]):
    """
    Extractor for HTML contact forms.

    Parses HTML forms and extracts customer contact information
    including name, email, phone, company, service interest, and message.
    """

    record_type = RecordType.FORM

    def extract(self, file_path: Path) -> ExtractionResult:
        """
        Extract data from an HTML contact form.

        Args:
            file_path: Path to the HTML file.

        Returns:
            ExtractionResult with ContactFormData.
        """
        extraction_id = str(file_path.name)
        warnings: list[str] = []
        errors: list[str] = []

        try:
            # Read and parse HTML
            html_content = self.read_file(file_path)
            soup = BeautifulSoup(html_content, "html.parser")

            # Extract form fields
            extracted = self._extract_form_fields(soup)

            # Parse submission date
            submission_date = self._parse_date(extracted.get("submission_date"))
            if not submission_date:
                warnings.append("Could not parse submission date, using current time")
                submission_date = datetime.utcnow()

            # Parse priority
            priority = self._parse_priority(extracted.get("priority"))
            if priority is None:
                warnings.append("Could not determine priority, defaulting to MEDIUM")
                priority = Priority.MEDIUM

            # Parse service interest
            service = self._standardize_service(extracted.get("service"))

            # Validate required fields
            if not extracted.get("full_name"):
                errors.append("Missing required field: full_name")
            if not extracted.get("email"):
                errors.append("Missing required field: email")

            if errors:
                self._log_extraction(
                    file_path, extraction_id, False, error_message="; ".join(errors)
                )
                return self._create_result(
                    source_file=file_path.name,
                    errors=errors,
                    warnings=warnings,
                    confidence=0.0,
                )

            # Create ContactFormData
            form_data = ContactFormData(
                full_name=extracted["full_name"],
                email=extracted["email"],
                phone=extracted.get("phone"),
                company=extracted.get("company"),
                service_interest=service,
                message=extracted.get("message"),
                submission_date=submission_date,
                priority=priority,
            )

            # Validate the extracted data
            is_valid, validation_messages = self.validate(form_data)
            if not is_valid:
                warnings.extend(validation_messages)

            # Calculate confidence score
            confidence = self._calculate_confidence(form_data, warnings)

            self.logger.info(
                "form_extraction_success",
                file=str(file_path),
                name=form_data.full_name,
                confidence=confidence,
            )

            self._log_extraction(file_path, extraction_id, True, confidence)

            return self._create_result(
                source_file=file_path.name,
                data=form_data,
                confidence=confidence,
                warnings=warnings,
            )

        except FileNotFoundError as e:
            errors.append(f"File not found: {file_path}")
            self._log_extraction(file_path, extraction_id, False, error_message=str(e))
            return self._create_result(
                source_file=file_path.name,
                errors=errors,
                confidence=0.0,
            )
        except Exception as e:
            self.logger.error("form_extraction_error", file=str(file_path), error=str(e))
            errors.append(f"Extraction error: {str(e)}")
            self._log_extraction(file_path, extraction_id, False, error_message=str(e))
            return self._create_result(
                source_file=file_path.name,
                errors=errors,
                confidence=0.0,
            )

    def validate(self, data: ContactFormData) -> tuple[bool, list[str]]:
        """
        Validate extracted form data.

        Args:
            data: ContactFormData to validate.

        Returns:
            Tuple of (is_valid, list of validation messages).
        """
        messages: list[str] = []
        is_valid = True

        # Check name length
        if len(data.full_name) < 2:
            messages.append("Name seems too short")
            is_valid = False

        # Check if email domain looks valid
        if data.email and "@" in data.email:
            domain = data.email.split("@")[1]
            if "." not in domain:
                messages.append("Email domain appears invalid")
                is_valid = False

        # Check phone format
        if data.phone:
            cleaned = data.phone.replace("-", "").replace(" ", "").replace("+", "")
            if not cleaned.isdigit() or len(cleaned) < 10:
                messages.append("Phone number format may be incorrect")

        return is_valid, messages

    def _extract_form_fields(self, soup: BeautifulSoup) -> dict[str, str | None]:
        """
        Extract all form field values from HTML.

        Args:
            soup: BeautifulSoup parsed HTML.

        Returns:
            Dictionary of field names to values.
        """
        fields: dict[str, str | None] = {}

        # Map of field names to extract
        field_names = [
            "full_name",
            "email",
            "phone",
            "company",
            "service",
            "message",
            "submission_date",
            "priority",
        ]

        for field_name in field_names:
            # Try input elements
            input_elem = soup.find("input", {"name": field_name})
            if input_elem and input_elem.get("value"):
                fields[field_name] = input_elem["value"].strip()
                continue

            # Try select elements
            select_elem = soup.find("select", {"name": field_name})
            if select_elem:
                selected = select_elem.find("option", selected=True)
                if selected:
                    # Prefer value attribute, fall back to text
                    fields[field_name] = selected.get("value") or selected.get_text().strip()
                continue

            # Try textarea elements
            textarea_elem = soup.find("textarea", {"name": field_name})
            if textarea_elem:
                fields[field_name] = textarea_elem.get_text().strip()

        return fields

    def _parse_date(self, date_str: str | None) -> datetime | None:
        """
        Parse date string to datetime.

        Supports multiple formats commonly used in HTML forms.
        """
        if not date_str:
            return None

        formats = [
            "%Y-%m-%dT%H:%M",  # HTML5 datetime-local
            "%Y-%m-%d %H:%M:%S",
            "%Y-%m-%d",
            "%d/%m/%Y",
            "%d-%m-%Y",
        ]

        for fmt in formats:
            try:
                return datetime.strptime(date_str, fmt)
            except ValueError:
                continue

        return None

    def _parse_priority(self, priority_str: str | None) -> Priority | None:
        """Parse priority string to Priority enum."""
        if not priority_str:
            return None

        priority_lower = priority_str.lower().strip()
        return PRIORITY_MAP.get(priority_lower)

    def _standardize_service(self, service: str | None) -> str | None:
        """Standardize service name."""
        if not service:
            return None

        service_lower = service.lower().strip()
        return SERVICE_MAP.get(service_lower, service)

    def _calculate_confidence(
        self, data: ContactFormData, warnings: list[str]
    ) -> float:
        """
        Calculate confidence score based on extracted data quality.

        Args:
            data: Extracted ContactFormData.
            warnings: List of extraction warnings.

        Returns:
            Confidence score between 0.0 and 1.0.
        """
        # Start with perfect confidence for rule-based extraction
        confidence = 1.0

        # Reduce for each warning
        confidence -= len(warnings) * 0.05

        # Reduce if optional fields are missing
        optional_fields = [data.phone, data.company, data.service_interest, data.message]
        missing_optional = sum(1 for f in optional_fields if not f)
        confidence -= missing_optional * 0.02

        # Ensure minimum confidence
        return max(0.5, min(1.0, confidence))
