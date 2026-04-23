from __future__ import annotations

import json
import os


def _require(name: str) -> str:
    val = os.environ.get(name)
    if not val:
        raise EnvironmentError(f"Missing required env var: {name}")
    return val


# ── Pipeline environment ────────────────────────────────────────────
PIPELINE_ENV: str = os.environ.get("PIPELINE_ENV", "dev")

# ── Trade Republic ──────────────────────────────────────────────────
TR_PHONE_NUMBER: str = os.environ.get("TR_PHONE_NUMBER", "")
TR_PIN: str = os.environ.get("TR_PIN", "")

# ── Firestore ───────────────────────────────────────────────────────
FIRESTORE_PROJECT_ID = "openwealthlab"
FIRESTORE_DATABASE = "openwealthlab"
FIRESTORE_BASE_URL = (
    f"https://firestore.googleapis.com/v1/projects/"
    f"{FIRESTORE_PROJECT_ID}/databases/{FIRESTORE_DATABASE}/documents"
)
FIRESTORE_COLLECTION = (
    "dividend_payments" if PIPELINE_ENV == "prod" else "dev_dividend_payments"
)
FIRESTORE_MAPPING_COLLECTION = (
    "instrument_mappings" if PIPELINE_ENV == "prod" else "dev_instrument_mappings"
)


def get_service_account_info() -> dict:
    raw = _require("FIREBASE_SERVICE_ACCOUNT_KEY")
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        # Might be a file path
        with open(raw) as f:
            return json.load(f)


# ── GitHub ──────────────────────────────────────────────────────────
OWL_GITHUB_TOKEN: str = os.environ.get("OWL_GITHUB_TOKEN", "")
OWL_GITHUB_REPO = "derHeinzer/openwealthlab"
OWL_CONTENT_PATH = "src/content/dividend-logs"

# ── Gemini (Google AI Studio) ──────────────────────────────────────
GEMINI_API_KEY: str = os.environ.get("GEMINI_API_KEY", "")
