---
applyTo: "**"
---

# OpenWealthLab Pipeline — Copilot Instructions

## Project Overview

This is the **data pipeline** for [OpenWealthLab](https://openwealthlab.com) — a public, data-driven wealth-tech experiment ("Building wealth in public — powered by data & code.").

This repo collects real financial data (dividends, portfolio transactions, market data), writes it to Firestore, and generates automated content stubs that are pushed to the website repo [`derHeinzer/openwealthlab`](https://github.com/derHeinzer/openwealthlab).

**This is a public repo.** Never hardcode secrets, API keys, credentials, account numbers, or sensitive personal data. Everything sensitive goes into GitHub Secrets / environment variables.

## Architecture

```
Broker API → collect.py → write_firestore.py → Firestore (dividend_payments)
                                              → generate_markdown.py → GitHub API → openwealthlab repo
```

### Two-Repo Setup

| Repo | Purpose |
|---|---|
| `derHeinzer/openwealthlab` | Astro website (SSG), Cloudflare Pages Functions (`/api/dividends`), React frontend components |
| `derHeinzer/openwealthlab-pipeline` (this repo) | Python data pipeline, scheduled via GitHub Actions |

The website reads from Firestore at runtime via its own `/api/dividends` Pages Function. This repo writes to Firestore and generates Markdown stubs that trigger website rebuilds.

## Tech Stack

- **Language:** Python 3.12+
- **Database:** Google Firestore (REST API, database name: `openwealthlab`)
- **Scheduling:** GCP Cloud Run Jobs + Cloud Scheduler (Sunday 18:00 UTC)
- **Target repo:** `derHeinzer/openwealthlab` (Astro, Cloudflare Pages)

## Firestore Schema

### Collection: `dividend_payments` (prod) / `dev_dividend_payments` (dev)

```python
{
    "payment_date": "2026-04-21",       # str, YYYY-MM-DD
    "stock": "Apple Inc.",               # str, full company name
    "isin": "US0378331005",             # str, ISIN from Trade Republic
    "ticker": "AAPL",                    # str, ticker symbol (resolved via OpenFIGI)
    "shares": 50,                        # int, number of shares held
    "dividend_per_share": 0.26,          # float
    "amount_gross": 13.00,               # float, gross dividend
    "amount_net": 9.75,                  # float, net after tax
    "currency": "USD",                   # str, ISO currency code
    "tax_withheld": 3.25,               # float, tax amount
    "week": "2026-W17",                  # str, ISO week (YYYY-Wnn)
    "year": 2026,                        # int
}
```

### Collection: `instrument_mappings` (prod) / `dev_instrument_mappings` (dev)

Document ID = ISIN. Cached results from OpenFIGI API v3.

```python
{
    "isin": "US0378331005",             # str, ISIN (same as doc ID)
    "figi": "BBG000B9XRY4",            # str, FIGI
    "ticker": "AAPL",                   # str, ticker symbol
    "name": "APPLE INC",               # str, instrument name
    "exchCode": "US",                   # str, exchange code
    "compositeFIGI": "BBG000B9XRY4",   # str
    "shareClassFIGI": "BBG001S5N8V8",  # str
    "securityType": "Common Stock",     # str
    "securityType2": "Common Stock",    # str
    "securityDescription": "AAPL",      # str
    "marketSector": "Equity",           # str
}
```

### Firestore Connection

- Project ID: `openwealthlab`
- Database: `openwealthlab` (named database, NOT `(default)`)
- Auth: Service Account JSON via `FIREBASE_SERVICE_ACCOUNT_KEY` env var
- Base URL: `https://firestore.googleapis.com/v1/projects/openwealthlab/databases/openwealthlab/documents`
- Auth flow: Create signed JWT → exchange for access token at `https://oauth2.googleapis.com/token`

## Markdown Stub Format

Generated files are pushed to `openwealthlab` repo at `src/content/dividend-logs/{week}.md`:

```markdown
---
title: "Dividend Report – Week {week_num}, {year}"
date: {sunday_date}
summary: "Weekly dividend payouts received in calendar week {week_num}, {year}."
tags: ["dividends", "weekly-report", "{year}"]
type: "weekly-report"
week: "{year}-W{week_num}"
draft: false
---

This is an automated weekly dividend report.
The table and charts below are loaded live from the dividend database.
```

The frontmatter fields `type: "weekly-report"` and `week` are required — they trigger the React components on the website to fetch live data from Firestore via `/api/dividends?week=YYYY-Wnn`.

## Target Repo Structure (for generated files)

Files are committed to `derHeinzer/openwealthlab`:
- Path: `src/content/dividend-logs/{week}.md` (e.g. `2026-w17.md`)
- Branch: `main`
- Commit message: `chore: add dividend report {week}` (automated)

## GitHub Secrets Required

| Secret | Purpose |
|---|---|
| `FIREBASE_SERVICE_ACCOUNT_KEY` | Service Account JSON for Firestore read/write |
| `BROKER_API_KEY` | Broker API credentials (format depends on broker) |
| `OWL_GITHUB_TOKEN` | Personal Access Token (classic) with `repo` scope — to push MD stubs to `derHeinzer/openwealthlab` |

## Pipeline Jobs

### 1. Weekly Dividend Report (Sunday 18:00 UTC)

Workflow: `.github/workflows/weekly-dividends.yml`

Steps:
1. `collect.py` — Query broker API for dividend payments received in the past week
2. `write_firestore.py` — Write each payment as a document to Firestore `dividend_payments`
3. `generate_markdown.py` — Create MD stub and push to `derHeinzer/openwealthlab` via GitHub API

### Future Jobs (not yet implemented)

- Portfolio Logs — buy/sell transactions
- Monthly Reports — monthly performance aggregation
- Market Data — stock prices, fundamentals for experiments

## Coding Conventions

- Python 3.12+, type hints encouraged
- No heavy frameworks — use `requests` or `httpx` for HTTP, no Firebase SDK
- Firestore via REST API (same pattern as the website's Cloudflare Functions)
- Keep modules self-contained: each job in its own directory under `src/`
- Shared utilities (Firestore client, GitHub API client) in `src/shared/`
- Config in `config/settings.py`, environment-specific values from env vars
- Tests in `tests/`, use pytest
- ISO week format: `YYYY-Wnn` (e.g. `2026-W17`), always zero-padded

## Security Rules

- NEVER commit secrets, API keys, or credentials
- NEVER log sensitive data (tokens, keys, account numbers)
- Use `.env` locally (gitignored), GitHub Secrets in CI
- Validate all external API responses before writing to Firestore
- Service account JSON must only be in env vars, never in files checked into git
