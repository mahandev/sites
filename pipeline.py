import json
import logging
import os
import re
import shutil
from datetime import datetime
from datetime import timedelta
from difflib import SequenceMatcher
from pathlib import Path

try:
    from dotenv import load_dotenv
except ImportError:
    def load_dotenv():
        return False

from deploy import deploy_file
from generate_sites import generate_one, make_slug
from sheet_sync import sync_business
from utils import normalize_phone

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] %(levelname)-5s %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[
        logging.FileHandler("pipeline.log"),
        logging.StreamHandler(),
    ],
)
log = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parent
NEW_DIR = BASE_DIR / "business_website_data/new"
PROCESSED_DIR = BASE_DIR / "processed"
MASTER_JSON = BASE_DIR / "business_website_data/pipeline_master.json"
OUTPUT_DIR = BASE_DIR / "output"
STATE_FILE = BASE_DIR / "pipeline_state.json"
TEMPLATE_FILE = BASE_DIR / "template.html"

TEMPLATES_DIR = BASE_DIR / "templates"

REQUIRED_FIELDS = ["name", "phone", "category"]

# Keywords used to auto-detect template type from category when not explicitly set
_TEMPLATE_KEYWORDS = {
    "clinic":     ["clinic", "diagnostic", "lab", "hospital", "pathology", "medical", "health", "doctor", "physician", "dental", "dentist", "eye", "ortho"],
    "coaching":   ["coaching", "tuition", "institute", "academy", "classes", "education", "school", "tutorial", "training"],
    "interior":   ["interior", "decorator", "design studio", "furnishing", "architecture", "architect"],
    "wedding":    ["wedding", "photographer", "photography", "videographer", "videography", "photo studio", "event photo"],
    "caterer":    ["caterer", "catering", "food", "tiffin", "cloud kitchen", "canteen", "mess", "meals", "dabba"],
    "realestate": ["real estate", "property", "realty", "builder", "developer", "broker", "housing", "plot", "flat"],
    "export":     ["export", "import", "trading", "trade", "wholesale", "manufacturer", "supplier", "distributor"],
}

# Cache loaded template strings so each file is read only once per pipeline run
_template_cache: dict = {}


def _resolve_template_type(business: dict) -> str:
    """Return the template key for this business: explicit > category keywords > 'general'."""
    explicit = (business.get("template") or "").strip().lower()
    if explicit and explicit != "general":
        return explicit
    category = (business.get("category") or "").lower()
    for key, keywords in _TEMPLATE_KEYWORDS.items():
        if any(kw in category for kw in keywords):
            return key
    return "general"


def _load_template(template_type: str) -> str:
    """Load and cache a template file with safe fallbacks."""
    if template_type in _template_cache:
        return _template_cache[template_type]

    candidate = TEMPLATES_DIR / f"{template_type}.html"
    if candidate.exists():
        text = candidate.read_text(encoding="utf-8")
        log.debug(f"Loaded template: {candidate}")
    else:
        fallback = None
        for option in [TEMPLATES_DIR / "general.html", TEMPLATE_FILE]:
            if option.exists():
                fallback = option
                break
        if fallback is None:
            available = sorted(p.name for p in TEMPLATES_DIR.glob("*.html"))
            if available:
                fallback = TEMPLATES_DIR / available[0]
                log.warning(
                    f"Template '{template_type}.html' not found, using '{fallback.name}' as fallback"
                )
            else:
                raise FileNotFoundError(
                    "No template files found. Add templates/*.html or template.html"
                )
        else:
            log.warning(
                f"Template '{template_type}.html' not found, using '{fallback.name}' as fallback"
            )
        text = fallback.read_text(encoding="utf-8")

    _template_cache[template_type] = text
    return text


