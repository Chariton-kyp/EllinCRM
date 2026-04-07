import os
import sys
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

# Define scopes
SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

CREDENTIALS_FILE = "credentials/google-sheets-credentials.json"

def verify():
    print("--- Google API Verification Script ---")
    
    # 1. Check if file exists
    if not os.path.exists(CREDENTIALS_FILE):
        print(f"ERROR: Credentials file not found at {CREDENTIALS_FILE}")
        return

    try:
        # 2. Load Credentials
        creds = Credentials.from_service_account_file(CREDENTIALS_FILE, scopes=SCOPES)
        print(f"SUCCESS: Loaded credentials.")
        print(f"Service Account Email: {creds.service_account_email}")
        print(f"Project ID: {creds.project_id}")
        
        # 3. Test Drive API
        print("\nTesting Google Drive API (creating a test file)...")
        service = build('drive', 'v3', credentials=creds)
        
        # Try to create a simple file to verify 'drive' scope write permissions
        file_metadata = {
            'name': 'EllinCRM_Connection_Test',
            'mimeType': 'application/vnd.google-apps.spreadsheet'
        }
        file = service.files().create(body=file_metadata, fields='id').execute()
        print(f"SUCCESS: Created test spreadsheet with ID: {file.get('id')}")
        
        # Clean up
        service.files().delete(fileId=file.get('id')).execute()
        print("SUCCESS: Cleaned up test file.")
        
        print("\nVERDICT: Google Drive API is fully functional!")
        
    except HttpError as e:
        print(f"\nERROR: Google API Error: {e}")
        print(f"Details: {e.content.decode('utf-8')}")
        if e.resp.status == 403:
             print("\nSuggestion: Double check that 'Google Drive API' is enabled for THIS specific Project ID above.")
    except Exception as e:
        print(f"\nERROR: Unexpected error: {e}")

if __name__ == "__main__":
    verify()
