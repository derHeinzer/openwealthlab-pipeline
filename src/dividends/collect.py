"""Orchestrate the weekly dividend pipeline: collect → write → markdown."""

from __future__ import annotations

import logging

from src.dividends.generate_markdown import push_markdown
from src.dividends.tr_client import fetch_dividends
from src.dividends.write_firestore import write_dividends
from src.shared.isin_mapping import enrich_dividends

log = logging.getLogger(__name__)


def run_pipeline(weeks: list[str], *, dry_run: bool = False, skip_markdown: bool = False) -> None:
    """Execute the full dividend pipeline for the given ISO weeks."""
    log.info("=== Dividend pipeline starting (weeks: %s, dry_run=%s, skip_markdown=%s) ===", weeks, dry_run, skip_markdown)

    # 1. Collect from Trade Republic
    log.info("--- Step 1: Fetching dividends from Trade Republic ---")
    dividends = fetch_dividends(weeks)

    if not dividends:
        log.info("No dividends found for weeks %s — nothing to do.", weeks)
        return

    log.info("Found %d dividend payment(s):", len(dividends))
    for d in dividends:
        log.info(
            "  %s | %s (ISIN: %s) | gross=%s %s | net=%s %s | tax=%s",
            d["payment_date"],
            d["stock"],
            d.get("isin", "?"),
            d["amount_gross"],
            d["currency"],
            d["amount_net"],
            d["currency"],
            d["tax_withheld"],
        )

    # 2. Resolve ISINs → tickers via OpenFIGI + Firestore cache
    log.info("--- Step 2: Resolving ISINs via OpenFIGI ---")
    enrich_dividends(dividends, dry_run=dry_run)

    log.info("After enrichment:")
    for d in dividends:
        log.info(
            "  %s | %s | ISIN=%s → ticker=%s",
            d["payment_date"],
            d["stock"],
            d.get("isin", "?"),
            d.get("ticker", "?"),
        )

    # 3. Write to Firestore
    log.info("--- Step 3: Writing dividends to Firestore ---")
    write_dividends(dividends, dry_run=dry_run)

    # 4. Generate & push markdown stubs (one per week that has dividends)
    if skip_markdown:
        log.info("--- Step 4: Skipping markdown push (backfill mode) ---")
    else:
        log.info("--- Step 4: Generating markdown stubs ---")
        weeks_with_data = sorted({d["week"] for d in dividends})
        for week in weeks_with_data:
            push_markdown(week, dry_run=dry_run)

    log.info("=== Dividend pipeline finished ===")
