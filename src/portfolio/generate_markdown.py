"""Generate weekly portfolio-log markdown stubs and push to the website repo."""

from __future__ import annotations

import logging

import yaml

from config import settings
from src.shared.github_client import push_file
from src.shared.week_utils import week_sunday

log = logging.getLogger(__name__)


def _build_summary(transactions: list[dict]) -> dict:
    """Compute aggregate stats for the frontmatter."""
    buys = [t for t in transactions if t["type"] == "buy"]
    sells = [t for t in transactions if t["type"] == "sell"]
    savings = [t for t in transactions if t.get("is_savings_plan")]
    return {
        "total_invested": round(sum(t["total_amount"] for t in buys), 2),
        "total_sold": round(sum(t["total_amount"] for t in sells), 2),
        "total_fees": round(sum(t.get("fees", 0) for t in transactions), 2),
        "total_tax": round(sum(t.get("tax_withheld", 0) for t in transactions), 2),
        "buy_count": len(buys),
        "sell_count": len(sells),
        "savings_plan_count": len(savings),
    }


def _clean_transaction(tx: dict) -> dict:
    """Return a frontmatter-safe subset of a transaction dict."""
    return {
        "date": tx["date"],
        "type": tx["type"],
        "stock": tx["stock"],
        "isin": tx.get("isin", ""),
        "ticker": tx.get("ticker", ""),
        "shares": tx["shares"],
        "price_per_share": tx["price_per_share"],
        "total_amount": tx["total_amount"],
        "currency": tx.get("currency", "EUR"),
        "fees": tx.get("fees", 0),
        "tax_withheld": tx.get("tax_withheld", 0),
        "is_savings_plan": tx.get("is_savings_plan", False),
    }


def generate_markdown(week_str: str, transactions: list[dict] | None = None) -> str:
    """Return the markdown content for a given ISO week.

    When *transactions* is provided, the data is embedded in frontmatter
    so the website can render it without Firestore calls.
    """
    year, week_num = week_str.split("-W")
    sunday = week_sunday(week_str)

    frontmatter: dict = {
        "title": f"Portfolio Log – Week {int(week_num)}, {year}",
        "date": sunday.isoformat(),
        "summary": f"Weekly portfolio activity in calendar week {int(week_num)}, {year}.",
        "tags": ["portfolio", "weekly-log", year],
        "type": "portfolio-log",
        "week": week_str,
        "draft": False,
    }

    if transactions:
        cleaned = [_clean_transaction(tx) for tx in transactions]
        # Sort: buys first, then sells, then by date
        cleaned.sort(key=lambda t: (0 if t["type"] == "buy" else 1, t["date"], t["stock"]))
        frontmatter["transactions"] = cleaned
        frontmatter["stats"] = _build_summary(transactions)

    fm_yaml = yaml.dump(frontmatter, default_flow_style=False, allow_unicode=True, sort_keys=False)
    body = (
        "This is an automated weekly portfolio log.\n"
        "The table and charts below are rendered from the embedded transaction data."
    )
    return f"---\n{fm_yaml}---\n\n{body}\n"


def push_portfolio_markdown(
    week_str: str,
    transactions: list[dict] | None = None,
    *,
    dry_run: bool = False,
) -> bool:
    """Generate the markdown stub and push it to the website repo.

    Returns True if a file was created / updated.
    """
    filename = f"{week_str.lower()}.md"
    path = f"{settings.OWL_PORTFOLIO_CONTENT_PATH}/{filename}"
    content = generate_markdown(week_str, transactions=transactions)

    if dry_run:
        log.info("[dry-run] Would push %s:\n%s", path, content)
        return True

    if not settings.OWL_GITHUB_TOKEN:
        log.warning("OWL_GITHUB_TOKEN not set – skipping portfolio markdown push.")
        return False

    pushed = push_file(
        path=path,
        content=content,
        message=f"chore: add portfolio log {week_str}",
    )
    if pushed:
        log.info("Pushed %s to %s", path, settings.OWL_GITHUB_REPO)
    else:
        log.info("Portfolio markdown for %s already up-to-date.", week_str)
    return pushed
