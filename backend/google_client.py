import json
import os
import re
from datetime import datetime
from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

SCOPES = [
    "https://www.googleapis.com/auth/documents",
    "https://www.googleapis.com/auth/drive",
    "https://www.googleapis.com/auth/spreadsheets",
]

PROJECT_ROOT = Path(__file__).parent.parent
TOKEN_PATH = PROJECT_ROOT / "token.json"
SECRETS_PATH = PROJECT_ROOT / "client_secrets.json"
LOCAL_CONFIG_PATH = PROJECT_ROOT / "local_config.json"

SHEET_HEADERS = ["Date", "Company", "Title", "Seniority", "Match Score", "Job Post Link", "Tailored CV Link", "Submitted?"]


def _creds() -> Credentials:
    if not SECRETS_PATH.exists():
        raise FileNotFoundError(
            f"client_secrets.json not found at {SECRETS_PATH}. "
            "Create OAuth 2.0 credentials (Desktop app) in Google Cloud Console and download them here."
        )
    creds = None
    if TOKEN_PATH.exists():
        creds = Credentials.from_authorized_user_file(str(TOKEN_PATH), SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(str(SECRETS_PATH), SCOPES)
            creds = flow.run_local_server(port=0)
        TOKEN_PATH.write_text(creds.to_json())
    return creds


def _load_local_config() -> dict:
    if LOCAL_CONFIG_PATH.exists():
        return json.loads(LOCAL_CONFIG_PATH.read_text())
    return {}


def _save_local_config(data: dict) -> None:
    config = _load_local_config()
    config.update(data)
    LOCAL_CONFIG_PATH.write_text(json.dumps(config, indent=2))


def create_tailored_cv_doc(cv_content: str, job_info: dict) -> str:
    """Copy the CV template (or create fresh doc) and write tailored content. Returns edit URL."""
    creds = _creds()
    docs = build("docs", "v1", credentials=creds)
    drive = build("drive", "v3", credentials=creds)

    company = job_info.get("company_name", "Company")
    title = job_info.get("job_title", "Position")
    date_str = datetime.now().strftime("%Y-%m-%d")
    doc_title = f"Tahel CV — {company} — {title} — {date_str}"

    template_id = os.getenv("GOOGLE_CV_TEMPLATE_ID", "").strip()
    output_folder_id = os.getenv("GOOGLE_OUTPUT_FOLDER_ID", "").strip()

    copy_body = {"name": doc_title}
    if output_folder_id:
        copy_body["parents"] = [output_folder_id]

    if template_id:
        doc = drive.files().copy(fileId=template_id, body=copy_body).execute()
        doc_id = doc["id"]
        existing = docs.documents().get(documentId=doc_id).execute()
        end_index = existing["body"]["content"][-1]["endIndex"] - 1
        if end_index > 1:
            docs.documents().batchUpdate(
                documentId=doc_id,
                body={"requests": [
                    {"deleteContentRange": {"range": {"startIndex": 1, "endIndex": end_index}}}
                ]}
            ).execute()
        docs.documents().batchUpdate(
            documentId=doc_id,
            body={"requests": [
                {"insertText": {"location": {"index": 1}, "text": cv_content}}
            ]}
        ).execute()
    else:
        doc = docs.documents().create(body={"title": doc_title}).execute()
        doc_id = doc["documentId"]
        if output_folder_id:
            drive.files().update(
                fileId=doc_id,
                addParents=output_folder_id,
                removeParents="root",
                fields="id, parents"
            ).execute()
        docs.documents().batchUpdate(
            documentId=doc_id,
            body={"requests": [
                {"insertText": {"location": {"index": 1}, "text": cv_content}}
            ]}
        ).execute()

    drive.permissions().create(
        fileId=doc_id,
        body={"type": "anyone", "role": "reader"},
    ).execute()

    return f"https://docs.google.com/document/d/{doc_id}/edit"


def log_to_sheet(job_info: dict, match_score: int, cv_url: str, job_url: str) -> str:
    """Append a row to the tracking sheet. Creates the sheet on first use. Returns sheet URL."""
    creds = _creds()
    sheets = build("sheets", "v4", credentials=creds)
    drive = build("drive", "v3", credentials=creds)

    sheet_id = os.getenv("GOOGLE_SHEET_ID", "").strip() or _load_local_config().get("sheet_id", "")

    if not sheet_id:
        sheet_id = _create_tracking_sheet(sheets, drive)
        _save_local_config({"sheet_id": sheet_id})
        print(f"\n[CV Updater] Tracking sheet created. Add to .env:\nGOOGLE_SHEET_ID={sheet_id}\n")

    row = [
        datetime.now().strftime("%Y-%m-%d"),
        job_info.get("company_name", ""),
        job_info.get("job_title", ""),
        job_info.get("seniority", ""),
        match_score,
        job_url,
        cv_url,
        False,  # Submitted?
    ]
    result = sheets.spreadsheets().values().append(
        spreadsheetId=sheet_id,
        range="Sheet1!A:H",
        valueInputOption="RAW",
        body={"values": [row]},
    ).execute()

    # Apply checkbox data validation to the Submitted? cell (column H)
    updated_range = result.get("updates", {}).get("updatedRange", "")
    row_match = re.search(r":H(\d+)$", updated_range)
    if row_match:
        row_idx = int(row_match.group(1)) - 1  # convert to 0-based
        meta = sheets.spreadsheets().get(spreadsheetId=sheet_id, fields="sheets.properties").execute()
        grid_id = meta["sheets"][0]["properties"]["sheetId"]
        sheets.spreadsheets().batchUpdate(
            spreadsheetId=sheet_id,
            body={"requests": [{
                "setDataValidation": {
                    "range": {
                        "sheetId": grid_id,
                        "startRowIndex": row_idx,
                        "endRowIndex": row_idx + 1,
                        "startColumnIndex": 7,
                        "endColumnIndex": 8,
                    },
                    "rule": {"condition": {"type": "BOOLEAN"}, "showCustomUi": True},
                }
            }]}
        ).execute()

    return f"https://docs.google.com/spreadsheets/d/{sheet_id}"


def check_duplicate(company_name: str, job_title: str) -> dict | None:
    """Check if this company+title combo already exists in the tracker. Returns existing row data or None."""
    try:
        creds = _creds()
        sheets = build("sheets", "v4", credentials=creds)
        sheet_id = os.getenv("GOOGLE_SHEET_ID", "").strip() or _load_local_config().get("sheet_id", "")
        if not sheet_id:
            return None

        result = sheets.spreadsheets().values().get(
            spreadsheetId=sheet_id,
            range="Sheet1!A:H",
        ).execute()
        rows = result.get("values", [])
        if len(rows) <= 1:
            return None

        company_lower = company_name.lower().strip()
        title_lower = job_title.lower().strip()

        for row in rows[1:]:
            if len(row) < 3:
                continue
            if row[1].lower().strip() == company_lower and row[2].lower().strip() == title_lower:
                return {
                    "date": row[0] if len(row) > 0 else "",
                    "company": row[1] if len(row) > 1 else "",
                    "title": row[2] if len(row) > 2 else "",
                    "cv_url": row[6] if len(row) > 6 else "",
                }
        return None
    except Exception:
        return None  # Never block a run due to a failed check


def _create_tracking_sheet(sheets, drive) -> str:
    header_cells = [{"userEnteredValue": {"stringValue": h}} for h in SHEET_HEADERS]
    spreadsheet = sheets.spreadsheets().create(body={
        "properties": {"title": "Tahel — Job Applications Tracker"},
        "sheets": [{
            "properties": {"title": "Sheet1"},
            "data": [{"rowData": [{"values": header_cells}]}],
        }],
    }).execute()
    sheet_id = spreadsheet["spreadsheetId"]
    drive.permissions().create(
        fileId=sheet_id,
        body={"type": "anyone", "role": "writer"},
    ).execute()
    return sheet_id
