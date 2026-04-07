import os
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build

SCOPES = ["https://www.googleapis.com/auth/drive"]
CREDS_FILE = "/app/credentials/google-sheets-credentials.json"

def check_quota():
    print("--- Checking Service Account Quota ---")
    if not os.path.exists(CREDS_FILE):
        print(f"Error: Credentials not found at {CREDS_FILE}")
        return

    try:
        creds = Credentials.from_service_account_file(CREDS_FILE, scopes=SCOPES)
        service = build('drive', 'v3', credentials=creds)
        
        # Get About info which contains quota
        about = service.about().get(fields="storageQuota,user").execute()
        
        quota = about.get('storageQuota', {})
        usage = int(quota.get('usage', 0))
        limit = int(quota.get('limit', 0))
        
        print(f"User (Service Account): {about.get('user', {}).get('emailAddress')}")
        print(f"Usage: {usage / (1024*1024*1024):.2f} GB")
        if limit > 0:
            print(f"Limit: {limit / (1024*1024*1024):.2f} GB")
            print(f"Percent: {(usage/limit)*100:.1f}%")
        else:
            print("Limit: Unlimited (or unknown)")

    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    check_quota()
