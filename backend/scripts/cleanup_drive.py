#!/usr/bin/env python3
"""
Cleanup script to delete old spreadsheets from the service account's Drive.
This frees up quota so new spreadsheets can be created.

Run inside the backend container:
    docker exec -it ellincrm-backend-dev python cleanup_drive.py
"""

import os
from pathlib import Path
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

# Spreadsheets to KEEP (don't delete these)
# Reads from GOOGLE_SPREADSHEET_ID environment variable
_configured_id = os.getenv("GOOGLE_SPREADSHEET_ID", "")
KEEP_SPREADSHEETS = {_configured_id} if _configured_id else set()


def main():
    credentials_path = os.getenv("GOOGLE_CREDENTIALS_PATH", "/app/credentials/google-sheets-credentials.json")

    if not Path(credentials_path).exists():
        print(f"ERROR: Credentials file not found at {credentials_path}")
        return

    print(f"Loading credentials from: {credentials_path}")
    credentials = Credentials.from_service_account_file(credentials_path, scopes=SCOPES)

    drive_service = build("drive", "v3", credentials=credentials)

    # List all spreadsheets owned by the service account
    print("\nSearching for spreadsheets owned by service account...")
    results = drive_service.files().list(
        q="mimeType='application/vnd.google-apps.spreadsheet'",
        spaces="drive",
        fields="files(id, name, createdTime, ownedByMe)",
        pageSize=100,
    ).execute()

    files = results.get("files", [])

    if not files:
        print("No spreadsheets found.")
        return

    print(f"\nFound {len(files)} spreadsheet(s):\n")

    to_delete = []
    to_keep = []

    for f in files:
        file_id = f["id"]
        name = f["name"]
        created = f.get("createdTime", "Unknown")
        owned = f.get("ownedByMe", False)

        if file_id in KEEP_SPREADSHEETS:
            to_keep.append(f)
            print(f"  [KEEP] {name}")
            print(f"         ID: {file_id}")
            print(f"         Created: {created}")
        elif owned:
            to_delete.append(f)
            print(f"  [DELETE] {name}")
            print(f"           ID: {file_id}")
            print(f"           Created: {created}")
        else:
            print(f"  [SKIP - Not owned] {name}")
            print(f"         ID: {file_id}")

    if not to_delete:
        print("\nNo spreadsheets to delete.")
        return

    print(f"\n{'='*50}")
    print(f"Will DELETE {len(to_delete)} spreadsheet(s)")
    print(f"Will KEEP {len(to_keep)} spreadsheet(s)")
    print(f"{'='*50}")

    confirm = input("\nType 'YES' to confirm deletion: ")

    if confirm != "YES":
        print("Aborted.")
        return

    print("\nDeleting spreadsheets...")
    deleted_count = 0
    error_count = 0

    for f in to_delete:
        try:
            drive_service.files().delete(fileId=f["id"]).execute()
            print(f"  Deleted: {f['name']}")
            deleted_count += 1
        except Exception as e:
            print(f"  ERROR deleting {f['name']}: {e}")
            error_count += 1

    print(f"\nDone! Deleted {deleted_count} spreadsheet(s), {error_count} error(s).")
    print("\nYou should now be able to create new spreadsheets!")


if __name__ == "__main__":
    main()
