"""ISIN → instrument mapping with Firestore cache + OpenFIGI resolution."""

from __future__ import annotations

import logging
from typing import Any

import httpx

from config import settings
from src.shared.auth import get_access_token
from src.shared.openfigi_client import resolve_isins

log = logging.getLogger(__name__)

_COLLECTION = (
    "instrument_mappings" if settings.PIPELINE_ENV == "prod" else "dev_instrument_mappings"
)


def _headers() -> dict[str, str]:
    return {
        "Authorization": f"Bearer {get_access_token()}",
        "Content-Type": "application/json",
    }


def _to_fv(val: Any) -> dict:
    if val is None:
        return {"nullValue": None}
    if isinstance(val, str):
        return {"stringValue": val}
    if isinstance(val, int):
        return {"integerValue": str(val)}
    if isinstance(val, float):
        return {"doubleValue": val}
    if isinstance(val, bool):
        return {"booleanValue": val}
    return {"stringValue": str(val)}


def _from_fv(fv: dict) -> Any:
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


def _collection_url(doc_id: str | None = None) -> str:
    base = f"{settings.FIRESTORE_BASE_URL}/{_COLLECTION}"
    return f"{base}/{doc_id}" if doc_id else base


# ── Firestore operations ────────────────────────────────────────────


def _get_cached(isin: str) -> dict | None:
    """Fetch a single mapping document from Firestore, or None."""
    url = _collection_url(isin)
    resp = httpx.get(url, headers=_headers(), timeout=15)
    if resp.status_code == 404:
        return None
    resp.raise_for_status()
    doc = resp.json()
    fields = doc.get("fields", {})
    return {k: _from_fv(v) for k, v in fields.items()}


def _get_cached_batch(isins: list[str]) -> dict[str, dict | None]:
    """Fetch multiple mapping docs. Returns {isin: data | None}."""
    result: dict[str, dict | None] = {}
    for isin in isins:
        result[isin] = _get_cached(isin)
    return result


def _write_mapping(isin: str, data: dict, *, dry_run: bool = False) -> None:
    """Upsert an instrument mapping document (doc ID = ISIN)."""
    if dry_run:
        log.info("[dry-run] Would write instrument_mappings/%s: %s", isin, data)
        return

    fields = {k: _to_fv(v) for k, v in data.items()}
    body = {"fields": fields}
    url = _collection_url()
    params = {"documentId": isin}

    resp = httpx.post(url, json=body, headers=_headers(), params=params, timeout=15)
    if resp.status_code == 409:
        # Already exists — patch
        params_patch = [("updateMask.fieldPaths", k) for k in data]
        resp = httpx.patch(
            _collection_url(isin), json=body, headers=_headers(), params=params_patch, timeout=15
        )
    resp.raise_for_status()
    log.info("Wrote instrument_mappings/%s (ticker=%s)", isin, data.get("ticker"))


# ── Public API ──────────────────────────────────────────────────────


def enrich_dividends(
    dividends: list[dict], *, dry_run: bool = False
) -> list[dict]:
    """Resolve ISINs to tickers + metadata for all dividends.

    - Checks Firestore ``instrument_mappings`` cache first
    - Calls OpenFIGI for unknown ISINs (one batch request)
    - Writes new mappings to Firestore
    - Enriches each dividend dict with ``ticker`` from the mapping

    Returns the enriched dividends list (mutated in place).
    """
    # Collect unique ISINs
    isins = sorted({d["isin"] for d in dividends if d.get("isin")})
    if not isins:
        return dividends

    log.info("Resolving %d unique ISIN(s): %s", len(isins), ", ".join(isins))

    # 1. Check Firestore cache
    if dry_run:
        log.info("[dry-run] Would check Firestore instrument_mappings for: %s", isins)
        cached: dict[str, dict | None] = {isin: None for isin in isins}
    else:
        cached = _get_cached_batch(isins)

    known = {isin: data for isin, data in cached.items() if data is not None}
    unknown = [isin for isin in isins if isin not in known]

    if known:
        log.info(
            "Firestore cache hit for %d ISIN(s): %s",
            len(known),
            ", ".join(f"{isin}→{d.get('ticker')}" for isin, d in known.items()),
        )

    # 2. Resolve unknowns via OpenFIGI
    resolved: dict[str, dict | None] = {}
    if unknown:
        log.info("OpenFIGI lookup needed for %d ISIN(s): %s", len(unknown), ", ".join(unknown))
        resolved = resolve_isins(unknown)

        # 3. Write new mappings to Firestore
        for isin, data in resolved.items():
            if data:
                _write_mapping(isin, data, dry_run=dry_run)

    # 4. Build final lookup and enrich dividends
    lookup: dict[str, dict] = {**known}
    for isin, data in resolved.items():
        if data:
            lookup[isin] = data

    for div in dividends:
        isin = div.get("isin", "")
        mapping = lookup.get(isin)
        if mapping:
            div["ticker"] = mapping.get("ticker") or ""
        else:
            div["ticker"] = ""

    return dividends
