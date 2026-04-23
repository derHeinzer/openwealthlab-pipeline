"""Write dividend payment records to Firestore."""

from __future__ import annotations

import logging

from src.shared import firestore_client as fs

log = logging.getLogger(__name__)


def _doc_id(div: dict) -> str:
    """Deterministic document ID so re-runs are idempotent."""
    # payment_date + isin gives a unique key per payout event
    return f"{div['payment_date']}_{div.get('isin') or div.get('ticker', 'UNKNOWN')}"


def write_dividends(dividends: list[dict], *, dry_run: bool = False) -> int:
    """Write dividend records to Firestore.

    Returns the number of documents written / updated.
    """
    if not dividends:
        log.info("No dividends to write.")
        return 0

    written = 0
    for div in dividends:
        doc_id = _doc_id(div)
        if dry_run:
            log.info("[dry-run] Would write %s: %s", doc_id, div)
            written += 1
            continue

        fs.create_document(div, doc_id=doc_id)
        log.info("Wrote %s → %s", doc_id, div["stock"])
        written += 1

    log.info("Wrote %d dividend documents to Firestore.", written)
    return written
