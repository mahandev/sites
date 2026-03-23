import os
import re
from typing import Dict, List, Tuple

from utils import normalize_phone, extract_city

try:
    from dotenv import load_dotenv
except ImportError:
    def load_dotenv():
        return False

load_dotenv()

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

HEADERS = [
    "Business Name",
    "Category",
    "Phone",
    "Address",
    "City",
    "Demo URL",
    "Call Status",
    "Deal Status",
    "Notes",
    "Phone Key",
]

CALL_STATUS_OPTIONS = ["Not Called", "Called", "Follow Up", "No Answer", "Wrong Number"]
DEAL_STATUS_OPTIONS = ["New Lead", "Interested", "Negotiating", "Closed Won", "Rejected", "Not Relevant"]


def get_sheet():
    """Connect to Google Sheet. Tries service account first, falls back to OAuth."""
    try:
        import gspread
        from google.oauth2.service_account import Credentials
    except ImportError as exc:
        raise RuntimeError(
            "Google Sheets dependencies missing. Install: pip install gspread google-auth"
        ) from exc

    creds_path = os.getenv("CREDENTIALS_PATH", "credentials.json")
    sheet_id = os.getenv("GOOGLE_SHEET_ID")

    if not sheet_id:
        raise ValueError("GOOGLE_SHEET_ID not set in .env")

    if os.path.exists(creds_path):
        creds = Credentials.from_service_account_file(creds_path, scopes=SCOPES)
        gc = gspread.authorize(creds)
    else:
        gc = gspread.oauth()

    spreadsheet = gc.open_by_key(sheet_id)

    try:
        ws = spreadsheet.worksheet("Leads")
    except gspread.WorksheetNotFound:
        ws = spreadsheet.add_worksheet(title="Leads", rows=1000, cols=10)
        ws.append_row(HEADERS)
        ws.format("A1:J1", {"textFormat": {"bold": True}})

    return ws




def make_demo_url(business_name: str, github_username: str) -> str:
    """Generate the expected GitHub Pages demo URL for this business."""
    slug = re.sub(r"[^a-z0-9\s-]", "", (business_name or "").lower())
    slug = re.sub(r"\s+", "-", slug.strip())
    slug = re.sub(r"-+", "-", slug)
    repo = (os.getenv("GITHUB_REPO", "").split("/")[-1] or "sites").strip()
    username = (github_username or "").strip() or "username"
    return f"https://{username}.github.io/{repo}/{slug}.html"


def sync_business(business: Dict, github_username: str = "") -> Tuple[str, str]:
    """
    Add a business to the Google Sheet if not already present.
    Returns: ("added" | "duplicate" | "error", message)
    """
    try:
        ws = get_sheet()
    except Exception as exc:
        return "error", str(exc)

    phone_key = normalize_phone(business.get("phone", ""))

    try:
        all_values = ws.get_all_values()
    except Exception as exc:
        return "error", f"Could not read sheet: {exc}"

    if len(all_values) > 950:
        try:
            ws.add_rows(500)
        except Exception as exc:
            return "error", f"Could not expand sheet rows: {exc}"

    existing_phone_keys = [row[9] if len(row) > 9 else "" for row in all_values[1:]]

    if phone_key and phone_key in existing_phone_keys:
        return "duplicate", f"Phone {phone_key} already in sheet"

    name = business.get("name", "")
    category = business.get("category", "")
    phone = business.get("phone", "")
    address = business.get("full_address") or business.get("address", "") or ""
    city = extract_city(address)
    demo_url = make_demo_url(name, github_username)

    row = [
        name,
        category,
        phone,
        address,
        city,
        demo_url,
        "Not Called",
        "New Lead",
        "",
        phone_key,
    ]

    try:
        ws.append_row(row, value_input_option="USER_ENTERED")
        return "added", f"Added: {name}"
    except Exception as exc:
        return "error", str(exc)


def bulk_sync(businesses: List[Dict], github_username: str = "") -> Dict:
    """Sync a list of businesses. Returns summary dict."""
    results = {"added": 0, "duplicate": 0, "error": 0, "errors": []}
    for business in businesses:
        status, msg = sync_business(business, github_username)
        results[status] += 1
        if status == "error":
            results["errors"].append(msg)
    return results
