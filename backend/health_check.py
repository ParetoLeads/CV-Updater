import os
from pathlib import Path

CREDS_BASE = Path(__file__).parent.parent
TAHEL_PROFILE_PATH = CREDS_BASE / "tahel_profile.md"


def check_anthropic() -> dict:
    try:
        key = os.getenv("ANTHROPIC_API_KEY", "")
        if not key:
            return {"status": "error", "message": "ANTHROPIC_API_KEY not set in .env"}
        import anthropic
        client = anthropic.Anthropic(api_key=key)
        client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=1,
            messages=[{"role": "user", "content": "ping"}],
        )
        return {"status": "ok", "message": "Connected"}
    except Exception as e:
        return {"status": "error", "message": str(e)[:120]}


def check_tavily() -> dict:
    key = os.getenv("TAVILY_API_KEY", "")
    if not key:
        return {"status": "warning", "message": "Not set — news search will be skipped"}
    if not key.startswith("tvly-"):
        return {"status": "warning", "message": "Key format looks wrong (should start with tvly-)"}
    return {"status": "ok", "message": "Key configured"}


def check_google() -> dict:
    secrets_path = CREDS_BASE / "client_secrets.json"
    token_path = CREDS_BASE / "token.json"
    if not secrets_path.exists():
        return {"status": "error", "message": "client_secrets.json not found — download OAuth credentials (Desktop app) from Google Cloud Console"}
    if not token_path.exists():
        return {"status": "warning", "message": "Not yet authorised — a browser window will open on first run to sign in with Google"}
    try:
        from google.oauth2.credentials import Credentials
        from google.auth.transport.requests import Request
        from googleapiclient.discovery import build
        scopes = [
            "https://www.googleapis.com/auth/documents",
            "https://www.googleapis.com/auth/drive",
            "https://www.googleapis.com/auth/spreadsheets",
        ]
        creds = Credentials.from_authorized_user_file(str(token_path), scopes)
        if creds.expired and creds.refresh_token:
            creds.refresh(Request())
        drive = build("drive", "v3", credentials=creds)
        drive.files().list(pageSize=1, fields="files(id)").execute()
        return {"status": "ok", "message": "Authenticated as your Google account"}
    except Exception as e:
        return {"status": "error", "message": str(e)[:120]}


def check_tahel_profile() -> dict:
    if TAHEL_PROFILE_PATH.exists():
        size = TAHEL_PROFILE_PATH.stat().st_size
        return {"status": "ok", "message": f"Loaded ({size:,} bytes)"}
    return {
        "status": "warning",
        "message": "tahel_profile.md not found — fill in tahel_questionnaire.md first",
    }


def run_all_checks() -> dict:
    checks = {
        "anthropic":     check_anthropic(),
        "tavily":        check_tavily(),
        "google":        check_google(),
        "tahel_profile": check_tahel_profile(),
    }
    ready = (
        checks["anthropic"]["status"] == "ok" and
        checks["google"]["status"] in ("ok", "warning") and  # warning = not yet signed in, OAuth triggers on first run
        checks["tahel_profile"]["status"] == "ok"
    )
    return {"checks": checks, "ready": ready}
