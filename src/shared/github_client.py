"""GitHub REST-API client — push files to the openwealthlab website repo."""

from __future__ import annotations

import base64
import logging

import httpx

from config import settings

log = logging.getLogger(__name__)

_API = "https://api.github.com"


def _headers() -> dict[str, str]:
    return {
        "Authorization": f"Bearer {settings.OWL_GITHUB_TOKEN}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }


def push_file(path: str, content: str, message: str, branch: str = "main") -> bool:
    """Create or update a file in the openwealthlab repo.

    Returns True if the file was created/updated, False if it already
    existed with the same content.
    """
    repo = settings.OWL_GITHUB_REPO
    url = f"{_API}/repos/{repo}/contents/{path}"

    # Check if the file already exists
    sha: str | None = None
    resp = httpx.get(url, headers=_headers(), params={"ref": branch}, timeout=15)
    if resp.status_code == 200:
        existing = resp.json()
        sha = existing["sha"]
        existing_content = base64.b64decode(existing["content"]).decode()
        if existing_content.strip() == content.strip():
            log.info("File unchanged, skipping: %s", path)
            return False

    body: dict = {
        "message": message,
        "content": base64.b64encode(content.encode()).decode(),
        "branch": branch,
    }
    if sha:
        body["sha"] = sha

    resp = httpx.put(url, json=body, headers=_headers(), timeout=15)
    resp.raise_for_status()
    log.info("Pushed %s to %s", path, repo)
    return True
