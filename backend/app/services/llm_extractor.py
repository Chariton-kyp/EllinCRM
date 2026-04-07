"""LLM-based document extraction using Gemini Flash via any-llm (Mozilla.ai).

Extracts structured data from forms, emails, and invoices with per-field
confidence scores. Uses ai_completion_json() for model calls with automatic
fallback chains.

The regex extractors are NOT imported here -- fallback logic lives in the
extraction router.
"""

import logging
from datetime import datetime
from decimal import Decimal, InvalidOperation
from uuid import uuid4

from app.models.schemas import (
    ContactFormData,
    EmailData,
    EmailType,
    ExtractionResult,
    InvoiceData,
    InvoiceItem,
    Priority,
    RecordType,
)
from app.services.ai_call import ai_completion_json

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# System prompts — English for model reliability, Greek-aware context
# ---------------------------------------------------------------------------

_CONFIDENCE_SUFFIX = (
    '\n\nReturn ONLY valid JSON. Include a "field_confidence" object mapping '
    "each field name to a confidence score 0.0-1.0. Set the overall "
    '"confidence" field to the average of all field confidences.'
)

FORM_SYSTEM_PROMPT = (
    "You are a data extraction AI. Extract structured data from this HTML "
    "contact form. Return JSON with field-level confidence scores. "
    "Fields: full_name, email, phone, company, service_interest, message, "
    "submission_date (ISO format), priority (low/medium/high). "
    "For each field, also return a confidence score 0-1."
    + _CONFIDENCE_SUFFIX
)

EMAIL_SYSTEM_PROMPT = (
    "You are a data extraction AI. Extract structured data from this email. "
    "Determine if it's a client_inquiry or invoice_notification. "
    "Return JSON with field-level confidence scores. "
    "Fields: email_type, sender_name, sender_email, recipient_email, subject, "
    "date_sent (ISO format), body, phone, company, position, service_interest, "
    "invoice_number, invoice_amount, vendor_name."
    + _CONFIDENCE_SUFFIX
)

INVOICE_SYSTEM_PROMPT = (
    "You are a data extraction AI. Extract structured data from this invoice "
    "(Greek business format). Return JSON with field-level confidence scores. "
    "Fields: invoice_number, invoice_date (ISO format), client_name, "
    "client_address, client_vat_number (AFM), items (array of "
    "{description, quantity, unit_price, total}), net_amount, vat_rate, "
    "vat_amount, total_amount, payment_terms, notes. "
    "All monetary values as numbers (not strings)."
    + _CONFIDENCE_SUFFIX
)


# ---------------------------------------------------------------------------
# Helper: robust date parsing
# ---------------------------------------------------------------------------

def _parse_date(value) -> datetime | None:
    """Parse a date string with multiple fallback strategies."""
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        return datetime.fromisoformat(value)
    except (ValueError, TypeError):
        pass
    try:
        from dateutil import parser as dateutil_parser
        return dateutil_parser.parse(value)
    except Exception:
        return None


def _to_decimal(value) -> Decimal | None:
    """Safely convert a value to Decimal."""
    if value is None:
        return None
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        return None


# ---------------------------------------------------------------------------
# LLMExtractor
# ---------------------------------------------------------------------------

