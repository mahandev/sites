# Pipeline Fixes Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Eliminate code duplication, wire the scraper output directly into the pipeline, and make the website filter consistent end-to-end.

**Architecture:** Extract shared logic into `utils.py`; have the scraper write one JSON per business into `business_website_data/new/`; remove the redundant `has_website` guard from the pipeline validator; replace the ever-growing `processed_files` list with a filesystem existence check; use real scraped services in site generation when available.

**Tech Stack:** Python 3, Selenium, gspread, requests, python-dotenv

---

## File Map

| File | Change |
|---|---|
| `utils.py` | **Create** — shared `normalize_phone()` and `extract_city()` |
| `business_scraper_v3.py` | **Modify** — write one JSON per business to `business_website_data/new/` |
| `pipeline.py` | **Modify** — remove `has_website` guard; drop `processed_files` list; import from `utils` |
| `generate_sites.py` | **Modify** — prefer real `service_options` over hardcoded map; import `extract_city` from `utils` |
| `sheet_sync.py` | **Modify** — import `extract_city` and `make_phone_key` from `utils` |

---

## Task 1: Create `utils.py` with shared helpers

**Files:**
- Create: `utils.py`

- [ ] **Step 1.1 — Write `utils.py`**

```python
# utils.py
import re


def normalize_phone(phone: str) -> str:
    """Return last 10 digits of an Indian phone number."""
    digits = re.sub(r"\D", "", phone or "")
    if digits.startswith("91") and len(digits) >= 12:
        digits = digits[2:]
    elif digits.startswith("0") and len(digits) >= 11:
        digits = digits[1:]
    return digits[-10:] if len(digits) >= 10 else digits


KNOWN_CITIES = ["pune", "mumbai", "nashik", "nagpur", "aurangabad", "thane"]


def extract_city(full_address: str) -> str:
    """Extract city name from a comma-separated address string."""
    full_address = full_address or ""
    for part in full_address.split(","):
        if any(c in part.lower() for c in KNOWN_CITIES):
            return part.strip()
    parts = [p.strip() for p in full_address.split(",") if p.strip()]
    if len(parts) >= 3:
        return parts[-3]
    return parts[-1] if parts else ""
```

- [ ] **Step 1.2 — Verify it imports cleanly**

```bash
python -c "from utils import normalize_phone, extract_city; print(normalize_phone('+91 98765 43210')); print(extract_city('Kothrud, Pune, Maharashtra 411038'))"
```

Expected output:
```
9876543210
Pune
```

- [ ] **Step 1.3 — Commit**

```bash
git add utils.py
git commit -m "feat: add shared utils for phone normalization and city extraction"
```

---

## Task 2: Update `sheet_sync.py` and `generate_sites.py` to use `utils`

**Files:**
- Modify: `sheet_sync.py` — replace `make_phone_key` and `extract_city` with imports
- Modify: `generate_sites.py` — replace `extract_location` city logic with `extract_city` import

### 2a — `sheet_sync.py`

- [ ] **Step 2a.1 — Replace duplicated helpers**

In `sheet_sync.py`, remove the `extract_city` and `make_phone_key` function bodies and replace with:

```python
from utils import normalize_phone, extract_city

# replace make_phone_key usages with normalize_phone
```

Change line ~82 (`make_phone_key` function) — delete the function body and add the import at the top. Update all call sites from `make_phone_key(...)` to `normalize_phone(...)`.

- [ ] **Step 2a.2 — Verify no import errors**

```bash
python -c "from sheet_sync import sync_business; print('OK')"
```

Expected: `OK`

### 2b — `generate_sites.py`

- [ ] **Step 2b.1 — Import `extract_city` from utils**

At the top of `generate_sites.py`, add:
```python
from utils import extract_city
```

- [ ] **Step 2b.2 — Update `extract_location` to use shared city logic**

```python
def extract_location(full_address):
    parts = [p.strip() for p in (full_address or "").split(",") if p.strip()]
    area = parts[0] if parts else ""
    city = extract_city(full_address)
    return area, city
```

- [ ] **Step 2b.3 — Verify**

```bash
python -c "from generate_sites import extract_location; print(extract_location('Kothrud, Pune, Maharashtra 411038'))"
```

Expected: `('Kothrud', 'Pune')`

- [ ] **Step 2c — Commit**

```bash
git add sheet_sync.py generate_sites.py
git commit -m "refactor: deduplicate phone normalization and city extraction via utils"
```

---

## Task 3: Update `pipeline.py` — remove `has_website` guard and fix state tracking

**Files:**
- Modify: `pipeline.py`

The pipeline's `validate_business` function rejects any business that has a website (line ~99). This conflicts with the scraper's `filter_mode` — if you run the scraper in `with_website` or `all` mode, every record gets rejected before a site is generated. Remove the guard and let the scraper decide.

