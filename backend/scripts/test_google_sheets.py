#!/usr/bin/env python3
"""
Test script for Google Sheets integration.

Usage:
    python scripts/test_google_sheets.py --check        # Check if configured
    python scripts/test_google_sheets.py --create       # Create new spreadsheet
    python scripts/test_google_sheets.py --sync ID      # Sync to spreadsheet
    python scripts/test_google_sheets.py --test-all     # Full integration test

Requirements:
    - GOOGLE_CREDENTIALS_PATH environment variable set
    - Google Sheets API enabled in Google Cloud project
    - Service account with credentials JSON
"""

import argparse
import asyncio
import os
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv

# Load .env file
load_dotenv()


def check_configuration():
    """Check if Google Sheets is properly configured."""
    print("\n" + "=" * 60)
    print("GOOGLE SHEETS CONFIGURATION CHECK")
    print("=" * 60)

    credentials_path = os.getenv("GOOGLE_CREDENTIALS_PATH")
    spreadsheet_id = os.getenv("GOOGLE_SPREADSHEET_ID")
    auto_sync = os.getenv("GOOGLE_SHEETS_AUTO_SYNC", "true").lower() == "true"
    multi_sheet = os.getenv("GOOGLE_SHEETS_MULTI_SHEET", "true").lower() == "true"

    print(f"\n1. GOOGLE_CREDENTIALS_PATH: {credentials_path or 'NOT SET'}")
    if credentials_path:
        path = Path(credentials_path)
        if path.exists():
            print(f"   Status: File EXISTS")
            # Try to read and validate JSON
            try:
                import json
                with open(path) as f:
                    creds = json.load(f)
                print(f"   Client Email: {creds.get('client_email', 'NOT FOUND')}")
                print(f"   Project ID: {creds.get('project_id', 'NOT FOUND')}")
            except Exception as e:
                print(f"   Error reading JSON: {e}")
        else:
            print(f"   Status: File NOT FOUND at {path}")

    print(f"\n2. GOOGLE_SPREADSHEET_ID: {spreadsheet_id or 'NOT SET'}")
    if spreadsheet_id:
        print(f"   URL: https://docs.google.com/spreadsheets/d/{spreadsheet_id}/edit")

    print(f"\n3. GOOGLE_SHEETS_AUTO_SYNC: {auto_sync}")
    print(f"4. GOOGLE_SHEETS_MULTI_SHEET: {multi_sheet}")

    # Try to import and initialize the service
    print("\n" + "-" * 60)
    print("Testing Service Initialization...")
    print("-" * 60)

    try:
        from app.core.config import settings
        print(f"Settings loaded: OK")
        print(f"  - google_credentials_path: {settings.google_credentials_path}")
        print(f"  - google_spreadsheet_id: {settings.google_spreadsheet_id}")
        print(f"  - google_sheets_auto_sync: {settings.google_sheets_auto_sync}")
        print(f"  - google_sheets_multi_sheet: {settings.google_sheets_multi_sheet}")
    except Exception as e:
        print(f"Error loading settings: {e}")
        return False

    # Try to create the service
    try:
        from app.services.google_sheets_service import GoogleSheetsService

        # Create a mock repository for testing
        class MockRepository:
            async def get_exportable_records(self, **kwargs):
                return []

        service = GoogleSheetsService(MockRepository())
        is_configured = service.is_configured()
        print(f"\nService Configuration Status: {'CONFIGURED' if is_configured else 'NOT CONFIGURED'}")

        if is_configured:
            print("\n[SUCCESS] Google Sheets integration is ready!")
            return True
        else:
            print("\n[WARNING] Google Sheets is not fully configured.")
            print("Please check the credentials path and ensure the file exists.")
            return False

    except Exception as e:
        print(f"\n[ERROR] Failed to initialize service: {e}")
        return False


async def create_spreadsheet(title: str = None):
    """Create a new Google Spreadsheet."""
    print("\n" + "=" * 60)
    print("CREATING NEW GOOGLE SPREADSHEET")
    print("=" * 60)

    try:
        from app.services.google_sheets_service import GoogleSheetsService

        class MockRepository:
            async def get_exportable_records(self, **kwargs):
                return []

        service = GoogleSheetsService(MockRepository())

        if not service.is_configured():
            print("[ERROR] Google Sheets is not configured!")
            return None

        print(f"\nCreating spreadsheet...")
        if title:
            print(f"Title: {title}")

        result = await service.create_spreadsheet(title=title)

        print("\n[SUCCESS] Spreadsheet created!")
        print(f"  Spreadsheet ID: {result['spreadsheet_id']}")
        print(f"  URL: {result['spreadsheet_url']}")
        print(f"  Multi-sheet: {result.get('multi_sheet', False)}")

        print("\n" + "-" * 60)
        print("NEXT STEPS:")
        print("-" * 60)
        print(f"1. Add this to your .env file:")
        print(f"   GOOGLE_SPREADSHEET_ID={result['spreadsheet_id']}")
        print(f"\n2. Share the spreadsheet with your service account email")
        print(f"   (Check your credentials JSON for 'client_email')")

        return result['spreadsheet_id']

    except Exception as e:
        print(f"\n[ERROR] Failed to create spreadsheet: {e}")
        import traceback
        traceback.print_exc()
        return None


