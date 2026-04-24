"""Trade Republic API client — wraps pytr for dividend and transaction extraction."""

from __future__ import annotations

import asyncio
import base64
import logging
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from config import settings
from src.shared.week_utils import date_to_week, week_to_date_range

log = logging.getLogger(__name__)

# ── Credential helpers ──────────────────────────────────────────────

_PYTR_DIR = Path.home() / ".pytr"


def _ensure_credentials() -> None:
    """Write TR credentials / cookies from env vars to disk so pytr can find them."""
    _PYTR_DIR.mkdir(parents=True, exist_ok=True)

    cred_file = _PYTR_DIR / "credentials"
    if not cred_file.exists() and settings.TR_PHONE_NUMBER and settings.TR_PIN:
        cred_file.write_text(f"{settings.TR_PHONE_NUMBER}\n{settings.TR_PIN}\n")
        log.info("Wrote TR credentials to %s", cred_file)

    cookies_b64 = os.environ.get("TR_COOKIES_BASE64", "")
    if cookies_b64:
        phone = settings.TR_PHONE_NUMBER
        cookie_file = _PYTR_DIR / f"cookies.{phone}.txt"
        cookie_file.write_bytes(base64.b64decode(cookies_b64))
        log.info("Wrote TR cookies from TR_COOKIES_BASE64 to %s", cookie_file)


# ── Login ───────────────────────────────────────────────────────────


def create_tr_api(*, interactive: bool = True):
    """Create and authenticate a ``TradeRepublicApi`` instance.

    When *interactive* is False (CI / GCP) the function never prompts for
    user input — it either resumes the saved session or raises.
    """
    from pytr.api import TradeRepublicApi

    _ensure_credentials()

    api = TradeRepublicApi(
        phone_no=settings.TR_PHONE_NUMBER or None,
        pin=settings.TR_PIN or None,
        save_cookies=True,
    )

    if api.resume_websession():
        log.info("Resumed Trade Republic session from saved cookies.")
        return api

    if not interactive:
        raise RuntimeError(
            "Cannot resume TR session (cookies expired or missing).  "
            "Run  python main.py setup  locally first, then store the "
            "cookies as TR_COOKIES_BASE64 secret for headless runs."
        )

    # Interactive web-login (local development only)
    log.info("No saved session — starting interactive web login …")
    countdown = api.initiate_weblogin()
    print(
        f"\nOpen your Trade Republic app and enter the 4-digit code "
        f"(you have ~{countdown}s)."
    )
    code = input("Code (leave empty to request SMS instead): ").strip()
    if not code:
        import time

        wait = max(0, countdown - 2)
        print(f"Waiting {wait}s before requesting SMS …")
        time.sleep(wait)
        api.resend_weblogin()
        code = input("SMS code: ").strip()
    api.complete_weblogin(code)
    log.info("Logged in to Trade Republic.")
    return api


def export_cookies_base64() -> str:
    """Return the current session cookies as a base64 string (for CI secrets)."""
    phone = settings.TR_PHONE_NUMBER
    cookie_file = _PYTR_DIR / f"cookies.{phone}.txt"
    if not cookie_file.exists():
        raise FileNotFoundError(f"No cookie file found at {cookie_file}")
    return base64.b64encode(cookie_file.read_bytes()).decode()


# ── Shared timeline fetch ────────────────────────────────────────────

_SAVINGS_PLAN_EVENT_TYPES = {
    "SAVINGS_PLAN_EXECUTED",
    "SAVINGS_PLAN_INVOICE_CREATED",
    "trading_savingsplan_executed",
}

_SAVINGS_PLAN_SUBTITLES = {
    "Sparplan ausgeführt",
}


def _fetch_timeline(weeks: list[str]) -> list[tuple[dict, "Event"]]:
    """Fetch and parse all timeline events for the given ISO weeks.

    Returns a list of ``(raw_event_dict, parsed_Event)`` tuples.
    """
    from pytr.event import Event
    from pytr.timeline import Timeline

    # Compute the overall date window
    all_mondays, all_sundays = zip(*(week_to_date_range(w) for w in weeks))
    start_date = min(all_mondays)
    end_date = max(all_sundays)

    not_before = datetime.combine(start_date, datetime.min.time(), tzinfo=timezone.utc).timestamp()
    not_after = datetime.combine(end_date, datetime.max.time(), tzinfo=timezone.utc).timestamp()

    log.info(
        "Fetching TR timeline from %s to %s (weeks: %s)",
        start_date,
        end_date,
        ", ".join(sorted(weeks)),
    )

    # Login
    is_interactive = not (os.environ.get("CI") or os.environ.get("PIPELINE_HEADLESS"))
    api = create_tr_api(interactive=is_interactive)

    # Use pytr's Timeline to fetch all events in range with details
    with tempfile.TemporaryDirectory() as tmpdir:
        tl = Timeline(
            tr=api,
            output_path=Path(tmpdir),
            not_before=not_before,
            not_after=not_after,
            store_event_database=False,
        )
        asyncio.run(tl.tl_loop())
        raw_events = list(tl.events)

    log.info("Received %d timeline events total.", len(raw_events))

    parsed: list[tuple[dict, Event]] = []
    for raw in raw_events:
        event = Event.from_dict(raw)
        parsed.append((raw, event))
    return parsed


