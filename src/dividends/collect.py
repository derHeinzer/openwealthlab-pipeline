"""Orchestrate the pipeline: dividends and/or portfolio transactions."""

from __future__ import annotations

import logging

from src.dividends.generate_markdown import push_markdown
from src.dividends.write_firestore import write_dividends
from src.portfolio.generate_markdown import push_portfolio_markdown
from src.portfolio.write_firestore import write_transactions
from src.shared.firestore_client import summarize_week
from src.shared.gemini_client import generate_commentary
from src.shared.isin_mapping import enrich_records
from src.shared.tr_client import fetch_dividends, fetch_transactions
from src.shared.week_utils import prev_week, same_week_prev_year

log = logging.getLogger(__name__)


def run_pipeline(
    weeks: list[str],
    *,
    dry_run: bool = False,
    run_dividends: bool = True,
    run_portfolio: bool = True,
    push_dividend_md: bool = False,
    push_portfolio_md: bool = False,
) -> None:
    """Execute the pipeline for the given ISO weeks."""
    log.info(
        "=== Pipeline starting (weeks=%s, dry_run=%s, dividends=%s, portfolio=%s, "
        "push_dividend_md=%s, push_portfolio_md=%s) ===",
        weeks, dry_run, run_dividends, run_portfolio,
        push_dividend_md, push_portfolio_md,
    )

    # ── Dividend pipeline ───────────────────────────────────────────
    if run_dividends:
        _run_dividend_pipeline(weeks, dry_run=dry_run, push_md=push_dividend_md)

    # ── Portfolio pipeline ──────────────────────────────────────────
    if run_portfolio:
        _run_portfolio_pipeline(weeks, dry_run=dry_run, push_md=push_portfolio_md)

    log.info("=== Pipeline finished ===")


def _run_dividend_pipeline(weeks: list[str], *, dry_run: bool, push_md: bool) -> None:
    """Collect dividends → enrich → write → optionally push markdown."""
    log.info("--- Dividends: Fetching from Trade Republic ---")
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

    log.info("--- Dividends: Resolving ISINs via OpenFIGI ---")
    enrich_records(dividends, dry_run=dry_run)

    log.info("After enrichment:")
    for d in dividends:
        log.info(
            "  %s | %s | ISIN=%s → ticker=%s",
            d["payment_date"],
            d["stock"],
            d.get("isin", "?"),
            d.get("ticker", "?"),
        )

    log.info("--- Dividends: Writing to Firestore ---")
    write_dividends(dividends, dry_run=dry_run)

    if not push_md:
        log.info("--- Dividends: Skipping markdown push ---")
        return

    log.info("--- Dividends: Generating commentary & markdown stubs ---")
    weeks_with_data = sorted({d["week"] for d in dividends})
    for week in weeks_with_data:
        week_divs = [d for d in dividends if d["week"] == week]

        # Aggregate comparison data from Firestore
        log.info("  Fetching comparison data for %s …", week)
        current_summary = summarize_week(week)
        prev_summary = summarize_week(prev_week(week))
        yoy_summary = summarize_week(same_week_prev_year(week))

        log.info("  Current: %s | Prev: %s | YoY: %s",
                 current_summary, prev_summary, yoy_summary)

        # Generate LLM commentary
        log.info("  Generating Gemini commentary …")
        commentary = generate_commentary(
            current=current_summary,
            prev_week=prev_summary,
            prev_year=yoy_summary,
            dividends=week_divs,
        )

        push_markdown(week, commentary=commentary, dry_run=dry_run)


def _run_portfolio_pipeline(weeks: list[str], *, dry_run: bool, push_md: bool) -> None:
    """Collect transactions → enrich → write → optionally push markdown."""
    log.info("--- Portfolio: Fetching transactions from Trade Republic ---")
    transactions = fetch_transactions(weeks)

    if not transactions:
        log.info("No transactions found for weeks %s — nothing to do.", weeks)
        return

    log.info("Found %d transaction(s):", len(transactions))
    for tx in transactions:
        log.info(
            "  %s | %s %s (ISIN: %s) | shares=%s | amount=%s %s | fees=%s | tax=%s%s",
            tx["date"],
            tx["type"].upper(),
            tx["stock"],
            tx.get("isin", "?"),
            tx["shares"],
            tx["total_amount"],
            tx["currency"],
            tx["fees"],
            tx.get("tax_withheld", 0),
            " [savings plan]" if tx.get("is_savings_plan") else "",
        )

    log.info("--- Portfolio: Resolving ISINs via OpenFIGI ---")
    enrich_records(transactions, dry_run=dry_run)

    log.info("After enrichment:")
    for tx in transactions:
        log.info(
            "  %s | %s %s | ISIN=%s → ticker=%s",
            tx["date"],
            tx["type"].upper(),
            tx["stock"],
            tx.get("isin", "?"),
            tx.get("ticker", "?"),
        )

    log.info("--- Portfolio: Writing transactions to Firestore ---")
    write_transactions(transactions, dry_run=dry_run)

    if not push_md:
        log.info("--- Portfolio: Skipping markdown push ---")
        return

    log.info("--- Portfolio: Generating markdown stubs ---")
    weeks_with_data = sorted({tx["week"] for tx in transactions})
    for week in weeks_with_data:
        week_txs = [tx for tx in transactions if tx["week"] == week]
        push_portfolio_markdown(week, transactions=week_txs, dry_run=dry_run)
