"""Write portfolio transaction records to Firestore."""

from __future__ import annotations

import logging

from config import settings
from src.shared import firestore_client as fs

log = logging.getLogger(__name__)


def _doc_id(tx: dict) -> str:
    """Deterministic document ID so re-runs are idempotent."""
    isin = tx.get("isin") or tx.get("ticker", "UNKNOWN")
    return f"{tx['date']}_{isin}_{tx['type']}"


def write_transactions(transactions: list[dict], *, dry_run: bool = False) -> int:
    """Write transaction records to Firestore.

    Returns the number of documents written / updated.
    """
    if not transactions:
        log.info("No transactions to write.")
        return 0

    collection = settings.FIRESTORE_PORTFOLIO_COLLECTION
    written = 0
    for tx in transactions:
        doc_id = _doc_id(tx)
        if dry_run:
            log.info("[dry-run] Would write %s: %s", doc_id, tx)
            written += 1
            continue

        fs.create_document(tx, doc_id=doc_id, collection=collection)
        log.info("Wrote %s → %s (%s)", doc_id, tx["stock"], tx["type"])
        written += 1

    log.info("Wrote %d transaction documents to Firestore.", written)
    return written