Also replace the `processed_files` list (grows forever) with a simple check: if the source file no longer exists in `new/` (it's been moved to `processed/`), it's already done.

- [ ] **Step 3.1 — Remove `has_website` check from `validate_business`**

In `pipeline.py`, delete these lines from `validate_business`:
```python
if business.get("has_website") or business.get("website"):
    errors.append("Business already has a website - skipping")
```

- [ ] **Step 3.2 — Remove `processed_files` from `load_state` default and tracking**

Replace the `load_state` default:
```python
return {
    "last_run": None,
    "total_generated": 0,
    "total_skipped": 0,
}
```

Remove the `if filename in state.get("processed_files", []):` early-continue block in `run()` — it's no longer needed because `_move_to_processed` already removes the file from `new/`.

Remove all `state["processed_files"].append(filename)` lines throughout `run()`.

- [ ] **Step 3.3 — Import `normalize_phone` from utils**

Replace the inline `make_identity` phone-digit logic with:
```python
from utils import normalize_phone

def make_identity(business):
    return normalize_phone(business.get("phone", "") or "")
```

- [ ] **Step 3.4 — Verify pipeline imports cleanly**

```bash
python -c "from pipeline import run; print('OK')"
```

Expected: `OK`

- [ ] **Step 3.5 — Commit**

```bash
git add pipeline.py
git commit -m "fix: remove has_website guard from pipeline validator; simplify state tracking"
```

---

## Task 4: Use real scraped services in `generate_sites.py`

**Files:**
- Modify: `generate_sites.py`

Right now `build_services_html` always uses the hardcoded `SERVICES_MAP`. The scraper collects `service_options` and `offerings` from the About tab — use those when they exist, fall back to the map only when empty.

- [ ] **Step 4.1 — Update `build_services_html` to accept real data**

```python
def build_services_html(category, scraped_services=None):
    """Use scraped services when available, else fall back to SERVICES_MAP."""
    if scraped_services:
        services = [(s, "") for s in scraped_services[:5]]
    else:
        services = get_services(category)

    html = ""
    for i, (name, desc) in enumerate(services, 1):
        html += (
            "\n        <div class=\"service-item reveal\">"
            f"\n          <span class=\"service-num\">0{i}</span>"
            "\n          <div>"
            f"\n            <p class=\"service-name\">{escape(name)}</p>"
            + (f"\n            <p class=\"service-desc\">{escape(desc)}</p>" if desc else "")
            + "\n          </div>"
            "\n        </div>"
        )
    return html
```

- [ ] **Step 4.2 — Pass real services from `generate_one`**

In `generate_one`, replace:
```python
services_list_html = build_services_html(category)
```
with:
```python
scraped = (b.get("service_options") or []) + (b.get("offerings") or [])
services_list_html = build_services_html(category, scraped_services=scraped or None)
```

- [ ] **Step 4.3 — Verify**

```bash
python -c "
from generate_sites import build_services_html
print(build_services_html('gym', ['Cardio Zone', 'Weight Training', 'Yoga Classes']))
"
```

Expected: HTML with `Cardio Zone`, `Weight Training`, `Yoga Classes` as service names.

- [ ] **Step 4.4 — Commit**

```bash
git add generate_sites.py
git commit -m "feat: use real scraped service_options in site generation, fall back to defaults"
```

---

## Task 5: Wire scraper output directly into `business_website_data/new/`

**Files:**
- Modify: `business_scraper_v3.py`

Currently the scraper writes everything to a single `businesses_progress.json`. The pipeline expects individual JSON files in `business_website_data/new/`. Add a step after each successful scrape to write `new/{slug}.json`.

- [ ] **Step 5.1 — Add `_write_to_new` method**

Add this method to `BusinessWebsiteDataScraper`:

```python
def _write_to_new(self, business):
    """Write individual business JSON to new/ for pipeline pickup."""
    import re
    slug = re.sub(r"[^a-z0-9]+", "-", (business.get("name") or "unknown").lower()).strip("-")
    new_dir = os.path.join(self.output_dir, "new")
    os.makedirs(new_dir, exist_ok=True)
    path = os.path.join(new_dir, f"{slug}.json")
    # avoid overwrite collisions
    counter = 1
    while os.path.exists(path):
        path = os.path.join(new_dir, f"{slug}-{counter}.json")
        counter += 1
    with open(path, "w", encoding="utf-8") as f:
        json.dump(business, f, indent=2, ensure_ascii=False)
    logging.info(f"  Written to new/: {os.path.basename(path)}")
```

- [ ] **Step 5.2 — Call it in `run()` after a successful scrape**

In `run()`, after `self.businesses_data.append(business)`:
```python
self._write_to_new(business)
```

- [ ] **Step 5.3 — Verify a dry run creates the file**

Run the scraper for 1 business manually or inspect that the file appears in `business_website_data/new/` after a scrape. Check the JSON is valid:

```bash
python -c "import json; f=open('business_website_data/new/some-business.json'); print(json.load(f).get('name'))"
```

- [ ] **Step 5.4 — Commit**

```bash
git add business_scraper_v3.py
git commit -m "feat: write per-business JSON to new/ dir so pipeline auto-picks up scrape results"
```

---

## Verification — full end-to-end smoke test

- [ ] **Step 6.1 — Run the whole pipeline against the existing progress JSON**

Copy one entry from `business_website_data/businesses_progress.json` into `business_website_data/new/test-biz.json` and run:

```bash
python pipeline.py
```

Expected log output includes:
```
OK    Generated: test-biz.html
OK    Sheet synced: ...
OK    Deployed to GitHub: test-biz.html
Pipeline complete. Generated: 1, Skipped: 0, Errors: 0
```

- [ ] **Step 6.2 — Confirm no leftover file in `new/`**

```bash
ls business_website_data/new/
```

Expected: empty (file moved to `processed/`)

- [ ] **Step 6.3 — Final commit if anything was missed**

```bash
git status
git add -p  # stage only intentional changes
git commit -m "chore: post-fix cleanup"
```