def load_state():
    if STATE_FILE.exists():
        try:
            return json.loads(STATE_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {
        "last_run": None,
        "total_generated": 0,
        "total_skipped": 0,
    }


def save_state(state):
    STATE_FILE.write_text(json.dumps(state, indent=2), encoding="utf-8")


def load_master():
    if MASTER_JSON.exists():
        try:
            return json.loads(MASTER_JSON.read_text(encoding="utf-8"))
        except Exception:
            return []
    return []


def save_master(businesses):
    MASTER_JSON.parent.mkdir(parents=True, exist_ok=True)
    MASTER_JSON.write_text(json.dumps(businesses, indent=2, ensure_ascii=False), encoding="utf-8")


def make_identity(business):
    return normalize_phone(business.get("phone", "") or "")


def names_are_similar(name_a, name_b, threshold=0.85):
    a_clean = re.sub(r"[^a-z0-9]", "", (name_a or "").lower())
    b_clean = re.sub(r"[^a-z0-9]", "", (name_b or "").lower())
    if not a_clean or not b_clean:
        return False
    return SequenceMatcher(None, a_clean, b_clean).ratio() >= threshold


def validate_business(business, filename, existing_ids, existing_names):
    errors = []

    for field in REQUIRED_FIELDS:
        if not business.get(field):
            errors.append(f"Missing required field: {field}")

    phone_digits = re.sub(r"\D", "", business.get("phone", "") or "")
    if phone_digits.startswith("91"):
        phone_digits = phone_digits[2:]
    elif phone_digits.startswith("0"):
        phone_digits = phone_digits[1:]
    if len(phone_digits) != 10:
        errors.append(f"Invalid phone number: {business.get('phone')}")

    if len((business.get("name") or "").strip()) < 3:
        errors.append("Business name too short")

    if re.match(r"^[\d\s\-\.]+$", business.get("name", "") or ""):
        errors.append("Business name looks invalid (all numbers/symbols)")

    identity = make_identity(business)
    if identity and identity in existing_ids:
        errors.append(f"Duplicate phone: {identity}")

    for existing_name in existing_names:
        if names_are_similar(business.get("name", ""), existing_name):
            errors.append(f"Near-duplicate name: '{business.get('name', '')}' ~ '{existing_name}'")
            break

    return errors


def _load_business_from_file(json_file):
    raw = json.loads(json_file.read_text(encoding="utf-8"))
    if isinstance(raw, list):
        if not raw:
            raise ValueError("Empty JSON array")
        raw = raw[0]
    if not isinstance(raw, dict):
        raise ValueError("JSON root must be an object or a non-empty array")
    return raw


def _move_to_processed(path_obj):
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    destination = PROCESSED_DIR / f"{timestamp}_{path_obj.name}"
    shutil.move(str(path_obj), str(destination))


def _get_json_cleanup_mode() -> str:
    """How to handle processed JSON files: delete (default) or archive."""
    mode = (os.getenv("PIPELINE_JSON_CLEANUP", "delete") or "delete").strip().lower()
    return mode if mode in {"delete", "archive"} else "delete"


def _finalize_json(path_obj: Path):
    """Cleanup current JSON after processing based on configured mode."""
    if _get_json_cleanup_mode() == "archive":
        _move_to_processed(path_obj)
        return
    try:
        path_obj.unlink(missing_ok=True)
    except Exception as exc:
        log.warning(f"WARN  Could not delete processed JSON {path_obj.name}: {exc}")


def _cleanup_archived_jsons():
    """Delete old archived JSON files after configured retention period."""
    if _get_json_cleanup_mode() != "archive":
        return

    keep_days_raw = (os.getenv("PIPELINE_PROCESSED_KEEP_DAYS", "7") or "7").strip()
    try:
        keep_days = int(keep_days_raw)
    except ValueError:
        keep_days = 7

    if keep_days < 0:
        return

    cutoff = datetime.now() - timedelta(days=keep_days)
    removed = 0
    for path_obj in PROCESSED_DIR.glob("*.json"):
        try:
            modified_at = datetime.fromtimestamp(path_obj.stat().st_mtime)
            if modified_at < cutoff:
                path_obj.unlink()
                removed += 1
        except Exception as exc:
            log.warning(f"WARN  Could not cleanup archived JSON {path_obj.name}: {exc}")

    if removed:
        log.info(f"OK    Cleaned archived JSON files: {removed}")


def run():
    log.info("=" * 60)
    log.info("Pipeline started")

    NEW_DIR.mkdir(parents=True, exist_ok=True)
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    state = load_state()
    master = load_master()

    existing_ids = {make_identity(b) for b in master if make_identity(b)}
    existing_names = [b.get("name", "") for b in master if b.get("name")]

    new_files = sorted(NEW_DIR.glob("*.json"))
    log.info(f"Found {len(new_files)} new JSON files in {NEW_DIR}/")

    github_user = (os.getenv("GITHUB_REPO", "/").split("/")[0] or "").strip()

    stats = {"generated": 0, "skipped": 0, "errors": 0}

    for json_file in new_files:
        filename = json_file.name

        try:
            business = _load_business_from_file(json_file)
        except Exception as exc:
            log.error(f"ERROR Validation failed for {filename}: {exc}")
            stats["errors"] += 1
            state["total_skipped"] = state.get("total_skipped", 0) + 1
            save_state(state)
            _finalize_json(json_file)
            continue

        errors = validate_business(business, filename, existing_ids, existing_names)
        if errors:
            log.warning(f"SKIP  {filename}: {'; '.join(errors)}")
            stats["skipped"] += 1
            state["total_skipped"] = state.get("total_skipped", 0) + 1
            save_state(state)
            _finalize_json(json_file)
            continue

        slug = make_slug(business["name"])
        out_path = OUTPUT_DIR / f"{slug}.html"

        try:
            tpl_type = _resolve_template_type(business)
            template_str = _load_template(tpl_type)
            html = generate_one(business, template_str)
            out_path.write_text(html, encoding="utf-8")
            log.info(f"OK    Generated: {out_path.name} [{tpl_type}]")
        except Exception as exc:
            log.error(f"ERROR Site generation failed for {filename}: {exc}")
            stats["errors"] += 1
            state["total_skipped"] = state.get("total_skipped", 0) + 1
            save_state(state)
            _finalize_json(json_file)
            continue

        try:
            status, message = sync_business(business, github_username=github_user)
            if status == "added":
                log.info(f"OK    Sheet synced: {business['name']}")
            elif status == "duplicate":
                log.info(f"SKIP  Sheet duplicate: {business['name']}")
            else:
                log.warning(f"WARN  Sheet sync failed: {message}")
        except Exception as exc:
            log.warning(f"WARN  Sheet sync error (non-fatal): {exc}")

        try:
            deployed = deploy_file(str(out_path), f"{slug}.html")
            if deployed:
                log.info(f"OK    Deployed to GitHub: {slug}.html")
            else:
                log.warning(f"WARN  GitHub deploy failed for {slug}.html (non-fatal)")
        except Exception as exc:
            log.warning(f"WARN  Deploy error (non-fatal): {exc}")

        master.append(business)
        business_id = make_identity(business)
        if business_id:
            existing_ids.add(business_id)
        existing_names.append(business.get("name", ""))

        _finalize_json(json_file)

        state["total_generated"] = state.get("total_generated", 0) + 1
        stats["generated"] += 1
        save_state(state)

    save_master(master)
    _cleanup_archived_jsons()
    state["last_run"] = datetime.now().isoformat()
    save_state(state)

    log.info(
        "Pipeline complete. "
        f"Generated: {stats['generated']}, "
        f"Skipped: {stats['skipped']}, "
        f"Errors: {stats['errors']}"
    )
    log.info("=" * 60)


if __name__ == "__main__":
    run()
