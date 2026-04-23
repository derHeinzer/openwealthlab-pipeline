#!/usr/bin/env python3
"""CLI entry point for the openwealthlab dividend pipeline.

Usage
-----
    # First-time setup: login to Trade Republic interactively
    python main.py setup

    # Run pipeline for the current week
    python main.py run

    # Run pipeline for specific weeks
    python main.py run --weeks 2026-W01 2026-W17

    # Dry-run (preview, no writes)
    python main.py run --dry-run

    # Dry-run for specific weeks
    python main.py run --weeks 2026-W17 --dry-run
"""

from __future__ import annotations

import argparse
import logging
import sys

from dotenv import load_dotenv

load_dotenv()  # load .env before anything reads settings


def _setup_logging(verbosity: str) -> None:
    level = {"debug": logging.DEBUG, "info": logging.INFO, "warning": logging.WARNING}[
        verbosity
    ]
    logging.basicConfig(
        level=level,
        format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
        datefmt="%H:%M:%S",
    )


# ── Sub-commands ────────────────────────────────────────────────────


def cmd_setup(args: argparse.Namespace) -> None:
    """Interactive Trade Republic login — saves session cookies."""
    from src.dividends.tr_client import create_tr_api, export_cookies_base64

    api = create_tr_api(interactive=True)
    print("\n✓ Logged in successfully. Session cookies saved.\n")

    b64 = export_cookies_base64()
    print("To use this session in CI / GCP, store the following value")
    print("as the  TR_COOKIES_BASE64  secret:\n")
    print(b64)
    print()


def cmd_run(args: argparse.Namespace) -> None:
    """Run the dividend pipeline."""
    from src.dividends.collect import run_pipeline
    from src.shared.week_utils import current_week, parse_week_arg

    if args.weeks:
        weeks = [parse_week_arg(w) for w in args.weeks]
        skip_md = not args.push_markdown
    else:
        weeks = [current_week()]
        skip_md = False

    run_pipeline(weeks, dry_run=args.dry_run, skip_markdown=skip_md)


# ── Argument parser ─────────────────────────────────────────────────


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="openwealthlab-pipeline",
        description="Dividend data pipeline for OpenWealthLab",
    )
    parser.add_argument(
        "-v",
        "--verbosity",
        choices=["debug", "info", "warning"],
        default="info",
        help="Log verbosity (default: info)",
    )

    sub = parser.add_subparsers(dest="command")

    # setup
    sub.add_parser("setup", help="Login to Trade Republic (interactive)")

    # run
    run_p = sub.add_parser("run", help="Run the dividend pipeline")
    run_p.add_argument(
        "--weeks",
        nargs="+",
        metavar="WEEK",
        help="ISO weeks to process, e.g. 2026-W17  (default: current week)",
    )
    run_p.add_argument(
        "--push-markdown",
        action="store_true",
        help="Also push markdown stubs when using --weeks (default: skip)",
    )
    run_p.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview without writing to Firestore or pushing markdown",
    )

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    _setup_logging(args.verbosity)

    if args.command == "setup":
        cmd_setup(args)
    elif args.command == "run":
        cmd_run(args)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
