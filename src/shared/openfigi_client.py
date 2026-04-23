"""OpenFIGI API v3 client — resolve ISINs to tickers and instrument metadata."""

from __future__ import annotations

import logging
import os

import httpx

log = logging.getLogger(__name__)

_BASE_URL = "https://api.openfigi.com/v3/mapping"

# OpenFIGI response fields we persist
FIGI_FIELDS = (
    "figi",
    "name",
    "ticker",
    "exchCode",
    "compositeFIGI",
    "shareClassFIGI",
    "securityType",
    "securityType2",
    "securityDescription",
    "marketSector",
)


def _headers() -> dict[str, str]:
    h: dict[str, str] = {"Content-Type": "application/json"}
    api_key = os.environ.get("OPENFIGI_API_KEY", "")
    if api_key:
        h["X-OPENFIGI-APIKEY"] = api_key
    return h


def resolve_isins(isins: list[str]) -> dict[str, dict | None]:
    """Batch-resolve ISINs via OpenFIGI.

    Returns a dict  ``{isin: {figi_data...} | None}``.
    For each ISIN we pick the *first* Equity / Common Stock result.
    ISINs without a match map to ``None``.

    Without an API key the limit is 10 jobs per request / 25 req per minute.
    With a key: 100 jobs per request.
    """
    if not isins:
        return {}

    api_key = os.environ.get("OPENFIGI_API_KEY", "")
    batch_size = 100 if api_key else 10

    results: dict[str, dict | None] = {}

    for i in range(0, len(isins), batch_size):
        batch = isins[i : i + batch_size]
        jobs = [{"idType": "ID_ISIN", "idValue": isin} for isin in batch]

        log.info(
            "OpenFIGI: POST %s  (%d ISINs: %s)",
            _BASE_URL,
            len(batch),
            ", ".join(batch),
        )

        resp = httpx.post(_BASE_URL, json=jobs, headers=_headers(), timeout=15)
        resp.raise_for_status()
        data = resp.json()

        log.info("OpenFIGI: %d responses received", len(data))

        for isin, item in zip(batch, data):
            if "warning" in item:
                log.warning("OpenFIGI: no match for %s — %s", isin, item["warning"])
                results[isin] = None
                continue
            if "error" in item:
                log.error("OpenFIGI: error for %s — %s", isin, item["error"])
                results[isin] = None
                continue

            # Pick the best match: prefer Equity / Common Stock
            matches = item.get("data", [])
            best = _pick_best(matches)
            if best:
                entry = {k: best.get(k) for k in FIGI_FIELDS}
                entry["isin"] = isin
                log.info(
                    "OpenFIGI: %s → ticker=%s, name=%s, figi=%s",
                    isin,
                    entry.get("ticker"),
                    entry.get("name"),
                    entry.get("figi"),
                )
                results[isin] = entry
            else:
                log.warning("OpenFIGI: %s returned %d results but none usable", isin, len(matches))
                results[isin] = None

    return results


def _pick_best(matches: list[dict]) -> dict | None:
    """Pick the best FIGI result — prefer Equity Common Stock with a compositeFIGI."""
    if not matches:
        return None

    # 1st pass: composite FIGI + equity
    for m in matches:
        if m.get("marketSector") == "Equity" and m.get("compositeFIGI"):
            return m

    # 2nd pass: any equity
    for m in matches:
        if m.get("marketSector") == "Equity":
            return m

    # Fallback: first result
    return matches[0]
