import json
import os
from datetime import datetime
from pathlib import Path

from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build

SCOPES = [
    "https://www.googleapis.com/auth/documents",
    "https://www.googleapis.com/auth/drive",
    "https://www.googleapis.com/auth/spreadsheets",
]

LOCAL_CONFIG_PATH = Path(__file__).parent.parent / "local_config.json"

SHEET_HEADERS = ["Date", "Company", "Title", "Seniority", "Match Score", "Job Post Link", "Tailored CV Link"]


def _creds() -> Credentials:
    path = os.getenv("GOOGLE_CREDENTIALS_PATH", "google_credentials.json")
    if not Path(path).exists():
        raise FileNotFoundError(
            f"Google credentials not found at '{path}'. "
            "See SETUP.md for instructions on creating a service account."
        )
    return Credentials.from_service_account_file(path, scopes=SCOPES)


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

    if template_id:
        doc = drive.files().copy(fileId=template_id, body={"name": doc_title}).execute()
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
    ]
    sheets.spreadsheets().values().append(
        spreadsheetId=sheet_id,
        range="Sheet1!A:G",
        valueInputOption="RAW",
        body={"values": [row]},
    ).execute()

    return f"https://docs.google.com/spreadsheets/d/{sheet_id}"


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
