"""Firestore REST-API client (no SDK)."""

from __future__ import annotations

import logging
from typing import Any

import httpx

from config import settings
from src.shared.auth import get_access_token

log = logging.getLogger(__name__)


def _headers() -> dict[str, str]:
    return {
        "Authorization": f"Bearer {get_access_token()}",
        "Content-Type": "application/json",
    }


def _to_firestore_value(val: Any) -> dict:
    if isinstance(val, bool):
        return {"booleanValue": val}
    if isinstance(val, int):
        return {"integerValue": str(val)}
    if isinstance(val, float):
        return {"doubleValue": val}
    if isinstance(val, str):
        return {"stringValue": val}
    raise TypeError(f"Unsupported Firestore value type: {type(val)}")


def _from_firestore_value(fv: dict) -> Any:
    if "stringValue" in fv:
        return fv["stringValue"]
    if "integerValue" in fv:
        return int(fv["integerValue"])
    if "doubleValue" in fv:
        return fv["doubleValue"]
    if "booleanValue" in fv:
        return fv["booleanValue"]
    if "nullValue" in fv:
        return None
    return str(fv)


def _doc_url(doc_id: str | None = None, collection: str | None = None) -> str:
    coll = collection or settings.FIRESTORE_COLLECTION
    base = f"{settings.FIRESTORE_BASE_URL}/{coll}"
    if doc_id:
        return f"{base}/{doc_id}"
    return base


# ── Public API ──────────────────────────────────────────────────────


def create_document(data: dict, doc_id: str | None = None, *, collection: str | None = None) -> dict:
    """Create a Firestore document.  Returns the created document."""
    fields = {k: _to_firestore_value(v) for k, v in data.items()}
    body: dict[str, Any] = {"fields": fields}

    if doc_id:
        url = _doc_url(collection=collection)
        params = {"documentId": doc_id}
    else:
        url = _doc_url(collection=collection)
        params = {}

    resp = httpx.post(url, json=body, headers=_headers(), params=params, timeout=15)
    if resp.status_code == 409:
        log.info("Document already exists, updating: %s", doc_id)
        return update_document(doc_id, data, collection=collection)
    resp.raise_for_status()
    return resp.json()


def update_document(doc_id: str, data: dict, *, collection: str | None = None) -> dict:
    """Patch (upsert) a Firestore document."""
    fields = {k: _to_firestore_value(v) for k, v in data.items()}
    body: dict[str, Any] = {"fields": fields}
    params = [("updateMask.fieldPaths", k) for k in data]
    resp = httpx.patch(
        _doc_url(doc_id, collection=collection), json=body, headers=_headers(), params=params, timeout=15
    )
    resp.raise_for_status()
    return resp.json()


def query_by_week(week: str, *, collection: str | None = None) -> list[dict]:
    """Query documents where week == ``week``."""
    coll = collection or settings.FIRESTORE_COLLECTION
    url = f"{settings.FIRESTORE_BASE_URL}:runQuery"
    body = {
        "structuredQuery": {
            "from": [{"collectionId": coll}],
            "where": {
                "fieldFilter": {
                    "field": {"fieldPath": "week"},
                    "op": "EQUAL",
                    "value": {"stringValue": week},
                }
            },
        }
    }
    resp = httpx.post(url, json=body, headers=_headers(), timeout=15)
    resp.raise_for_status()

    results: list[dict] = []
    for item in resp.json():
        doc = item.get("document")
        if not doc:
            continue
        fields = doc.get("fields", {})
        results.append({k: _from_firestore_value(v) for k, v in fields.items()})
    return results


def summarize_week(week: str) -> dict:
    """Return aggregated summary for a given week.

    Returns dict with keys: total_gross, total_net, total_tax, count, week.
    """
    docs = query_by_week(week)
    if not docs:
        return {"week": week, "total_gross": 0, "total_net": 0, "total_tax": 0, "count": 0}
    total_gross = sum(d.get("amount_gross", 0) for d in docs)
    total_net = sum(d.get("amount_net", 0) for d in docs)
    total_tax = sum(d.get("tax_withheld", 0) for d in docs)
    return {
        "week": week,
        "total_gross": round(total_gross, 2),
        "total_net": round(total_net, 2),
        "total_tax": round(total_tax, 2),
        "count": len(docs),
    }
