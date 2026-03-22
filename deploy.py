import base64
import os
import time
from typing import List, Tuple

try:
    import requests
except ImportError:
    requests = None

try:
    from dotenv import load_dotenv
except ImportError:
    def load_dotenv():
        return False

load_dotenv()

GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
GITHUB_REPO = os.getenv("GITHUB_REPO")
BRANCH = "main"


def get_headers():
    return {
        "Authorization": f"token {GITHUB_TOKEN}",
        "Accept": "application/vnd.github.v3+json",
    }


def file_exists_on_github(filepath: str):
    """Check if a file already exists in the repo and return its SHA if present."""
    if requests is None:
        return None
    if not GITHUB_REPO:
        return None
    url = f"https://api.github.com/repos/{GITHUB_REPO}/contents/{filepath}"
    response = requests.get(url, headers=get_headers(), timeout=30)
    if response.status_code == 200:
        return response.json().get("sha")
    return None


def _upload_with_payload(remote_path: str, payload: dict):
    if requests is None:
        return None
    url = f"https://api.github.com/repos/{GITHUB_REPO}/contents/{remote_path}"
    return requests.put(url, headers=get_headers(), json=payload, timeout=30)


def deploy_file(local_path: str, remote_path: str, commit_message: str = None) -> bool:
    """
    Upload or update a single file on GitHub.
    Returns True on success, False on failure.
    """
    if not GITHUB_TOKEN or not GITHUB_REPO:
        print("ERROR: GITHUB_TOKEN or GITHUB_REPO not set in .env")
        return False
    if requests is None:
        print("ERROR: requests is not installed. Install: pip install requests")
        return False

    with open(local_path, "rb") as file_obj:
        content = base64.b64encode(file_obj.read()).decode("utf-8")

    existing_sha = file_exists_on_github(remote_path)
    slug = os.path.basename(local_path).replace(".html", "")
    message = commit_message or f"Add site: {slug}"

    payload = {
        "message": message,
        "content": content,
        "branch": BRANCH,
    }
    if existing_sha:
        payload["sha"] = existing_sha

    response = _upload_with_payload(remote_path, payload)

    if response is not None and response.status_code in (200, 201):
        return True

    if response is not None and response.status_code == 409:
        refreshed_sha = file_exists_on_github(remote_path)
        if refreshed_sha:
            payload["sha"] = refreshed_sha
            retry_response = _upload_with_payload(remote_path, payload)
            if retry_response is None:
                print("GitHub deploy error: requests unavailable during retry")
                return False
            if retry_response.status_code in (200, 201):
                return True
            print(f"GitHub deploy error {retry_response.status_code}: {retry_response.json().get('message')}")
            return False

    if response is not None and response.status_code == 404:
        print("Repo not found - check GITHUB_REPO in .env")
        return False

    if response is None:
        print("GitHub deploy error: request client unavailable")
        return False

    try:
        message = response.json().get("message")
    except Exception:
        message = response.text
    print(f"GitHub deploy error {response.status_code}: {message}")
    return False


def deploy_all_new(output_dir: str = "output", remote_prefix: str = "") -> Tuple[List[str], List[str]]:
    """
    Deploy all HTML files in output directory.
    Returns (deployed, failed) filename lists.
    """
    deployed = []
    failed = []

    files = [f for f in os.listdir(output_dir) if f.endswith(".html")]
    throttle = len(files) > 20

    for filename in files:
        local_path = os.path.join(output_dir, filename)
        remote_path = f"{remote_prefix}{filename}" if remote_prefix else filename

        success = deploy_file(local_path, remote_path)
        if success:
            deployed.append(filename)
            print(f"Deployed: {filename}")
        else:
            failed.append(filename)
            print(f"Failed:   {filename}")

        if throttle:
            time.sleep(0.5)

    return deployed, failed
