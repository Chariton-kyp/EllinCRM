"""
Email Extractor for EML files.
Uses Python's email.parser for reliable email parsing.
Handles both client inquiries and invoice notifications.
"""

import re
from datetime import UTC, datetime
from decimal import Decimal
from email import message_from_string
from email.message import Message
from email.utils import parseaddr, parsedate_to_datetime
from pathlib import Path

from app.core.logging import get_logger
from app.extractors.base import BaseExtractor
from app.models.schemas import (
    EmailData,
    EmailType,
    ExtractionResult,
    RecordType,
)

logger = get_logger(__name__)

# Patterns for extracting structured data from email body
PATTERNS = {
    "name": [
        r"Όνομα:\s*(.+?)(?:\n|$)",
        r"Name:\s*(.+?)(?:\n|$)",
        r"(?:Είμαι ο|Είμαι η)\s+(.+?)(?:\s+από|\s+και|\s*[,\.])",
    ],
    "email": [
        r"Email:\s*([\w\.-]+@[\w\.-]+\.\w+)",
        r"E-mail:\s*([\w\.-]+@[\w\.-]+\.\w+)",
    ],
    "phone": [
        r"Τηλέφωνο:\s*([\d\-\s\+\(\)]+)",
        r"Phone:\s*([\d\-\s\+\(\)]+)",
        r"Τηλ\.?:\s*([\d\-\s\+\(\)]+)",
    ],
    "company": [
        r"Εταιρεία:\s*(.+?)(?:\n|$)",
        r"Company:\s*(.+?)(?:\n|$)",
        r"από την\s+(.+?)(?:\s+και|\s*[,\.]|$)",
    ],
    "position": [
        r"Θέση:\s*(.+?)(?:\n|$)",
        r"Position:\s*(.+?)(?:\n|$)",
    ],
    # Invoice notification patterns — accept any 2+ letter prefix
    # (TF- legacy TechFlow, EC- current EllinCRM, easily extensible).
    "invoice_number": [
        r"Αριθμός:\s*([A-Z]{2,}-\d{4}-\d{3})",
        r"Invoice #?:\s*([A-Z]{2,}-\d{4}-\d{3})",
        r"Τιμολόγιο #?([A-Z]{2,}-\d{4}-\d{3})",
        r"#([A-Z]{2,}-\d{4}-\d{3})",
    ],
    "net_amount": [
        r"Καθαρή Αξία:\s*€?([\d,\.]+)",
        r"Net Amount:\s*€?([\d,\.]+)",
    ],
    "vat_amount": [
        r"ΦΠΑ\s*\d*%?:\s*€?([\d,\.]+)",
        r"VAT\s*\d*%?:\s*€?([\d,\.]+)",
    ],
    "total_amount": [
        r"Συνολικό Ποσό:\s*€?([\d,\.]+)",
        r"Total:\s*€?([\d,\.]+)",
        r"ΣΥΝΟΛΟ:\s*€?([\d,\.]+)",
    ],
    "vendor": [
        r"Προμηθευτής:\s*(.+?)(?:\n|$)",
        r"Vendor:\s*(.+?)(?:\n|$)",
        r"Supplier:\s*(.+?)(?:\n|$)",
    ],
}

# Keywords indicating invoice notification
INVOICE_KEYWORDS = [
    "τιμολόγιο",
    "τιμολογίου",
    "invoice",
    "συνημμένο",
    "attachment",
    "πληρωμή",
    "payment",
    "λογιστήριο",
    "accounting",
]


