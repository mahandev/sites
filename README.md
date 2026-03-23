# Business Website Pipeline

Scrape Google Maps → generate a professional website → push to GitHub Pages → log the lead in Google Sheets. One command per stage.

---

## How it works

```
business_scraper_v3.py
  └─ scrapes Google Maps for a given industry + city
  └─ writes one JSON per business into business_website_data/new/

pipeline.py  ← run this to process everything
  ├─ validates each JSON (phone, name, dedup)
  ├─ generate_sites.py  → fills template.html → output/{slug}.html
  ├─ sheet_sync.py      → adds row to Google Sheet (your CRM)
  └─ deploy.py          → pushes HTML to GitHub Pages via API
```

---

## Setup

### 1. Install dependencies

```bash
python -m venv venv
source venv/bin/activate      # Windows: venv\Scripts\activate
pip install selenium requests python-dotenv gspread google-auth
```

Chrome + ChromeDriver must be installed and on your PATH for the scraper.

### 2. Create `.env`

```env
# GitHub — push sites to this repo
GITHUB_TOKEN=ghp_xxxxxxxxxxxxxxxxxxxx
GITHUB_REPO=yourusername/your-sites-repo

# Google Sheets — your lead CRM
GOOGLE_SHEET_ID=1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs74OgVE2upms
CREDENTIALS_PATH=credentials.json   # service account JSON, or omit for OAuth
```

### 3. Google Sheets credentials

