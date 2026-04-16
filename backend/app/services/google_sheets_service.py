"""
Google Sheets integration service for syncing extraction records.

This service provides live synchronization of extraction records to Google Sheets,
fulfilling the requirement for centralized data management with auto-update capability.

Features:
- Multi-sheet organization (Summary, Forms, Emails, Invoices)
- Auto-sync on record approve/reject/edit
- Real-time single record updates
- Professional formatting with status colors
"""

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from fastapi import HTTPException
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from app.core.config import settings
from app.core.logging import audit_logger, get_logger
from app.db.models import ExtractionRecordDB
from app.db.repositories import RecordRepository

logger = get_logger(__name__)

# Google Sheets API scopes
# NOTE: Both scopes are required:
# - spreadsheets: For reading/writing spreadsheet data
# - drive: For creating new spreadsheets (creates file in Drive)
SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

# Sheet names for multi-sheet organization
SHEET_NAMES = {
    "summary": "Summary",
    "all": "All Records",
    "forms": "Forms",
    "emails": "Emails",
    "invoices": "Invoices",
}

# Column headers for All Records sheet
HEADERS_ALL = [
    "ID",
    "Type",
    "Source",
    "Date",
    "Status",
    "Confidence",
    "Client_Name",
    "Email",
    "Phone",
    "Company",
    "Service_Interest",
    "Amount",
    "VAT",
    "Total_Amount",
    "Invoice_Number",
    "Priority",
    "Message",
    "Reviewed_By",
    "Reviewed_At",
    "Last_Updated",
]

# Type-specific headers
HEADERS_FORMS = [
    "ID",
    "Source",
    "Date",
    "Status",
    "Confidence",
    "Client_Name",
    "Email",
    "Phone",
    "Company",
    "Service_Interest",
    "Priority",
    "Message",
    "Reviewed_By",
    "Reviewed_At",
]

HEADERS_EMAILS = [
    "ID",
    "Source",
    "Date",
    "Status",
    "Confidence",
    "Sender_Name",
    "Sender_Email",
    "Phone",
    "Company",
    "Service_Interest",
    "Email_Type",
    "Invoice_Number",
    "Amount",
    "Subject",
    "Reviewed_By",
    "Reviewed_At",
]

HEADERS_INVOICES = [
    "ID",
    "Source",
    "Date",
    "Status",
    "Confidence",
    "Invoice_Number",
    "Client_Name",
    "Net_Amount",
    "VAT_Amount",
    "Total_Amount",
    "Payment_Terms",
    "Notes",
    "Reviewed_By",
    "Reviewed_At",
]

# Legacy single-sheet headers (for backward compatibility)
HEADERS = HEADERS_ALL


