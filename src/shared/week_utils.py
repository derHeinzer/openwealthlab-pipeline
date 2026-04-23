"""ISO-week helper utilities.

Week format used everywhere: ``YYYY-Wnn`` (zero-padded).
"""

from __future__ import annotations

from datetime import date, datetime, timedelta


def current_week() -> str:
    """Return the ISO week string for today, e.g. ``2026-W17``."""
    return date_to_week(date.today())


def date_to_week(d: date) -> str:
    iso = d.isocalendar()
    return f"{iso.year}-W{iso.week:02d}"


def week_to_date_range(week_str: str) -> tuple[date, date]:
    """Return (monday, sunday) for an ISO week string like ``2026-W17``."""
    year, wn = _parse_week(week_str)
    # ISO: week 1 contains the first Thursday → derive Monday
    jan4 = date(year, 1, 4)
    start_of_w1 = jan4 - timedelta(days=jan4.weekday())
    monday = start_of_w1 + timedelta(weeks=wn - 1)
    sunday = monday + timedelta(days=6)
    return monday, sunday


def week_sunday(week_str: str) -> date:
    """Return the Sunday of the given ISO week (used as report date)."""
    _, sunday = week_to_date_range(week_str)
    return sunday


def parse_week_arg(raw: str) -> str:
    """Normalise user input like ``2026-17`` or ``2026-W3`` → ``2026-W17`` / ``2026-W03``."""
    raw = raw.strip().upper()
    if "-W" in raw:
        year, wn = _parse_week(raw)
    elif "-" in raw:
        parts = raw.split("-")
        year, wn = int(parts[0]), int(parts[1])
    else:
        raise ValueError(f"Cannot parse week: {raw!r}  (expected YYYY-Wnn or YYYY-nn)")
    if not (1 <= wn <= 53):
        raise ValueError(f"Week number out of range: {wn}")
    return f"{year}-W{wn:02d}"


def _parse_week(week_str: str) -> tuple[int, int]:
    year_s, w_s = week_str.split("-W")
    return int(year_s), int(w_s)