class EmailExtractor(BaseExtractor[EmailData]):
    """
    Extractor for EML email files.

    Parses email files and extracts:
    - Client inquiries: Contact info, service needs
    - Invoice notifications: Invoice references, amounts
    """

    record_type = RecordType.EMAIL

    def extract(self, file_path: Path) -> ExtractionResult:
        """
        Extract data from an EML email file.

        Args:
            file_path: Path to the EML file.

        Returns:
            ExtractionResult with EmailData.
        """
        extraction_id = str(file_path.name)
        warnings: list[str] = []
        errors: list[str] = []

        try:
            # Read and parse email
            email_content = self.read_file(file_path)
            msg = message_from_string(email_content)

            # Extract basic email metadata
            sender_name, sender_email = self._parse_sender(msg)
            recipient_email = self._get_recipient(msg)
            subject = self._decode_header(msg.get("Subject", ""))
            date_sent = self._parse_date(msg)
            body = self._get_body(msg)

            if not sender_email:
                errors.append("Could not extract sender email")
                return self._create_result(
                    source_file=file_path.name,
                    errors=errors,
                    confidence=0.0,
                )

            if not date_sent:
                warnings.append("Could not parse email date, using current time")
                date_sent = datetime.now(UTC).replace(tzinfo=None)

            # Determine email type
            email_type = self._classify_email(subject, body)

            # Extract data based on email type
            extracted_data = self._extract_body_data(body, email_type)

            # Create EmailData
            email_data = EmailData(
                email_type=email_type,
                sender_name=sender_name or extracted_data.get("name"),
                sender_email=sender_email,
                recipient_email=recipient_email or "unknown@ellincrm.gr",
                subject=subject,
                date_sent=date_sent,
                body=body,
                phone=extracted_data.get("phone"),
                company=extracted_data.get("company"),
                position=extracted_data.get("position"),
                service_interest=self._extract_service_interest(subject, body),
                invoice_number=extracted_data.get("invoice_number"),
                invoice_amount=extracted_data.get("total_amount"),
                vendor_name=extracted_data.get("vendor"),
            )

            # Validate
            is_valid, validation_messages = self.validate(email_data)
            if not is_valid:
                warnings.extend(validation_messages)

            # Calculate confidence
            confidence = self._calculate_confidence(email_data, extracted_data, warnings)

            self.logger.info(
                "email_extraction_success",
                file=str(file_path),
                type=email_type.value,
                sender=sender_email,
                confidence=confidence,
            )

            self._log_extraction(file_path, extraction_id, True, confidence)

            return self._create_result(
                source_file=file_path.name,
                data=email_data,
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
            self.logger.error("email_extraction_error", file=str(file_path), error=str(e))
            errors.append(f"Extraction error: {str(e)}")
            self._log_extraction(file_path, extraction_id, False, error_message=str(e))
            return self._create_result(
                source_file=file_path.name,
                errors=errors,
                confidence=0.0,
            )

    def validate(self, data: EmailData) -> tuple[bool, list[str]]:
        """
        Validate extracted email data.

        Args:
            data: EmailData to validate.

        Returns:
            Tuple of (is_valid, list of validation messages).
        """
        messages: list[str] = []
        is_valid = True

        # Check email format
        if "@" not in data.sender_email:
            messages.append("Invalid sender email format")
            is_valid = False

        # Check subject
        if not data.subject or len(data.subject) < 3:
            messages.append("Email subject is missing or too short")

        # Type-specific validation
        if data.email_type == EmailType.INVOICE_NOTIFICATION:
            if not data.invoice_number:
                messages.append("Invoice notification missing invoice number")
        else:  # CLIENT_INQUIRY
            if not data.company and not data.sender_name:
                messages.append("Client inquiry missing company or sender name")

        return is_valid, messages

    def _parse_sender(self, msg: Message) -> tuple[str | None, str | None]:
        """Parse sender name and email from From header."""
        from_header = msg.get("From", "")
        name, email = parseaddr(from_header)
        return name or None, email or None

    def _get_recipient(self, msg: Message) -> str | None:
        """Get recipient email from To header."""
        to_header = msg.get("To", "")
        _, email = parseaddr(to_header)
        return email or None

    def _decode_header(self, header: str | None) -> str:
        """Decode email header to string."""
        if not header:
            return ""

        from email.header import decode_header as email_decode_header

        decoded_parts = email_decode_header(header)
        result = []
        for part, encoding in decoded_parts:
            if isinstance(part, bytes):
                result.append(part.decode(encoding or "utf-8", errors="replace"))
            else:
                result.append(part)
        return " ".join(result)

    def _parse_date(self, msg: Message) -> datetime | None:
        """Parse email date header."""
        date_str = msg.get("Date")
        if not date_str:
            return None

        try:
            return parsedate_to_datetime(date_str)
        except (ValueError, TypeError):
            return None

    def _get_body(self, msg: Message) -> str:
        """Extract email body text, preserving Greek characters."""
        if msg.is_multipart():
            for part in msg.walk():
                content_type = part.get_content_type()
                if content_type == "text/plain":
                    # Check if there's a Content-Transfer-Encoding
                    transfer_encoding = part.get("Content-Transfer-Encoding", "").lower()
                    if transfer_encoding in ("base64", "quoted-printable"):
                        payload = part.get_payload(decode=True)
                        if payload:
                            charset = part.get_content_charset() or "utf-8"
                            return payload.decode(charset, errors="replace")
                    else:
                        # Plain text without encoding - get directly
                        payload = part.get_payload(decode=False)
                        if isinstance(payload, str):
                            return payload
                        elif isinstance(payload, bytes):
                            charset = part.get_content_charset() or "utf-8"
                            return payload.decode(charset, errors="replace")
        else:
            # Check Content-Transfer-Encoding
            transfer_encoding = msg.get("Content-Transfer-Encoding", "").lower()
            if transfer_encoding in ("base64", "quoted-printable"):
                payload = msg.get_payload(decode=True)
                if payload:
                    charset = msg.get_content_charset() or "utf-8"
                    return payload.decode(charset, errors="replace")
            else:
                # Plain text - get directly to preserve Greek characters
                payload = msg.get_payload(decode=False)
                if isinstance(payload, str):
                    return payload
                elif isinstance(payload, bytes):
                    charset = msg.get_content_charset() or "utf-8"
                    return payload.decode(charset, errors="replace")

        return ""

    def _classify_email(self, subject: str, body: str) -> EmailType:
        """
        Classify email as client inquiry or invoice notification.

        Args:
            subject: Email subject.
            body: Email body text.

        Returns:
            EmailType classification.
        """
        text = (subject + " " + body).lower()

        # Count invoice-related keywords
        invoice_score = sum(1 for kw in INVOICE_KEYWORDS if kw in text)

        # Invoice notifications typically have specific patterns
        has_invoice_number = bool(re.search(r"[A-Z]{2,}-\d{4}-\d{3}", text, re.IGNORECASE))
        has_amount = bool(re.search(r"€\s*[\d,\.]+|[\d,\.]+\s*€", text))

        if invoice_score >= 2 or (has_invoice_number and has_amount):
            return EmailType.INVOICE_NOTIFICATION

        return EmailType.CLIENT_INQUIRY

    def _extract_body_data(
        self, body: str, _email_type: EmailType
    ) -> dict[str, str | Decimal | None]:
        """
        Extract structured data from email body using patterns.

        Args:
            body: Email body text.
            _email_type: Type of email (reserved for future per-type extraction).

        Returns:
            Dictionary of extracted field values.
        """
        extracted: dict[str, str | Decimal | None] = {}

        # Extract fields based on patterns
        for field, patterns in PATTERNS.items():
            for pattern in patterns:
                match = re.search(pattern, body, re.IGNORECASE | re.MULTILINE)
                if match:
                    value = match.group(1).strip()
                    # Convert amounts to Decimal
                    if field in ("net_amount", "vat_amount", "total_amount"):
                        extracted[field] = self._parse_amount(value)
                    else:
                        extracted[field] = value
                    break

        return extracted

    def _parse_amount(self, amount_str: str) -> Decimal | None:
        """Parse amount string to Decimal."""
        if not amount_str:
            return None

        # Remove currency symbols and whitespace
        cleaned = amount_str.replace("€", "").replace(" ", "").strip()

        # Handle different number formats
        if "," in cleaned and "." in cleaned:
            # Determine format by position of last separator
            last_comma = cleaned.rfind(",")
            last_dot = cleaned.rfind(".")
            if last_comma > last_dot:
                # European format: 1.234,56 -> comma is decimal
                cleaned = cleaned.replace(".", "").replace(",", ".")
            else:
                # US format: 1,234.56 -> period is decimal
                cleaned = cleaned.replace(",", "")
        elif "," in cleaned:
            # Could be European decimal (1234,56) or thousands (1,234)
            # Check if comma is followed by exactly 2-3 digits at end
            parts = cleaned.split(",")
            if len(parts) == 2 and len(parts[1]) <= 3 and len(parts[1]) >= 1:
                if len(parts[1]) == 2 or (len(parts[1]) == 3 and len(parts[0]) <= 3):
                    # Likely decimal separator
                    cleaned = cleaned.replace(",", ".")
                else:
                    # Likely thousands separator
                    cleaned = cleaned.replace(",", "")
            else:
                cleaned = cleaned.replace(",", "")

        try:
            return Decimal(cleaned)
        except Exception:
            return None

    def _extract_service_interest(self, subject: str, body: str) -> str | None:
        """Extract service interest from email content."""
        text = (subject + " " + body).lower()

        services = {
            "crm": "CRM System",
            "erp": "ERP Integration",
            "e-commerce": "E-commerce Platform",
            "ecommerce": "E-commerce Platform",
            "website": "Web Development",
            "ιστοσελίδα": "Web Development",
            "pharmacy": "Pharmacy Management",
            "φαρμακείο": "Pharmacy Management",
            "inventory": "Inventory Management",
            "αποθήκη": "Inventory Management",
            "accounting": "Accounting System",
            "λογιστικό": "Accounting System",
        }

        for keyword, service in services.items():
            if keyword in text:
                return service

        return None

    def _calculate_confidence(
        self,
        data: EmailData,
        extracted: dict[str, str | Decimal | None],
        warnings: list[str],
    ) -> float:
        """
        Calculate confidence score for email extraction.

        Args:
            data: Extracted EmailData.
            extracted: Raw extracted values.
            warnings: List of extraction warnings.

        Returns:
            Confidence score between 0.0 and 1.0.
        """
        confidence = 1.0

        # Reduce for warnings
        confidence -= len(warnings) * 0.05

        # Check extraction completeness based on type
        if data.email_type == EmailType.INVOICE_NOTIFICATION:
            if not data.invoice_number:
                confidence -= 0.15
            if not data.invoice_amount:
                confidence -= 0.1
        else:
            if not data.company:
                confidence -= 0.1
            if not data.phone:
                confidence -= 0.05

        # Boost if we found structured contact info in body
        if extracted.get("name") and extracted.get("email"):
            confidence = min(1.0, confidence + 0.05)

        return max(0.5, min(1.0, confidence))