class GoogleSheetsService:
    """
    Service for syncing extraction records to Google Sheets.

    Provides:
    - Create new spreadsheet for data
    - Sync all records to spreadsheet
    - Update existing records
    - Real-time sync capability
    """

    def __init__(self, repository: RecordRepository):
        """
        Initialize service with repository.

        Args:
            repository: RecordRepository for data access.
        """
        self.repository = repository
        self._service = None
        self._credentials = None

    def _get_credentials(self) -> Credentials | None:
        """
        Get Google API credentials from service account file.

        Returns:
            Credentials object or None if not configured.
        """
        if self._credentials:
            return self._credentials

        credentials_path = settings.google_credentials_path
        if not credentials_path or not Path(credentials_path).exists():
            logger.warning(
                "google_credentials_not_found",
                path=str(credentials_path),
            )
            return None

        try:
            self._credentials = Credentials.from_service_account_file(
                credentials_path,
                scopes=SCOPES,
            )
            return self._credentials
        except Exception as e:
            logger.error(
                "google_credentials_error",
                error=str(e),
            )
            return None

    def _get_service(self):
        """
        Get or create Google Sheets API service.

        Returns:
            Google Sheets API service object.

        Raises:
            ValueError: If credentials not configured.
        """
        if self._service:
            return self._service

        credentials = self._get_credentials()
        if not credentials:
            raise ValueError(
                "Google Sheets credentials not configured. "
                "Please set GOOGLE_CREDENTIALS_PATH environment variable."
            )

        self._service = build("sheets", "v4", credentials=credentials)
        return self._service

    def is_configured(self) -> bool:
        """
        Check if Google Sheets integration is configured.

        Returns:
            True if credentials are available.
        """
        return self._get_credentials() is not None

    async def create_spreadsheet(
        self,
        title: str | None = None,
        multi_sheet: bool | None = None,
    ) -> dict[str, str]:
        """
        Create a new spreadsheet for EllinCRM data.

        Args:
            title: Optional spreadsheet title.
            multi_sheet: Whether to create multi-sheet organization.
                        Defaults to settings.google_sheets_multi_sheet.

        Returns:
            Dict with spreadsheet_id and spreadsheet_url.

        Raises:
            ValueError: If not configured.
            HttpError: If API call fails.
        """
        service = self._get_service()

        if not title:
            timestamp = datetime.now(UTC).strftime("%Y-%m-%d %H:%M")
            title = f"EllinCRM Extractions - {timestamp}"

        # Determine if multi-sheet
        use_multi_sheet = (
            multi_sheet if multi_sheet is not None else settings.google_sheets_multi_sheet
        )

        spreadsheet_id = None
        spreadsheet_url = None

        # Strategy 1: Create directly in folder via Drive API (Bypasses Service Account Quota)
        # Using supportsAllDrives=True for Shared Drive support
        if settings.google_drive_folder_id:
            try:
                drive_service = build("drive", "v3", credentials=self._get_credentials())
                file_metadata = {
                    "name": title,
                    "mimeType": "application/vnd.google-apps.spreadsheet",
                    "parents": [settings.google_drive_folder_id],
                }
                # supportsAllDrives=True is required for Shared Drives
                # This allows the file to be owned by the Shared Drive, not the service account
                file = (
                    drive_service.files()
                    .create(body=file_metadata, fields="id, webViewLink", supportsAllDrives=True)
                    .execute()
                )
                spreadsheet_id = file.get("id")
                spreadsheet_url = file.get("webViewLink")

                # Now structure it using Sheets API
                # Default sheet is likely "Sheet1" (ID 0)
                # We need to rename/add sheets to match our desired structure
                reqs = []

                # Multi-sheet structure
                if use_multi_sheet:
                    # Rename default sheet to Summary
                    reqs.append(
                        {
                            "updateSheetProperties": {
                                "properties": {
                                    "sheetId": 0,
                                    "title": SHEET_NAMES["summary"],
                                    "gridProperties": {"frozenRowCount": 0},
                                },
                                "fields": "title,gridProperties",
                            }
                        }
                    )
                    # Add other sheets
                    for i, name in enumerate(
                        [
                            SHEET_NAMES["all"],
                            SHEET_NAMES["forms"],
                            SHEET_NAMES["emails"],
                            SHEET_NAMES["invoices"],
                        ],
                        start=1,
                    ):
                        reqs.append(
                            {
                                "addSheet": {
                                    "properties": {
                                        "sheetId": i,
                                        "title": name,
                                        "gridProperties": {"frozenRowCount": 1},
                                    }
                                }
                            }
                        )
                else:
                    # Single sheet structure, rename Sheet1
                    reqs.append(
                        {
                            "updateSheetProperties": {
                                "properties": {
                                    "sheetId": 0,
                                    "title": "Extraction Records",
                                    "gridProperties": {"frozenRowCount": 1},
                                },
                                "fields": "title,gridProperties",
                            }
                        }
                    )

                service.spreadsheets().batchUpdate(
                    spreadsheetId=spreadsheet_id, body={"requests": reqs}
                ).execute()

            except HttpError as e:
                # Re-raise to be caught by the outer block
                raise e

        # Strategy 2: Standard Sheets API Create (Fails if Quota exceeded)
        else:
            if use_multi_sheet:
                # Multi-sheet organization
                spreadsheet = {
                    "properties": {"title": title},
                    "sheets": [
                        {
                            "properties": {
                                "sheetId": 0,
                                "title": SHEET_NAMES["summary"],
                                "gridProperties": {"frozenRowCount": 0},
                            }
                        },
                        {
                            "properties": {
                                "sheetId": 1,
                                "title": SHEET_NAMES["all"],
                                "gridProperties": {"frozenRowCount": 1},
                            }
                        },
                        {
                            "properties": {
                                "sheetId": 2,
                                "title": SHEET_NAMES["forms"],
                                "gridProperties": {"frozenRowCount": 1},
                            }
                        },
                        {
                            "properties": {
                                "sheetId": 3,
                                "title": SHEET_NAMES["emails"],
                                "gridProperties": {"frozenRowCount": 1},
                            }
                        },
                        {
                            "properties": {
                                "sheetId": 4,
                                "title": SHEET_NAMES["invoices"],
                                "gridProperties": {"frozenRowCount": 1},
                            }
                        },
                    ],
                }
            else:
                # Single sheet (legacy)
                spreadsheet = {
                    "properties": {"title": title},
                    "sheets": [
                        {
                            "properties": {
                                "title": "Extraction Records",
                                "gridProperties": {"frozenRowCount": 1},
                            }
                        }
                    ],
                }

            result = (
                service.spreadsheets()
                .create(body=spreadsheet, fields="spreadsheetId,spreadsheetUrl")
                .execute()
            )

            spreadsheet_id = result.get("spreadsheetId")
            spreadsheet_url = result.get("spreadsheetUrl")

        # Common: Write Headers
        try:
            # Add headers to all sheets
            if use_multi_sheet:
                await self._write_multi_sheet_headers(spreadsheet_id)
            else:
                await self._write_headers(spreadsheet_id)

            logger.info(
                "spreadsheet_created",
                spreadsheet_id=spreadsheet_id,
                title=title,
                multi_sheet=use_multi_sheet,
                folder_id=settings.google_drive_folder_id,
            )

            return {
                "spreadsheet_id": spreadsheet_id,
                "spreadsheet_url": spreadsheet_url,
                "title": title,
                "multi_sheet": use_multi_sheet,
            }

        except HttpError as e:
            logger.error(
                "spreadsheet_creation_failed",
                error=str(e),
                status=e.resp.status,
                reason=e.resp.reason,
            )
            if e.resp.status == 403:
                # Raise 400 so the UI shows the message (instead of 500)
                raise HTTPException(
                    status_code=400,
                    detail=(
                        "Permission denied or Storage Quota Exceeded. "
                        "Please configure 'GOOGLE_DRIVE_FOLDER_ID' in settings to use a shared folder."
                    ),
                )
            raise

    async def _write_headers(self, spreadsheet_id: str) -> None:
        """Write column headers to the spreadsheet (legacy single-sheet)."""
        service = self._get_service()

        body = {"values": [HEADERS]}

        service.spreadsheets().values().update(
            spreadsheetId=spreadsheet_id,
            range="Extraction Records!A1",
            valueInputOption="RAW",
            body=body,
        ).execute()

        # Format headers (bold, background color)
        requests = [
            {
                "repeatCell": {
                    "range": {
                        "sheetId": 0,
                        "startRowIndex": 0,
                        "endRowIndex": 1,
                    },
                    "cell": {
                        "userEnteredFormat": {
                            "backgroundColor": {"red": 0.2, "green": 0.4, "blue": 0.8},
                            "textFormat": {
                                "bold": True,
                                "foregroundColor": {"red": 1, "green": 1, "blue": 1},
                            },
                        }
                    },
                    "fields": "userEnteredFormat(backgroundColor,textFormat)",
                }
            },
            {
                "autoResizeDimensions": {
                    "dimensions": {
                        "sheetId": 0,
                        "dimension": "COLUMNS",
                        "startIndex": 0,
                        "endIndex": len(HEADERS),
                    }
                }
            },
        ]

        service.spreadsheets().batchUpdate(
            spreadsheetId=spreadsheet_id,
            body={"requests": requests},
        ).execute()

    async def _write_multi_sheet_headers(self, spreadsheet_id: str) -> None:
        """Write headers to all sheets in multi-sheet spreadsheet."""
        service = self._get_service()

        # Batch update for all data sheets
        data = [
            {
                "range": f"{SHEET_NAMES['all']}!A1",
                "values": [HEADERS_ALL],
            },
            {
                "range": f"{SHEET_NAMES['forms']}!A1",
                "values": [HEADERS_FORMS],
            },
            {
                "range": f"{SHEET_NAMES['emails']}!A1",
                "values": [HEADERS_EMAILS],
            },
            {
                "range": f"{SHEET_NAMES['invoices']}!A1",
                "values": [HEADERS_INVOICES],
            },
        ]

        service.spreadsheets().values().batchUpdate(
            spreadsheetId=spreadsheet_id,
            body={"valueInputOption": "RAW", "data": data},
        ).execute()

        # Write Summary sheet title
        service.spreadsheets().values().update(
            spreadsheetId=spreadsheet_id,
            range=f"{SHEET_NAMES['summary']}!A1",
            valueInputOption="RAW",
            body={"values": [["EllinCRM Data Export Summary"]]},
        ).execute()

        # Format all headers with colors
        requests = []
        header_format = {
            "backgroundColor": {"red": 0.18, "green": 0.33, "blue": 0.59},
            "textFormat": {
                "bold": True,
                "foregroundColor": {"red": 1, "green": 1, "blue": 1},
            },
            "horizontalAlignment": "CENTER",
        }

        # Format each sheet's header row
        sheet_configs = [
            (1, len(HEADERS_ALL)),  # All Records
            (2, len(HEADERS_FORMS)),  # Forms
            (3, len(HEADERS_EMAILS)),  # Emails
            (4, len(HEADERS_INVOICES)),  # Invoices
        ]

        for sheet_id, col_count in sheet_configs:
            requests.append(
                {
                    "repeatCell": {
                        "range": {
                            "sheetId": sheet_id,
                            "startRowIndex": 0,
                            "endRowIndex": 1,
                            "startColumnIndex": 0,
                            "endColumnIndex": col_count,
                        },
                        "cell": {"userEnteredFormat": header_format},
                        "fields": "userEnteredFormat(backgroundColor,textFormat,horizontalAlignment)",
                    }
                }
            )
            requests.append(
                {
                    "autoResizeDimensions": {
                        "dimensions": {
                            "sheetId": sheet_id,
                            "dimension": "COLUMNS",
                            "startIndex": 0,
                            "endIndex": col_count,
                        }
                    }
                }
            )

        # Format Summary sheet title
        requests.append(
            {
                "repeatCell": {
                    "range": {"sheetId": 0, "startRowIndex": 0, "endRowIndex": 1},
                    "cell": {
                        "userEnteredFormat": {
                            "textFormat": {"bold": True, "fontSize": 14},
                        }
                    },
                    "fields": "userEnteredFormat(textFormat)",
                }
            }
        )

        service.spreadsheets().batchUpdate(
            spreadsheetId=spreadsheet_id,
            body={"requests": requests},
        ).execute()

        logger.info("multi_sheet_headers_written", spreadsheet_id=spreadsheet_id)

    async def sync_records(
        self,
        spreadsheet_id: str,
        include_rejected: bool = False,
        multi_sheet: bool | None = None,
    ) -> dict[str, Any]:
        """
        Sync all exportable records to the spreadsheet.

        This clears existing data (except headers) and writes all current records.
        Supports both single-sheet and multi-sheet modes.

        Args:
            spreadsheet_id: Target spreadsheet ID.
            include_rejected: Whether to include rejected records.
            multi_sheet: Whether to use multi-sheet mode.
                        Defaults to settings.google_sheets_multi_sheet.

        Returns:
            Dict with sync statistics.
        """
        self._get_service()

        # Get records to sync
        records = await self.repository.get_exportable_records(
            include_rejected=include_rejected,
        )

        if not records:
            return {
                "synced": 0,
                "spreadsheet_id": spreadsheet_id,
                "message": "No records to sync",
            }

        use_multi_sheet = (
            multi_sheet if multi_sheet is not None else settings.google_sheets_multi_sheet
        )

        if use_multi_sheet:
            return await self._sync_multi_sheet(spreadsheet_id, records)
        else:
            return await self._sync_single_sheet(spreadsheet_id, records)

    async def _sync_single_sheet(
        self,
        spreadsheet_id: str,
        records: list[ExtractionRecordDB],
    ) -> dict[str, Any]:
        """Sync to a single-sheet spreadsheet (legacy mode)."""
        service = self._get_service()

        # Convert records to rows
        rows = [self._record_to_row(r) for r in records]

        # Clear existing data (except headers)
        service.spreadsheets().values().clear(
            spreadsheetId=spreadsheet_id,
            range="Extraction Records!A2:Z10000",
        ).execute()

        # Write new data
        body = {"values": rows}
        result = (
            service.spreadsheets()
            .values()
            .update(
                spreadsheetId=spreadsheet_id,
                range="Extraction Records!A2",
                valueInputOption="USER_ENTERED",
                body=body,
            )
            .execute()
        )

        updated_rows = result.get("updatedRows", 0)

        # Log the sync
        audit_logger.log_export(
            export_format="google_sheets",
            record_count=len(records),
            destination=spreadsheet_id,
        )

        logger.info(
            "records_synced_to_sheets",
            spreadsheet_id=spreadsheet_id,
            record_count=len(records),
        )

        return {
            "synced": updated_rows,
            "spreadsheet_id": spreadsheet_id,
            "spreadsheet_url": f"https://docs.google.com/spreadsheets/d/{spreadsheet_id}",
            "message": f"Successfully synced {updated_rows} records",
        }

    async def _sync_multi_sheet(
        self,
        spreadsheet_id: str,
        records: list[ExtractionRecordDB],
    ) -> dict[str, Any]:
        """Sync to a multi-sheet spreadsheet with organization by type."""
        service = self._get_service()

        # Separate records by type
        forms = [r for r in records if r.record_type == "FORM"]
        emails = [r for r in records if r.record_type == "EMAIL"]
        invoices = [r for r in records if r.record_type == "INVOICE"]

        # Clear all data sheets (except headers)
        clear_ranges = [
            f"{SHEET_NAMES['all']}!A2:Z10000",
            f"{SHEET_NAMES['forms']}!A2:Z10000",
            f"{SHEET_NAMES['emails']}!A2:Z10000",
            f"{SHEET_NAMES['invoices']}!A2:Z10000",
            f"{SHEET_NAMES['summary']}!A2:D50",
        ]

        for range_name in clear_ranges:
            try:
                service.spreadsheets().values().clear(
                    spreadsheetId=spreadsheet_id,
                    range=range_name,
                ).execute()
            except HttpError:
                pass  # Sheet might not exist yet

        # Prepare data for batch update
        data = []

        # All Records sheet
        all_rows = [self._record_to_row(r) for r in records]
        if all_rows:
            data.append(
                {
                    "range": f"{SHEET_NAMES['all']}!A2",
                    "values": all_rows,
                }
            )

        # Forms sheet
        forms_rows = [self._record_to_form_row(r) for r in forms]
        if forms_rows:
            data.append(
                {
                    "range": f"{SHEET_NAMES['forms']}!A2",
                    "values": forms_rows,
                }
            )

        # Emails sheet
        emails_rows = [self._record_to_email_row(r) for r in emails]
        if emails_rows:
            data.append(
                {
                    "range": f"{SHEET_NAMES['emails']}!A2",
                    "values": emails_rows,
                }
            )

        # Invoices sheet
        invoices_rows = [self._record_to_invoice_row(r) for r in invoices]
        if invoices_rows:
            data.append(
                {
                    "range": f"{SHEET_NAMES['invoices']}!A2",
                    "values": invoices_rows,
                }
            )

        # Write all data
        if data:
            service.spreadsheets().values().batchUpdate(
                spreadsheetId=spreadsheet_id,
                body={"valueInputOption": "USER_ENTERED", "data": data},
            ).execute()

        # Update Summary sheet
        await self._update_summary_sheet(spreadsheet_id, records, forms, emails, invoices)

        # Log the sync
        audit_logger.log_export(
            export_format="google_sheets_multi",
            record_count=len(records),
            destination=spreadsheet_id,
        )

        logger.info(
            "records_synced_to_sheets_multi",
            spreadsheet_id=spreadsheet_id,
            total=len(records),
            forms=len(forms),
            emails=len(emails),
            invoices=len(invoices),
        )

        return {
            "synced": len(records),
            "by_type": {
                "forms": len(forms),
                "emails": len(emails),
                "invoices": len(invoices),
            },
            "spreadsheet_id": spreadsheet_id,
            "spreadsheet_url": f"https://docs.google.com/spreadsheets/d/{spreadsheet_id}",
            "message": f"Successfully synced {len(records)} records to multiple sheets",
        }

    async def _update_summary_sheet(
        self,
        spreadsheet_id: str,
        records: list[ExtractionRecordDB],
        forms: list[ExtractionRecordDB],
        emails: list[ExtractionRecordDB],
        invoices: list[ExtractionRecordDB],
    ) -> None:
        """Update the Summary sheet with statistics."""
        service = self._get_service()

        # Calculate statistics
        status_counts: dict[str, int] = {}
        for r in records:
            status_counts[r.status] = status_counts.get(r.status, 0) + 1

        total_amount = sum(float(r.extracted_data.get("total_amount", 0) or 0) for r in invoices)

        now = datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S UTC")

        # Build summary data
        summary_data = [
            ["EllinCRM Data Export Summary"],
            [f"Last Updated: {now}"],
            [""],
            ["Record Counts", ""],
            ["Total Records", len(records)],
            ["Forms", len(forms)],
            ["Emails", len(emails)],
            ["Invoices", len(invoices)],
            [""],
            ["Status Breakdown", ""],
        ]

        for status, count in sorted(status_counts.items()):
            summary_data.append([status.capitalize(), count])

        if invoices:
            summary_data.extend(
                [
                    [""],
                    ["Financial Summary (Invoices)", ""],
                    ["Total Invoice Amount", f"€{total_amount:,.2f}"],
                ]
            )

        # Write to Summary sheet
        service.spreadsheets().values().update(
            spreadsheetId=spreadsheet_id,
            range=f"{SHEET_NAMES['summary']}!A1",
            valueInputOption="USER_ENTERED",
            body={"values": summary_data},
        ).execute()

    def _record_to_form_row(self, record: ExtractionRecordDB) -> list[Any]:
        """Convert a FORM record to a form-specific row."""
        data = record.final_data
        return [
            str(record.id),
            record.source_file,
            record.created_at.strftime("%Y-%m-%d %H:%M:%S"),
            record.status,
            f"{record.confidence_score:.1%}",
            data.get("full_name", ""),
            data.get("email", ""),
            data.get("phone", ""),
            data.get("company", ""),
            data.get("service_interest", ""),
            data.get("priority", ""),
            self._truncate(data.get("message", ""), 300),
            record.reviewed_by or "",
            record.reviewed_at.strftime("%Y-%m-%d %H:%M:%S") if record.reviewed_at else "",
        ]

    def _record_to_email_row(self, record: ExtractionRecordDB) -> list[Any]:
        """Convert an EMAIL record to an email-specific row."""
        data = record.final_data
        return [
            str(record.id),
            record.source_file,
            record.created_at.strftime("%Y-%m-%d %H:%M:%S"),
            record.status,
            f"{record.confidence_score:.1%}",
            data.get("sender_name", ""),
            data.get("sender_email", ""),
            data.get("phone", ""),
            data.get("company", ""),
            data.get("service_interest", ""),
            data.get("email_type", ""),
            data.get("invoice_number", ""),
            data.get("invoice_amount", ""),
            self._truncate(data.get("subject", ""), 100),
            record.reviewed_by or "",
            record.reviewed_at.strftime("%Y-%m-%d %H:%M:%S") if record.reviewed_at else "",
        ]

    def _record_to_invoice_row(self, record: ExtractionRecordDB) -> list[Any]:
        """Convert an INVOICE record to an invoice-specific row."""
        data = record.final_data
        return [
            str(record.id),
            record.source_file,
            record.created_at.strftime("%Y-%m-%d %H:%M:%S"),
            record.status,
            f"{record.confidence_score:.1%}",
            data.get("invoice_number", ""),
            data.get("client_name", ""),
            data.get("net_amount", ""),
            data.get("vat_amount", ""),
            data.get("total_amount", ""),
            data.get("payment_terms", ""),
            self._truncate(data.get("notes", ""), 200),
            record.reviewed_by or "",
            record.reviewed_at.strftime("%Y-%m-%d %H:%M:%S") if record.reviewed_at else "",
        ]

    def _record_to_row(self, record: ExtractionRecordDB) -> list[Any]:
        """
        Convert a record to a spreadsheet row.

        Args:
            record: ExtractionRecordDB to convert.

        Returns:
            List of cell values.
        """
        data = record.final_data

        # Base fields
        row = [
            str(record.id),
            record.record_type,
            record.source_file,
            record.created_at.strftime("%Y-%m-%d %H:%M:%S"),
            record.status,
            f"{record.confidence_score:.1%}",
        ]

        # Type-specific fields
        if record.record_type == "FORM":
            row.extend(
                [
                    data.get("full_name", ""),
                    data.get("email", ""),
                    data.get("phone", ""),
                    data.get("company", ""),
                    data.get("service_interest", ""),
                    "",  # Amount
                    "",  # VAT
                    "",  # Total
                    "",  # Invoice Number
                    data.get("priority", ""),
                    data.get("message", ""),
                ]
            )
        elif record.record_type == "EMAIL":
            row.extend(
                [
                    data.get("sender_name", ""),
                    data.get("sender_email", ""),
                    data.get("phone", ""),
                    data.get("company", ""),
                    data.get("service_interest", ""),
                    data.get("invoice_amount", ""),
                    "",  # VAT
                    "",  # Total
                    data.get("invoice_number", ""),
                    "",  # Priority
                    self._truncate(data.get("body", ""), 500),
                ]
            )
        elif record.record_type == "INVOICE":
            row.extend(
                [
                    data.get("client_name", ""),
                    "",  # Email
                    "",  # Phone
                    "",  # Company
                    "",  # Service Interest
                    data.get("net_amount", ""),
                    data.get("vat_amount", ""),
                    data.get("total_amount", ""),
                    data.get("invoice_number", ""),
                    "",  # Priority
                    data.get("notes", ""),
                ]
            )
        else:
            row.extend([""] * 11)

        # Review info
        row.extend(
            [
                record.reviewed_by or "",
                record.reviewed_at.strftime("%Y-%m-%d %H:%M:%S") if record.reviewed_at else "",
                record.updated_at.strftime("%Y-%m-%d %H:%M:%S") if record.updated_at else "",
            ]
        )

        return row

    async def auto_sync_record(
        self,
        record: ExtractionRecordDB,
        action: str = "updated",
    ) -> dict[str, Any] | None:
        """
        Auto-sync a single record to Google Sheets after approval/rejection/edit.

        This is called automatically when a record status changes if auto-sync is enabled.
        It performs a full sync to ensure data consistency across all sheets.

        Args:
            record: The record that was updated.
            action: The action performed (approved, rejected, edited).

        Returns:
            Sync result dict or None if auto-sync is disabled/not configured.
        """
        # Check if auto-sync is enabled
        if not settings.google_sheets_auto_sync:
            logger.debug(
                "auto_sync_skipped",
                reason="auto_sync_disabled",
                record_id=str(record.id),
            )
            return None

        # Check if spreadsheet ID is configured
        spreadsheet_id = settings.google_spreadsheet_id
        if not spreadsheet_id:
            logger.debug(
                "auto_sync_skipped",
                reason="no_spreadsheet_id_configured",
                record_id=str(record.id),
            )
            return None

        try:
            # Perform full sync to maintain consistency
            # Use runtime settings to determine if rejected records should be included
            from app.core.runtime_settings import get_auto_sync_include_rejected

            include_rejected = get_auto_sync_include_rejected()

            result = await self.sync_records(
                spreadsheet_id=spreadsheet_id,
                include_rejected=include_rejected,
            )

            logger.info(
                "auto_sync_completed",
                record_id=str(record.id),
                action=action,
                synced=result.get("synced", 0),
            )

            return result

        except Exception as e:
            # Log error but don't fail the original operation
            logger.error(
                "auto_sync_failed",
                record_id=str(record.id),
                action=action,
                error=str(e),
            )
            return None

    async def trigger_full_sync(self) -> dict[str, Any] | None:
        """
        Trigger a full sync if auto-sync is configured.

        Returns:
            Sync result dict or None if not configured.
        """
        spreadsheet_id = settings.google_spreadsheet_id
        if not spreadsheet_id:
            return None

        if not self.is_configured():
            return None

        return await self.sync_records(spreadsheet_id=spreadsheet_id)

    def _truncate(self, text: str | None, max_length: int) -> str:
        """Truncate text to max length."""
        if not text:
            return ""
        if len(text) <= max_length:
            return text
        return text[: max_length - 3] + "..."