class LLMExtractor:
    """LLM-based document extraction using Gemini Flash via any-llm (Mozilla.ai)."""

    DEFAULT_MODEL = "gemini-flash"

    async def extract_form(self, content: str, filename: str) -> ExtractionResult:
        """Extract form data using LLM."""
        raw, model_used = await self._call_llm(FORM_SYSTEM_PROMPT, content)
        result = self._parse_form_response(raw, filename)
        logger.info(
            "LLM form extraction complete",
            extra={"file": filename, "model": model_used, "confidence": result.confidence_score},
        )
        return result

    async def extract_email(self, content: str, filename: str) -> ExtractionResult:
        """Extract email data using LLM."""
        raw, model_used = await self._call_llm(EMAIL_SYSTEM_PROMPT, content)
        result = self._parse_email_response(raw, filename)
        logger.info(
            "LLM email extraction complete",
            extra={"file": filename, "model": model_used, "confidence": result.confidence_score},
        )
        return result

    async def extract_invoice(self, content: str, filename: str) -> ExtractionResult:
        """Extract invoice data using LLM."""
        raw, model_used = await self._call_llm(INVOICE_SYSTEM_PROMPT, content)
        result = self._parse_invoice_response(raw, filename)
        logger.info(
            "LLM invoice extraction complete",
            extra={"file": filename, "model": model_used, "confidence": result.confidence_score},
        )
        return result

    # ----- internal helpers -----

    async def _call_llm(self, system_prompt: str, document_content: str) -> tuple[dict, str]:
        """Call LLM via ai_completion_json."""
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": document_content},
        ]
        return await ai_completion_json(messages, model=self.DEFAULT_MODEL, timeout=45)

    def _calculate_overall_confidence(self, field_confidence: dict) -> float:
        """Average of field confidences, or fallback to raw confidence value."""
        if not field_confidence:
            return 0.5
        values = [v for v in field_confidence.values() if isinstance(v, (int, float))]
        if not values:
            return 0.5
        return round(sum(values) / len(values), 4)

    @staticmethod
    def _extract_data_and_meta(raw: dict) -> tuple[dict, dict, float | None]:
        """Extract data dict, field_confidence dict, and raw confidence from LLM response.

        Handles both wrapped ({"data": {...}, "field_confidence": {...}})
        and flat (all fields at top level) response formats.
        """
        meta_keys = {"data", "confidence", "field_confidence"}

        if "data" in raw and isinstance(raw["data"], dict):
            data = raw["data"]
        else:
            # Flat structure: treat all non-meta keys as data
            data = {k: v for k, v in raw.items() if k not in meta_keys}

        field_confidence = raw.get("field_confidence", {})
        raw_confidence = raw.get("confidence")
        return data, field_confidence, raw_confidence

    # ----- response parsers -----

    def _parse_form_response(self, raw: dict, filename: str) -> ExtractionResult:
        """Parse LLM JSON into ExtractionResult with ContactFormData."""
        data, field_confidence, raw_conf = self._extract_data_and_meta(raw)
        warnings: list[str] = []
        errors: list[str] = []

        # Parse date
        submission_date = _parse_date(data.get("submission_date"))

        # Parse priority
        priority_str = str(data.get("priority", "medium")).lower()
        try:
            priority = Priority(priority_str)
        except ValueError:
            priority = Priority.MEDIUM
            warnings.append(f"Unknown priority '{priority_str}', defaulting to medium")

        try:
            form_data = ContactFormData(
                full_name=data.get("full_name", ""),
                email=data.get("email", ""),
                phone=data.get("phone"),
                company=data.get("company"),
                service_interest=data.get("service_interest"),
                message=data.get("message"),
                submission_date=submission_date,
                priority=priority,
            )
        except Exception as exc:
            errors.append(f"Pydantic validation failed: {exc}")
            logger.warning("Form Pydantic validation failed: %s", exc)
            return ExtractionResult(
                id=uuid4(),
                source_file=filename,
                record_type=RecordType.FORM,
                confidence_score=0.3,
                warnings=warnings,
                errors=errors,
            )

        confidence = self._calculate_overall_confidence(field_confidence)
        if raw_conf is not None and not field_confidence:
            confidence = float(raw_conf)

        return ExtractionResult(
            id=uuid4(),
            source_file=filename,
            record_type=RecordType.FORM,
            confidence_score=min(max(confidence, 0.0), 1.0),
            warnings=warnings,
            errors=errors,
            form_data=form_data,
        )

    def _parse_email_response(self, raw: dict, filename: str) -> ExtractionResult:
        """Parse LLM JSON into ExtractionResult with EmailData."""
        data, field_confidence, raw_conf = self._extract_data_and_meta(raw)
        warnings: list[str] = []
        errors: list[str] = []

        # Parse email_type
        email_type_str = str(data.get("email_type", "client_inquiry")).lower()
        try:
            email_type = EmailType(email_type_str)
        except ValueError:
            email_type = EmailType.CLIENT_INQUIRY
            warnings.append(f"Unknown email_type '{email_type_str}', defaulting to client_inquiry")

        # Parse date
        date_sent = _parse_date(data.get("date_sent"))
        if date_sent is None:
            date_sent = datetime.utcnow()
            warnings.append("Could not parse date_sent, using current time")

        # Parse invoice_amount
        invoice_amount = _to_decimal(data.get("invoice_amount"))

        try:
            email_data = EmailData(
                email_type=email_type,
                sender_name=data.get("sender_name"),
                sender_email=data.get("sender_email", ""),
                recipient_email=data.get("recipient_email", ""),
                subject=data.get("subject", ""),
                date_sent=date_sent,
                body=data.get("body", ""),
                phone=data.get("phone"),
                company=data.get("company"),
                position=data.get("position"),
                service_interest=data.get("service_interest"),
                invoice_number=data.get("invoice_number"),
                invoice_amount=invoice_amount,
                vendor_name=data.get("vendor_name"),
            )
        except Exception as exc:
            errors.append(f"Pydantic validation failed: {exc}")
            logger.warning("Email Pydantic validation failed: %s", exc)
            return ExtractionResult(
                id=uuid4(),
                source_file=filename,
                record_type=RecordType.EMAIL,
                confidence_score=0.3,
                warnings=warnings,
                errors=errors,
            )

        confidence = self._calculate_overall_confidence(field_confidence)
        if raw_conf is not None and not field_confidence:
            confidence = float(raw_conf)

        return ExtractionResult(
            id=uuid4(),
            source_file=filename,
            record_type=RecordType.EMAIL,
            confidence_score=min(max(confidence, 0.0), 1.0),
            warnings=warnings,
            errors=errors,
            email_data=email_data,
        )

    def _parse_invoice_response(self, raw: dict, filename: str) -> ExtractionResult:
        """Parse LLM JSON into ExtractionResult with InvoiceData."""
        data, field_confidence, raw_conf = self._extract_data_and_meta(raw)
        warnings: list[str] = []
        errors: list[str] = []

        # Parse date
        invoice_date = _parse_date(data.get("invoice_date"))
        if invoice_date is None:
            invoice_date = datetime.utcnow()
            warnings.append("Could not parse invoice_date, using current time")

        # Parse items
        raw_items = data.get("items", [])
        items: list[InvoiceItem] = []
        for idx, item in enumerate(raw_items):
            try:
                items.append(
                    InvoiceItem(
                        description=item.get("description", ""),
                        quantity=int(item.get("quantity", 0)),
                        unit_price=Decimal(str(item.get("unit_price", 0))),
                        total=Decimal(str(item.get("total", 0))),
                    )
                )
            except Exception as exc:
                warnings.append(f"Could not parse invoice item {idx}: {exc}")

        # Parse monetary values
        net_amount = _to_decimal(data.get("net_amount")) or Decimal("0")
        vat_rate = _to_decimal(data.get("vat_rate")) or Decimal("24")
        vat_amount = _to_decimal(data.get("vat_amount")) or Decimal("0")
        total_amount = _to_decimal(data.get("total_amount")) or Decimal("0")

        try:
            invoice_data = InvoiceData(
                invoice_number=data.get("invoice_number", ""),
                invoice_date=invoice_date,
                client_name=data.get("client_name", ""),
                client_address=data.get("client_address"),
                client_vat_number=data.get("client_vat_number"),
                items=items,
                net_amount=net_amount,
                vat_rate=vat_rate,
                vat_amount=vat_amount,
                total_amount=total_amount,
                payment_terms=data.get("payment_terms"),
                notes=data.get("notes"),
            )
        except Exception as exc:
            errors.append(f"Pydantic validation failed: {exc}")
            logger.warning("Invoice Pydantic validation failed: %s", exc)
            return ExtractionResult(
                id=uuid4(),
                source_file=filename,
                record_type=RecordType.INVOICE,
                confidence_score=0.3,
                warnings=warnings,
                errors=errors,
            )

        confidence = self._calculate_overall_confidence(field_confidence)
        if raw_conf is not None and not field_confidence:
            confidence = float(raw_conf)

        return ExtractionResult(
            id=uuid4(),
            source_file=filename,
            record_type=RecordType.INVOICE,
            confidence_score=min(max(confidence, 0.0), 1.0),
            warnings=warnings,
            errors=errors,
            invoice_data=invoice_data,
        )