**Option A — Service account (recommended for automation):**
1. Go to [Google Cloud Console](https://console.cloud.google.com) → IAM → Service Accounts → Create
2. Download the JSON key, save as `credentials.json` in this folder
3. Share your Google Sheet with the service account email

**Option B — OAuth (interactive, one-time):**
Omit `CREDENTIALS_PATH` from `.env`. On first run `gspread` will open a browser for login.

### 4. GitHub Pages

In your GitHub repo: **Settings → Pages → Source → Deploy from branch → `main` → `/ (root)`**

Your sites will be live at `https://yourusername.github.io/your-sites-repo/{slug}/`

---

## Running the pipeline

### Step 1 — Scrape businesses

```bash
python business_scraper_v3.py
```

Prompts:
```
Enter industry/category: dentists
Enter area/city: pune

Filter by website presence:
  1 - Only businesses WITHOUT a website (default)
  2 - Only businesses WITH a website
  3 - All businesses
Choose [1/2/3]: 1
```

Scraped businesses are saved to `business_website_data/new/` (one JSON per business) and `business_website_data/businesses_progress.json` (running master list).

### Step 2 — Run the pipeline

```bash
python pipeline.py
```

This processes every JSON in `business_website_data/new/` and for each business:

1. Validates (phone format, name, dedup by phone + fuzzy name match)
2. Generates `output/{slug}.html` from `template.html`
3. Adds a row to your Google Sheet with name, phone, city, demo URL, call status
4. Deploys the HTML file to GitHub Pages
5. Cleans up processed JSON (default: deletes it so no JSON files pile up)

Progress is logged to `pipeline.log` and the terminal.

### JSON cleanup behavior

By default, processed JSON files are deleted immediately.

Optional environment variables:

```env
# delete (default): remove JSON after processing
# archive: move JSON to processed/
PIPELINE_JSON_CLEANUP=delete

# only used when PIPELINE_JSON_CLEANUP=archive
# delete archived JSON older than this many days
PIPELINE_PROCESSED_KEEP_DAYS=7
```

---

## Automating with cron

Run the full pipeline automatically on a schedule.

### macOS / Linux

```bash
crontab -e
```

Add one of these:

```cron
# Run pipeline every day at 8am
0 8 * * * cd /path/to/gh && /path/to/gh/venv/bin/python pipeline.py >> pipeline.log 2>&1

# Run pipeline every 2 hours
0 */2 * * * cd /path/to/gh && /path/to/gh/venv/bin/python pipeline.py >> pipeline.log 2>&1
```

Replace `/path/to/gh` with the absolute path to this folder (get it with `pwd`).

### Windows Task Scheduler

1. Open Task Scheduler → Create Basic Task
2. Trigger: Daily (or your preferred schedule)
3. Action: Start a program
   - Program: `C:\path\to\gh\venv\Scripts\python.exe`
   - Arguments: `pipeline.py`
   - Start in: `C:\path\to\gh\`

---

## Running stages individually

### Generate sites only (no scrape, no deploy)

```bash
python generate_sites.py
```

Reads `business_website_data/businesses_progress.json`, writes all HTML files to `output/`.

### Deploy all files in `output/` to GitHub Pages

```bash
python deploy.py --all
```

### Deploy one manually edited HTML file

```bash
python deploy.py --file output/your-page.html
```

Optional custom commit message:

```bash
python deploy.py --file output/your-page.html --message "Manual HTML fix"
```

### Sync a single business to Google Sheets

```python
from sheet_sync import sync_business

business = {
    "name": "Sharma & Associates",
    "category": "Tax Consultant",
    "phone": "+91 98765 43210",
    "full_address": "Kothrud, Pune, Maharashtra 411038"
}
status, message = sync_business(business, github_username="yourusername")
print(status, message)
```

---

## Directory layout

```
gh/
├── business_scraper_v3.py  # Stage 1: scrape Google Maps
├── pipeline.py             # Stage 2: orchestrate everything
├── generate_sites.py       # Fills template.html with business data
├── deploy.py               # Pushes HTML to GitHub via API
├── sheet_sync.py           # Adds leads to Google Sheets
├── template.html           # Website design with {{TOKEN}} placeholders
├── utils.py                # Shared phone + city helpers
│
├── business_website_data/
│   ├── new/                # Scraper drops JSONs here; pipeline picks them up
│   ├── businesses_progress.json  # Master running list of all scraped data
│   └── images/             # (unused — photo URLs stored, not downloaded)
│
├── output/                 # Generated HTML files ready to deploy
├── processed/              # JSONs moved here after pipeline processes them
│
├── pipeline.log            # Full pipeline run log
├── pipeline_state.json     # Pipeline run metadata
└── .env                    # Your secrets (never commit this)
```

---

## Environment variables reference

| Variable | Required | Description |
|---|---|---|
| `GITHUB_TOKEN` | Yes | Personal access token with `repo` scope |
| `GITHUB_REPO` | Yes | `username/repo-name` of your GitHub Pages repo |
| `GOOGLE_SHEET_ID` | Yes | ID from the Google Sheet URL |
| `CREDENTIALS_PATH` | No | Path to service account JSON (default: `credentials.json`) |

---

## Troubleshooting

**Pipeline generates 0 sites**
- Check that `business_website_data/new/` has JSON files. The pipeline only reads from `new/`, not from `businesses_progress.json`.
- Check `pipeline.log` — look for `SKIP` lines with reasons.

**GitHub deploy fails with 404**
- Confirm `GITHUB_REPO` in `.env` matches the exact `username/repo` — case-sensitive.
- Confirm the token has `repo` (not just `public_repo`) scope.

**Google Sheets error: GOOGLE_SHEET_ID not set**
- Check `.env` exists and `load_dotenv()` is running before the error. Make sure there are no trailing spaces in the value.

**Scraper finds no businesses / Chrome crashes**
- Update ChromeDriver to match your installed Chrome version: `chromedriver --version` vs `google-chrome --version`.
- Google Maps selectors change occasionally — check `business_scraper_v3.log` for the exact error.

**Duplicate businesses keep appearing in the sheet**
- The sheet de-duplication is keyed on the last 10 digits of the phone number (`Phone Key` column). If a business has no phone or a malformed one, it will be added each run. Fix the phone in the JSON before re-running.
