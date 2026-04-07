"""
PDF Invoice Extractor.
Uses pdfplumber for reliable PDF parsing.
Extracts invoice details, line items, and totals from PDF invoices.
"""

import re
from datetime import datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

from app.core.logging import get_logger
from app.extractors.base import BaseExtractor
from app.models.schemas import (
    ExtractionResult,
    InvoiceData,
    InvoiceItem,
    RecordType,
)

logger = get_logger(__name__)

# Try to import pdfplumber, handle if not installed
try:
    import pdfplumber
    PDF_SUPPORT = True
except ImportError:
    pdfplumber = None  # type: ignore
    PDF_SUPPORT = False
    logger.warning("pdfplumber not installed, PDF extraction disabled")


class PDFInvoiceExtractor(BaseExtractor[InvoiceData]):
    """
    Extractor for PDF invoices.

    Parses PDF invoice files and extracts:
    - Invoice number, date, payment terms
    - Client information (name, address, VAT number)
    - Line items (description, quantity, unit price, total)
    - Financial totals (net, VAT, total)
    
    Uses pdfplumber for text extraction and table detection.
    """

    record_type = RecordType.INVOICE

    def __init__(self) -> None:
        """Initialize PDF extractor."""
        super().__init__()
        if not PDF_SUPPORT:
            logger.warning(
                "PDFInvoiceExtractor initialized but pdfplumber is not installed. "
                "Install with: pip install pdfplumber"
            )

    @staticmethod
    def is_supported() -> bool:
        """Check if PDF extraction is supported."""
        return PDF_SUPPORT

    def can_extract(self, file_path: Path) -> bool:
        """Check if this extractor can handle the file."""
        return file_path.suffix.lower() == ".pdf" and PDF_SUPPORT

    def extract(self, file_path: Path) -> ExtractionResult:
        """
        Extract data from a PDF invoice file.

        Args:
            file_path: Path to the PDF invoice file.

        Returns:
            ExtractionResult with InvoiceData.
        """
        extraction_id = str(file_path.name)
        warnings: list[str] = []
        errors: list[str] = []

        if not PDF_SUPPORT:
            errors.append("PDF extraction not supported - pdfplumber not installed")
            return self._create_result(
                source_file=file_path.name,
                errors=errors,
                confidence=0.0,
            )

        try:
            # Open and extract text from PDF
            with pdfplumber.open(file_path) as pdf:
                # Extract text from all pages
                full_text = ""
                tables: list[list[list[str]]] = []
                
                for page in pdf.pages:
                    page_text = page.extract_text() or ""
                    full_text += page_text + "\n"
                    
                    # Extract tables from page
                    page_tables = page.extract_tables()
                    if page_tables:
                        tables.extend(page_tables)

            if not full_text.strip():
                errors.append("Could not extract text from PDF")
                return self._create_result(
                    source_file=file_path.name,
                    errors=errors,
                    confidence=0.0,
                )

            # Extract invoice metadata
            invoice_number = self._extract_invoice_number(full_text, file_path.name)
            if not invoice_number:
                errors.append("Could not extract invoice number")

            invoice_date = self._extract_date(full_text)
            if not invoice_date:
                warnings.append("Could not parse invoice date, using current time")
                invoice_date = datetime.utcnow()

            # Extract client info
            client_info = self._extract_client_info(full_text)
            if not client_info.get("name"):
                errors.append("Could not extract client name")

            # Extract line items from tables
            items = self._extract_line_items_from_tables(tables)
            if not items:
                # Try to extract from text
                items = self._extract_line_items_from_text(full_text)
            if not items:
                warnings.append("No line items found in invoice")

            # Extract totals
            totals = self._extract_totals(full_text)
            if not totals.get("net_amount"):
                if items:
                    calculated_net = sum(item.total for item in items)
                    totals["net_amount"] = calculated_net
                    warnings.append("Net amount calculated from line items")
                else:
                    errors.append("Could not extract invoice amounts")

            # Extract payment terms
            payment_terms = self._extract_payment_terms(full_text)

            # Extract notes
            notes = self._extract_notes(full_text)

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

            # Calculate VAT if not found
            vat_rate = totals.get("vat_rate", Decimal("24"))
            vat_amount = totals.get("vat_amount")
            net_amount = totals["net_amount"]

            if not vat_amount and net_amount:
                vat_amount = net_amount * vat_rate / Decimal("100")
                warnings.append("VAT amount calculated from net amount")

            total_amount = totals.get("total_amount")
            if not total_amount and net_amount and vat_amount:
                total_amount = net_amount + vat_amount
                warnings.append("Total amount calculated from net + VAT")

            # Create InvoiceData
            invoice_data = InvoiceData(
                invoice_number=invoice_number or f"UNKNOWN-{file_path.stem}",
                invoice_date=invoice_date,
                client_name=client_info.get("name", "Unknown Client"),
                client_address=client_info.get("address"),
                client_vat_number=client_info.get("vat_number"),
                items=items,
                net_amount=net_amount or Decimal("0"),
                vat_rate=vat_rate,
                vat_amount=vat_amount or Decimal("0"),
                total_amount=total_amount or Decimal("0"),
                payment_terms=payment_terms,
                notes=notes,
            )

            # Validate
            is_valid, validation_messages = self.validate(invoice_data)
            if not is_valid:
                warnings.extend(validation_messages)

            # Calculate confidence
            confidence = self._calculate_confidence(invoice_data, warnings)

            self.logger.info(
                "pdf_invoice_extraction_success",
                file=str(file_path),
                invoice_number=invoice_data.invoice_number,
                total=str(invoice_data.total_amount),
                confidence=confidence,
            )

            self._log_extraction(file_path, extraction_id, True, confidence)

            return self._create_result(
                source_file=file_path.name,
                data=invoice_data,
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
            self.logger.error("pdf_invoice_extraction_error", file=str(file_path), error=str(e))
            errors.append(f"PDF extraction error: {str(e)}")
            self._log_extraction(file_path, extraction_id, False, error_message=str(e))
            return self._create_result(
                source_file=file_path.name,
                errors=errors,
                confidence=0.0,
            )

    def validate(self, data: InvoiceData) -> tuple[bool, list[str]]:
        """
        Validate extracted invoice data.

        Args:
            data: InvoiceData to validate.

        Returns:
            Tuple of (is_valid, list of validation messages).
        """
        messages: list[str] = []
        is_valid = True

        # Check invoice number format (flexible for PDF)
        if not re.match(r"^[A-Z]{2,3}-\d{4}-\d{3}$", data.invoice_number):
            if not data.invoice_number.startswith("UNKNOWN"):
                messages.append("Invoice number format not recognized")

        # Verify VAT calculation (24% standard Greek VAT)
        expected_vat = data.net_amount * Decimal("24") / Decimal("100")
        if abs(data.vat_amount - expected_vat) > Decimal("1"):
            messages.append(
                f"VAT amount ({data.vat_amount}) doesn't match expected 24% ({expected_vat})"
            )

        # Verify total
        expected_total = data.net_amount + data.vat_amount
        if abs(data.total_amount - expected_total) > Decimal("1"):
            messages.append(
                f"Total ({data.total_amount}) doesn't match net + VAT ({expected_total})"
            )

        return is_valid, messages

    def _extract_invoice_number(self, text: str, filename: str) -> str | None:
        """Extract invoice number from PDF text."""
        patterns = [
            r"Αριθμός:\s*([A-Z]{2,3}-\d{4}-\d{3})",
            r"Invoice\s*#?\s*:?\s*([A-Z]{2,3}-\d{4}-\d{3})",
            r"Αρ\.\s*Τιμολογίου:\s*([A-Z0-9-]+)",
            r"([A-Z]{2,3}-\d{4}-\d{3})",
        ]

        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return match.group(1)

        # Try from filename
        if "-" in filename:
            match = re.search(r"([A-Z]{2,3}-\d{4}-\d{3})", filename.upper())
            if match:
                return match.group(1)

        return None

    def _extract_date(self, text: str) -> datetime | None:
        """Extract invoice date from PDF text."""
        patterns = [
            r"Ημερομηνία:\s*(\d{1,2}/\d{1,2}/\d{4})",
            r"Date:\s*(\d{1,2}/\d{1,2}/\d{4})",
            r"Ημ/νία:\s*(\d{1,2}/\d{1,2}/\d{4})",
            r"(\d{1,2}/\d{1,2}/\d{4})",
        ]

        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                date_str = match.group(1)
                try:
                    return datetime.strptime(date_str, "%d/%m/%Y")
                except ValueError:
                    continue

        return None

    def _extract_client_info(self, text: str) -> dict[str, str | None]:
        """Extract client information from PDF text."""
        info: dict[str, str | None] = {
            "name": None,
            "address": None,
            "vat_number": None,
        }

        # Client name
        client_patterns = [
            r"Πελάτης:\s*(.+?)(?:\n|ΑΦΜ|Διεύθυνση)",
            r"Προς:\s*(.+?)(?:\n|ΑΦΜ)",
            r"Bill To:\s*(.+?)(?:\n|VAT)",
        ]
        for pattern in client_patterns:
            match = re.search(pattern, text, re.IGNORECASE | re.DOTALL)
            if match:
                info["name"] = match.group(1).strip().split("\n")[0].strip()
                break

        # VAT number
        vat_match = re.search(r"ΑΦΜ:\s*(\d{9})", text)
        if vat_match:
            all_vat = re.findall(r"ΑΦΜ:\s*(\d{9})", text)
            if len(all_vat) > 1:
                info["vat_number"] = all_vat[1]  # Client VAT is usually second
            elif all_vat:
                info["vat_number"] = all_vat[0]

        # Address
        addr_patterns = [
            r"Διεύθυνση:\s*([^\n]+)",
            r"((?:Οδός|Λεωφ\.|Βας\.)[^,\n]+,?\s*\d{5}\s*\w+)",
        ]
        for pattern in addr_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                info["address"] = match.group(1).strip()
                break

        return info

    def _extract_line_items_from_tables(
        self, tables: list[list[list[Any]]]
    ) -> list[InvoiceItem]:
        """Extract line items from PDF tables."""
        items: list[InvoiceItem] = []

        for table in tables:
            if not table or len(table) < 2:
                continue

            # Check if this looks like an invoice items table
            header = table[0] if table else []
            header_text = " ".join(str(h or "") for h in header).lower()
            
            if not any(x in header_text for x in ["περιγραφή", "description", "ποσότητα", "quantity"]):
                continue

            # Process rows (skip header)
            for row in table[1:]:
                if len(row) >= 4:
                    try:
                        description = str(row[0] or "").strip()
                        quantity = int(float(str(row[1] or "0").replace(",", ".")))
                        unit_price = self._parse_amount(str(row[2] or "0"))
                        total = self._parse_amount(str(row[3] or "0"))

                        if description and unit_price and total:
                            items.append(
                                InvoiceItem(
                                    description=description,
                                    quantity=quantity or 1,
                                    unit_price=unit_price,
                                    total=total,
                                )
                            )
                    except (ValueError, TypeError, InvalidOperation):
                        continue

        return items

    def _extract_line_items_from_text(self, text: str) -> list[InvoiceItem]:
        """Try to extract line items from plain text (fallback)."""
        items: list[InvoiceItem] = []
        
        # Pattern for line items in text format
        # e.g., "Service Description    1    €500.00    €500.00"
        pattern = r"([A-Za-zΑ-Ωα-ω\s]+)\s+(\d+)\s+€?([\d,.]+)\s+€?([\d,.]+)"
        
        for match in re.finditer(pattern, text):
            try:
                description = match.group(1).strip()
                quantity = int(match.group(2))
                unit_price = self._parse_amount(match.group(3))
                total = self._parse_amount(match.group(4))
                
                if description and len(description) > 3 and unit_price and total:
                    items.append(
                        InvoiceItem(
                            description=description,
                            quantity=quantity,
                            unit_price=unit_price,
                            total=total,
                        )
                    )
            except (ValueError, InvalidOperation):
                continue
        
        return items

    def _extract_totals(self, text: str) -> dict[str, Decimal | None]:
        """Extract financial totals from PDF text."""
        totals: dict[str, Decimal | None] = {
            "net_amount": None,
            "vat_rate": Decimal("24"),
            "vat_amount": None,
            "total_amount": None,
        }

        # Net amount
        net_patterns = [
            r"Καθαρή Αξία:?\s*€?([\d,\.]+)",
            r"Net Amount:?\s*€?([\d,\.]+)",
            r"Σύνολο:?\s*€?([\d,\.]+)(?:\s*ΦΠΑ)",
            r"Υποσύνολο:?\s*€?([\d,\.]+)",
        ]
        for pattern in net_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                totals["net_amount"] = self._parse_amount(match.group(1))
                break

        # VAT
        vat_patterns = [
            r"ΦΠΑ\s*(\d+)%:?\s*€?([\d,\.]+)",
            r"VAT\s*(\d+)%:?\s*€?([\d,\.]+)",
        ]
        for pattern in vat_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                totals["vat_rate"] = Decimal(match.group(1))
                totals["vat_amount"] = self._parse_amount(match.group(2))
                break

        # Total
        total_patterns = [
            r"ΣΥΝΟΛΟ:?\s*€?([\d,\.]+)",
            r"Total:?\s*€?([\d,\.]+)",
            r"Πληρωτέο:?\s*€?([\d,\.]+)",
            r"ΠΛΗΡΩΤΕΟ:?\s*€?([\d,\.]+)",
        ]
        for pattern in total_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                totals["total_amount"] = self._parse_amount(match.group(1))
                break

        return totals

    def _extract_payment_terms(self, text: str) -> str | None:
        """Extract payment terms from PDF text."""
        patterns = [
            r"Τρόπος Πληρωμής:?\s*(.+?)(?:\n|$)",
            r"Payment Terms?:?\s*(.+?)(?:\n|$)",
            r"Πληρωμή:?\s*(.+?)(?:\n|$)",
        ]

        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return match.group(1).strip()

        return None

    def _extract_notes(self, text: str) -> str | None:
        """Extract notes from PDF text."""
        patterns = [
            r"Σημειώσεις:?\s*(.+?)(?:\n\n|$)",
            r"Notes:?\s*(.+?)(?:\n\n|$)",
            r"Παρατηρήσεις:?\s*(.+?)(?:\n\n|$)",
        ]

        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE | re.DOTALL)
            if match:
                return match.group(1).strip()[:500]  # Limit to 500 chars

        return None

    def _parse_amount(self, amount_str: str | None) -> Decimal | None:
        """Parse amount string to Decimal."""
        if not amount_str:
            return None

        # Remove currency symbols and whitespace
        cleaned = amount_str.replace("€", "").replace(" ", "").strip()

        # Handle different number formats
        if "," in cleaned and "." in cleaned:
            last_comma = cleaned.rfind(",")
            last_dot = cleaned.rfind(".")
            if last_comma > last_dot:
                # European format: 1.234,56
                cleaned = cleaned.replace(".", "").replace(",", ".")
            else:
                # US format: 1,234.56
                cleaned = cleaned.replace(",", "")
        elif "," in cleaned:
            parts = cleaned.split(",")
            if len(parts) == 2 and len(parts[1]) <= 2:
                # Decimal separator
                cleaned = cleaned.replace(",", ".")
            else:
                # Thousands separator
                cleaned = cleaned.replace(",", "")

        try:
            return Decimal(cleaned)
        except InvalidOperation:
            return None

    def _calculate_confidence(
        self, data: InvoiceData, warnings: list[str]
    ) -> float:
        """Calculate confidence score for PDF invoice extraction."""
        confidence = 0.9  # Start lower than HTML (PDF is less reliable)

        # Reduce for warnings
        confidence -= len(warnings) * 0.05

        # Check for complete data
        if not data.items:
            confidence -= 0.15
        if not data.client_address:
            confidence -= 0.05
        if not data.client_vat_number:
            confidence -= 0.05
        if not data.payment_terms:
            confidence -= 0.02

        # Verify amounts match
        if data.items:
            items_total = sum(item.total for item in data.items)
            if abs(items_total - data.net_amount) < Decimal("0.01"):
                confidence = min(1.0, confidence + 0.1)

        return max(0.4, min(1.0, confidence))