class GoogleSheetsServiceFallback:
    """
    Fallback service when Google Sheets is not configured.

    Provides helpful error messages and alternative export options.
    """

    def __init__(self, repository: RecordRepository):
        self.repository = repository

    def is_configured(self) -> bool:
        return False

    async def create_spreadsheet(
        self,
        title: str | None = None,
        multi_sheet: bool | None = None,
    ) -> dict[str, str]:
        raise ValueError(
            "Google Sheets integration is not configured. "
            "To enable it:\n"
            "1. Create a Google Cloud project\n"
            "2. Enable Google Sheets API\n"
            "3. Create a Service Account and download credentials JSON\n"
            "4. Set GOOGLE_CREDENTIALS_PATH environment variable\n"
            "5. Share your spreadsheet with the service account email\n\n"
            "Alternatively, use the Export feature to download CSV/Excel files."
        )

    async def sync_records(self, spreadsheet_id: str, **kwargs) -> dict[str, Any]:
        raise ValueError(
            "Google Sheets integration is not configured. "
            "Use Export to download data as CSV or Excel."
        )

    async def auto_sync_record(
        self,
        record: ExtractionRecordDB,
        action: str = "updated",
    ) -> dict[str, Any] | None:
        """Auto-sync is not available when not configured - silently skip."""
        return None

    async def trigger_full_sync(self) -> dict[str, Any] | None:
        """Full sync is not available when not configured - silently skip."""
        return None


def get_google_sheets_service(
    repository: RecordRepository,
) -> GoogleSheetsService | GoogleSheetsServiceFallback:
    """
    Factory function to get the appropriate Google Sheets service.

    Returns:
        GoogleSheetsService if configured, otherwise GoogleSheetsServiceFallback.
    """
    service = GoogleSheetsService(repository)
    if service.is_configured():
        return service
    return GoogleSheetsServiceFallback(repository)