# ── Fetch dividends ─────────────────────────────────────────────────


def fetch_dividends(weeks: list[str]) -> list[dict]:
    """Fetch dividend events from Trade Republic for the given ISO weeks.

    Returns a list of dicts matching the Firestore ``dividend_payments`` schema.
    """
    from pytr.event import PPEventType

    week_set = set(weeks)
    all_events = _fetch_timeline(weeks)

    dividends: list[dict] = []
    for raw, event in all_events:
        if event.event_type != PPEventType.DIVIDEND:
            continue

        payment_date = event.date.date()
        week = date_to_week(payment_date)
        if week not in week_set:
            continue

        amount_net = abs(event.value) if event.value else 0.0
        tax = abs(event.taxes) if event.taxes else 0.0
        amount_gross = round(amount_net + tax, 2)
        shares = event.shares or 0.0
        dps = round(amount_gross / shares, 6) if shares else 0.0
        currency = raw.get("amount", {}).get("currency", "EUR")

        dividends.append(
            {
                "payment_date": payment_date.isoformat(),
                "stock": raw.get("title", "Unknown"),
                "isin": event.isin or "",
                "ticker": "",  # resolved later via OpenFIGI
                "shares": int(shares) if shares == int(shares) else shares,
                "dividend_per_share": dps,
                "amount_gross": amount_gross,
                "amount_net": amount_net,
                "currency": currency,
                "tax_withheld": tax,
                "week": week,
                "year": payment_date.year,
            }
        )

    log.info("Found %d dividend payments in target weeks.", len(dividends))
    return dividends


# ── Fetch transactions (buy / sell) ─────────────────────────────────


def fetch_transactions(weeks: list[str]) -> list[dict]:
    """Fetch buy/sell events from Trade Republic for the given ISO weeks.

    Returns a list of dicts matching the Firestore ``portfolio_transactions`` schema.
    """
    from pytr.event import ConditionalEventType, PPEventType

    trade_types = (PPEventType.BUY, PPEventType.SELL, ConditionalEventType.TRADE_INVOICE)

    week_set = set(weeks)
    all_events = _fetch_timeline(weeks)

    transactions: list[dict] = []
    for raw, event in all_events:
        if event.event_type not in trade_types:
            continue

        tx_date = event.date.date()
        week = date_to_week(tx_date)
        if week not in week_set:
            continue

        # For TRADE_INVOICE (savings plans, regular trades) determine buy/sell from value sign
        if event.event_type == ConditionalEventType.TRADE_INVOICE:
            tx_type = "sell" if (event.value or 0) >= 0 else "buy"
        else:
            tx_type = "buy" if event.event_type == PPEventType.BUY else "sell"
        total_amount = abs(event.value) if event.value else 0.0
        fees = abs(event.fees) if event.fees else 0.0
        tax = abs(event.taxes) if event.taxes else 0.0
        shares = event.shares or 0.0
        price_per_share = round(total_amount / shares, 6) if shares else 0.0
        currency = raw.get("amount", {}).get("currency", "EUR")

        # Detect savings plan executions (via eventType OR subtitle)
        raw_event_type = raw.get("eventType", "")
        raw_subtitle = raw.get("subtitle", "")
        is_savings_plan = (
            raw_event_type in _SAVINGS_PLAN_EVENT_TYPES
            or raw_subtitle in _SAVINGS_PLAN_SUBTITLES
        )

        transactions.append(
            {
                "date": tx_date.isoformat(),
                "type": tx_type,
                "stock": raw.get("title", "Unknown"),
                "isin": event.isin or "",
                "ticker": "",  # resolved later via OpenFIGI
                "shares": int(shares) if shares == int(shares) else shares,
                "price_per_share": price_per_share,
                "total_amount": total_amount,
                "currency": currency,
                "fees": fees,
                "tax_withheld": tax,
                "is_savings_plan": is_savings_plan,
                "week": week,
                "year": tx_date.year,
            }
        )

    log.info("Found %d transactions (buy/sell) in target weeks.", len(transactions))
    return transactions
