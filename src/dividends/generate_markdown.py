"""Generate weekly dividend-report markdown stubs and push to the website repo."""

from __future__ import annotations

import logging

from config import settings
from src.shared.github_client import push_file
from src.shared.week_utils import week_sunday

log = logging.getLogger(__name__)

_TEMPLATE = """\
---
title: "Dividend Report – Week {week_num}, {year}"
date: {sunday_date}
summary: "Weekly dividend payouts received in calendar week {week_num}, {year}."
tags: ["dividends", "weekly-report", "{year}"]
type: "weekly-report"
week: "{week_str}"
draft: false
---

This is an automated weekly dividend report.
The table and charts below are loaded live from the dividend database.
"""


def generate_markdown(week_str: str) -> str:
    """Return the markdown content for a given ISO week."""
    year, week_num = week_str.split("-W")
    sunday = week_sunday(week_str)
    return _TEMPLATE.format(
        week_num=int(week_num),
        year=year,
        sunday_date=sunday.isoformat(),
        week_str=week_str,
    )


def push_markdown(week_str: str, *, dry_run: bool = False) -> bool:
    """Generate the markdown stub and push it to the website repo.

    Returns True if a file was created / updated.
    """
    filename = f"{week_str.lower()}.md"
    path = f"{settings.OWL_CONTENT_PATH}/{filename}"
    content = generate_markdown(week_str)

    if dry_run:
        log.info("[dry-run] Would push %s:\n%s", path, content)
        return True

    if not settings.OWL_GITHUB_TOKEN:
        log.warning("OWL_GITHUB_TOKEN not set – skipping markdown push.")
        return False

    pushed = push_file(
        path=path,
        content=content,
        message=f"chore: add dividend report {week_str}",
    )
    if pushed:
        log.info("Pushed %s to %s", path, settings.OWL_GITHUB_REPO)
    else:
        log.info("Markdown for %s already up-to-date.", week_str)
    return pushed
