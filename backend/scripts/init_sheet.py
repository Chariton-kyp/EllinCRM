import asyncio
import sys
import logging
from app.services.google_sheets_service import GoogleSheetsService, SHEET_NAMES
from app.db.repositories import RecordRepository
from app.core.config import settings

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def init_sheet():
    print(f"--- Initializing Spreadsheet: {settings.google_spreadsheet_id} ---")
    
    if not settings.google_spreadsheet_id:
        print("Error: GOOGLE_SPREADSHEET_ID is not set.")
        return

    repo = None 
    service = GoogleSheetsService(repo)
    
    try:
        sheet_service = service._get_service()
        spreadsheet_id = settings.google_spreadsheet_id
        
        # Get current state
        metadata = sheet_service.spreadsheets().get(spreadsheetId=spreadsheet_id).execute()
        sheets = metadata.get('sheets', [])
        
        # Map Title -> ID
        sheet_map = {s['properties']['title']: s['properties']['sheetId'] for s in sheets}
        print(f"Current State: {sheet_map}")
        
        reqs = []
        
        # Target Configuration
        # Summary (0), All (1), Forms (2), Emails (3), Invoices (4)
        targets = {
            SHEET_NAMES["summary"]: 0,
            SHEET_NAMES["all"]: 1,
            SHEET_NAMES["forms"]: 2,
            SHEET_NAMES["emails"]: 3,
            SHEET_NAMES["invoices"]: 4
        }
        
        # 1. Check/Fix Summary (ID 0)
        # Find who has ID 0
        sheet0_title = next((t for t, i in sheet_map.items() if i == 0), None)
        if sheet0_title:
             if sheet0_title != SHEET_NAMES["summary"]:
                print(f"Queueing: Rename '{sheet0_title}' (ID 0) -> '{SHEET_NAMES['summary']}'")
                reqs.append({
                    "updateSheetProperties": {
                        "properties": {
                            "sheetId": 0,
                            "title": SHEET_NAMES["summary"],
                             # Do NOT touch gridProperties here to avoid row deletion error
                        },
                        "fields": "title"
                    }
                })
        else:
             print("Warning: No sheet with ID 0 found. Cannot ensure Summary is ID 0.")

        # 2. Check/Fix other sheets
        for name, target_id in targets.items():
            if name == SHEET_NAMES["summary"]: continue # Handled above
            
            current_id = sheet_map.get(name)
            
            if current_id is not None:
                if current_id != target_id:
                    print(f"Queueing: Delete '{name}' (ID {current_id}) - Wrong ID")
                    reqs.append({"deleteSheet": {"sheetId": current_id}})
                    # We will recreate it below
                    current_id = None # Treat as not existing
            
            # If not exists (or deleted above), create it
            if current_id is None:
                # Check if target_id is already taken by some OTHER sheet?
                clashing_title = next((t for t, i in sheet_map.items() if i == target_id and t != name), None)
                if clashing_title:
                     # This shouldn't happen usually unless mess. 
                     # If ID 1 is taken by "Sheet2", delete "Sheet2".
                     print(f"Queueing: Delete '{clashing_title}' (ID {target_id}) - Blocking target ID")
                     reqs.append({"deleteSheet": {"sheetId": target_id}})
                
                print(f"Queueing: Create '{name}' (ID {target_id})")
                reqs.append({
                    "addSheet": {
                        "properties": {
                            "sheetId": target_id,
                            "title": name,
                            "gridProperties": {"frozenRowCount": 1}
                        }
                    }
                })

        if reqs:
            print("Applying structural repairs...")
            sheet_service.spreadsheets().batchUpdate(
                spreadsheetId=spreadsheet_id,
                body={"requests": reqs}
            ).execute()
            print("Structure repaired.")
        else:
            print("Structure verified (No changes needed).")

        # 3. Write Headers
        print("Writing headers...")
        await service._write_multi_sheet_headers(spreadsheet_id)
        print("Headers written.")
        
        print("--- SUCCESS: Spreadsheet initialized ---")

    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(init_sheet())