async def sync_to_spreadsheet(spreadsheet_id: str):
    """Sync records to a Google Spreadsheet."""
    print("\n" + "=" * 60)
    print("SYNCING TO GOOGLE SPREADSHEET")
    print("=" * 60)
    print(f"Spreadsheet ID: {spreadsheet_id}")

    try:
        # This requires a database connection
        from app.db.database import async_session_maker
        from app.db.repositories import RecordRepository
        from app.services.google_sheets_service import GoogleSheetsService

        async with async_session_maker() as session:
            repository = RecordRepository(session)
            service = GoogleSheetsService(repository)

            if not service.is_configured():
                print("[ERROR] Google Sheets is not configured!")
                return False

            print("\nSyncing records...")
            result = await service.sync_records(
                spreadsheet_id=spreadsheet_id,
                include_rejected=True,
            )

            print("\n[SUCCESS] Sync completed!")
            print(f"  Records synced: {result.get('synced', 0)}")
            if 'by_type' in result:
                print(f"  Forms: {result['by_type'].get('forms', 0)}")
                print(f"  Emails: {result['by_type'].get('emails', 0)}")
                print(f"  Invoices: {result['by_type'].get('invoices', 0)}")
            print(f"  URL: {result.get('spreadsheet_url', 'N/A')}")

            return True

    except Exception as e:
        print(f"\n[ERROR] Failed to sync: {e}")
        import traceback
        traceback.print_exc()
        return False


async def run_full_test():
    """Run a complete integration test."""
    print("\n" + "=" * 60)
    print("FULL GOOGLE SHEETS INTEGRATION TEST")
    print("=" * 60)

    # Step 1: Check configuration
    print("\n[Step 1/3] Checking configuration...")
    if not check_configuration():
        print("\n[FAILED] Configuration check failed. Please fix the issues above.")
        return False

    # Step 2: Create a test spreadsheet
    print("\n[Step 2/3] Creating test spreadsheet...")
    spreadsheet_id = await create_spreadsheet(title="EllinCRM Integration Test")
    if not spreadsheet_id:
        print("\n[FAILED] Could not create spreadsheet.")
        return False

    # Step 3: Try to sync (may fail if no database)
    print("\n[Step 3/3] Testing sync...")
    try:
        await sync_to_spreadsheet(spreadsheet_id)
    except Exception as e:
        print(f"\n[WARNING] Sync test skipped (database may not be available): {e}")
        print("This is OK for initial testing - sync will work when the app is running.")

    print("\n" + "=" * 60)
    print("INTEGRATION TEST COMPLETE")
    print("=" * 60)
    print(f"\nYour test spreadsheet: https://docs.google.com/spreadsheets/d/{spreadsheet_id}/edit")
    print("\nDon't forget to:")
    print(f"1. Share the spreadsheet with your service account")
    print(f"2. Add GOOGLE_SPREADSHEET_ID={spreadsheet_id} to your .env")

    return True


def main():
    parser = argparse.ArgumentParser(
        description="Test Google Sheets integration for EllinCRM"
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Check if Google Sheets is properly configured"
    )
    parser.add_argument(
        "--create",
        action="store_true",
        help="Create a new Google Spreadsheet"
    )
    parser.add_argument(
        "--title",
        type=str,
        default=None,
        help="Title for the new spreadsheet (with --create)"
    )
    parser.add_argument(
        "--sync",
        type=str,
        metavar="SPREADSHEET_ID",
        help="Sync records to the specified spreadsheet"
    )
    parser.add_argument(
        "--test-all",
        action="store_true",
        help="Run full integration test"
    )

    args = parser.parse_args()

    # Default to check if no arguments provided
    if not any([args.check, args.create, args.sync, args.test_all]):
        args.check = True

    if args.check:
        check_configuration()

    if args.create:
        asyncio.run(create_spreadsheet(args.title))

    if args.sync:
        asyncio.run(sync_to_spreadsheet(args.sync))

    if args.test_all:
        asyncio.run(run_full_test())


if __name__ == "__main__":
    main()
