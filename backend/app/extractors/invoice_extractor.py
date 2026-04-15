"""
Invoice Extractor for HTML invoices.
Uses BeautifulSoup for reliable HTML parsing.
Extracts invoice details, line items, and totals.
"""

import re
from datetime import datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path

from bs4 import BeautifulSoup, Tag

from app.core.logging import get_logger
from app.extractors.base import BaseExtractor
from app.models.schemas import (
    ExtractionResult,
    InvoiceData,
    InvoiceItem,
    RecordType,
)

logger = get_logger(__name__)


class InvoiceExtractor(BaseExtractor[InvoiceData]):
    """
    Extractor for HTML invoices.

    Parses HTML invoice files and extracts:
    - Invoice number, date, payment terms
    - Client information (name, address, VAT number)
    - Line items (description, quantity, unit price, total)
    - Financial totals (net, VAT, total)
    """

    record_type = RecordType.INVOICE

    def extract(self, file_path: Path) -> ExtractionResult:
        """
        Extract data from an HTML invoice file.

        Args:
            file_path: Path to the HTML invoice file.

        Returns:
            ExtractionResult with InvoiceData.
        """
        extraction_id = str(file_path.name)
        warnings: list[str] = []
        errors: list[str] = []

        try:
            # Read and parse HTML
            html_content = self.read_file(file_path)
            soup = BeautifulSoup(html_content, "html.parser")

            # Extract invoice metadata
            invoice_number = self._extract_invoice_number(soup, file_path.name)
            if not invoice_number:
                errors.append("Could not extract invoice number")

            invoice_date = self._extract_date(soup)
            if not invoice_date:
                warnings.append("Could not parse invoice date, using current time")
                invoice_date = datetime.utcnow()

            # Extract client info
            client_info = self._extract_client_info(soup)
            if not client_info.get("name"):
                errors.append("Could not extract client name")

            # Extract line items
            items = self._extract_line_items(soup)
            if not items:
                warnings.append("No line items found in invoice")

            # Extract totals
            totals = self._extract_totals(soup)
            if not totals.get("net_amount"):
                # Try to calculate from items
                if items:
                    calculated_net = sum(item.total for item in items)
                    totals["net_amount"] = calculated_net
                    warnings.append("Net amount calculated from line items")
                else:
                    errors.append("Could not extract invoice amounts")

            # Extract payment terms
            payment_terms = self._extract_payment_terms(soup)

            # Extract notes
            notes = self._extract_notes(soup)

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
                "invoice_extraction_success",
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
            self.logger.error("invoice_extraction_error", file=str(file_path), error=str(e))
            errors.append(f"Extraction error: {str(e)}")
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

        # Check invoice number format
        if not re.match(r"^TF-\d{4}-\d{3}$", data.invoice_number):
            messages.append("Invoice number doesn't match expected format TF-YYYY-NNN")

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

        # Check items total matches net amount
        if data.items:
            items_total = sum(item.total for item in data.items)
            if abs(items_total - data.net_amount) > Decimal("1"):
                messages.append(
                    f"Sum of items ({items_total}) doesn't match net amount ({data.net_amount})"
                )

        return is_valid, messages

    def _extract_invoice_number(
        self, soup: BeautifulSoup, filename: str
    ) -> str | None:
        """Extract invoice number from HTML."""
        # Try to find in text content
        text = soup.get_text()

        # Pattern for invoice numbers — supports any 2+ letter prefix
        # (TF- legacy, EC- current EllinCRM, easily extensible).
        invoice_num_regex = r"[A-Z]{2,}-\d{4}-\d{3}"
        patterns = [
            rf"Αριθμός:\s*({invoice_num_regex})",
            rf"Τιμολόγιο\s+({invoice_num_regex})",
            rf"Invoice #?:?\s*({invoice_num_regex})",
            rf"({invoice_num_regex})",
        ]

        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return match.group(1)

        # Fallback: extract from filename
        match = re.search(rf"({invoice_num_regex})", filename)
        if match:
            return match.group(1)

        return None

    def _extract_date(self, soup: BeautifulSoup) -> datetime | None:
        """Extract invoice date from HTML."""
        text = soup.get_text()

        # Patterns for date extraction
        patterns = [
            r"Ημερομηνία:\s*(\d{1,2}/\d{1,2}/\d{4})",
            r"Date:\s*(\d{1,2}/\d{1,2}/\d{4})",
            r"(\d{1,2}/\d{1,2}/\d{4})",
        ]

        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                date_str = match.group(1)
                try:
                    # Greek format: DD/MM/YYYY
                    return datetime.strptime(date_str, "%d/%m/%Y")
                except ValueError:
                    continue

        return None

    def _extract_client_info(self, soup: BeautifulSoup) -> dict[str, str | None]:
        """Extract client information from HTML."""
        info: dict[str, str | None] = {
            "name": None,
            "address": None,
            "vat_number": None,
        }

        text = soup.get_text()

        # Find client name after "Πελάτης:" label
        client_match = re.search(
            r"Πελάτης:\s*(?:\n)?(.+?)(?:\n|Βας\.|Λεωφ\.|$)", text, re.IGNORECASE
        )
        if client_match:
            info["name"] = client_match.group(1).strip()

        # If not found, look for company name patterns
        if not info["name"]:
            # Look for text after "Πελάτης" in a div
            client_div = soup.find(string=re.compile(r"Πελάτης", re.IGNORECASE))
            if client_div:
                parent = client_div.parent
                if parent:
                    # Get the next few lines
                    next_text = parent.get_text()
                    lines = [l.strip() for l in next_text.split("\n") if l.strip()]
                    for line in lines[1:3]:  # Check next 2 lines
                        if line and not line.startswith(("ΑΦΜ", "Βας.", "Λεωφ.")):
                            info["name"] = line
                            break

        # Extract VAT number (ΑΦΜ)
        vat_match = re.search(r"ΑΦΜ:\s*(\d{9})", text)
        if vat_match:
            # Second occurrence is typically client VAT
            all_vat = re.findall(r"ΑΦΜ:\s*(\d{9})", text)
            if len(all_vat) > 1:
                info["vat_number"] = all_vat[1]
            elif all_vat:
                info["vat_number"] = all_vat[0]

        # Extract address
        addr_patterns = [
            r"((?:Βας\.|Λεωφ\.|Πλ\.)[^\n\d]*\d+[^\n]*)",
            r"(\d{5}\s+\w+)",  # Postal code and city
        ]
        for pattern in addr_patterns:
            addr_match = re.search(pattern, text)
            if addr_match:
                info["address"] = addr_match.group(1).strip()
                break

        return info

    def _extract_line_items(self, soup: BeautifulSoup) -> list[InvoiceItem]:
        """Extract line items from invoice table."""
        items: list[InvoiceItem] = []

        # Find the invoice table
        table = soup.find("table", class_="invoice-table")
        if not table:
            # Try to find any table with item-like structure
            tables = soup.find_all("table")
            for t in tables:
                if t.find("th", string=re.compile(r"Περιγραφή|Description", re.I)):
                    table = t
                    break

        if not table or not isinstance(table, Tag):
            return items

        # Find tbody rows
        tbody = table.find("tbody")
        if tbody and isinstance(tbody, Tag):
            rows = tbody.find_all("tr")
        else:
            rows = table.find_all("tr")[1:]  # Skip header row

        for row in rows:
            if not isinstance(row, Tag):
                continue

            cells = row.find_all("td")
            if len(cells) >= 4:
                try:
                    description = cells[0].get_text().strip()
                    quantity = int(cells[1].get_text().strip())
                    unit_price = self._parse_amount(cells[2].get_text())
                    total = self._parse_amount(cells[3].get_text())

                    if description and unit_price is not None and total is not None:
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

    def _extract_totals(self, soup: BeautifulSoup) -> dict[str, Decimal | None]:
        """Extract financial totals from invoice."""
        totals: dict[str, Decimal | None] = {
            "net_amount": None,
            "vat_rate": Decimal("24"),
            "vat_amount": None,
            "total_amount": None,
        }

        text = soup.get_text()

        # Extract net amount
        net_patterns = [
            r"Καθαρή Αξία:\s*€?([\d,\.]+)",
            r"Net Amount:\s*€?([\d,\.]+)",
            r"Subtotal:\s*€?([\d,\.]+)",
        ]
        for pattern in net_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                totals["net_amount"] = self._parse_amount(match.group(1))
                break

        # Extract VAT
        vat_patterns = [
            r"ΦΠΑ\s*(\d+)%:\s*€?([\d,\.]+)",
            r"VAT\s*(\d+)%:\s*€?([\d,\.]+)",
        ]
        for pattern in vat_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                totals["vat_rate"] = Decimal(match.group(1))
                totals["vat_amount"] = self._parse_amount(match.group(2))
                break

        # Extract total
        total_patterns = [
            r"ΣΥΝΟΛΟ:\s*€?([\d,\.]+)",
            r"Total:\s*€?([\d,\.]+)",
            r"Σύνολο Πληρωτέο:\s*€?([\d,\.]+)",
        ]
        for pattern in total_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                totals["total_amount"] = self._parse_amount(match.group(1))
                break

        return totals

    def _extract_payment_terms(self, soup: BeautifulSoup) -> str | None:
        """Extract payment terms from invoice."""
        text = soup.get_text()

        patterns = [
            r"Τρόπος Πληρωμής:\s*(.+?)(?:\n|$)",
            r"Payment Terms?:\s*(.+?)(?:\n|$)",
            r"Πληρωμή:\s*(.+?)(?:\n|$)",
        ]

        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return match.group(1).strip()

        return None

    def _extract_notes(self, soup: BeautifulSoup) -> str | None:
        """Extract notes from invoice."""
        text = soup.get_text()

        patterns = [
            r"Σημειώσεις:\s*(.+?)(?:\n\n|$)",
            r"Notes:\s*(.+?)(?:\n\n|$)",
        ]

        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE | re.DOTALL)
            if match:
                return match.group(1).strip()

        return None

    def _parse_amount(self, amount_str: str | None) -> Decimal | None:
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
        except InvalidOperation:
            return None

    def _calculate_confidence(
        self, data: InvoiceData, warnings: list[str]
    ) -> float:
        """
        Calculate confidence score for invoice extraction.

        Args:
            data: Extracted InvoiceData.
            warnings: List of extraction warnings.

        Returns:
            Confidence score between 0.0 and 1.0.
        """
        confidence = 1.0

        # Reduce for warnings
        confidence -= len(warnings) * 0.05

        # Check for complete data
        if not data.items:
            confidence -= 0.1
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
                confidence = min(1.0, confidence + 0.05)

        return max(0.5, min(1.0, confidence))
