# openwealthlab-pipeline

Data pipeline for [OpenWealthLab](https://openwealthlab.com) — collects dividends, portfolio transactions, and market data, writes to Firestore, and generates automated reports.

## Architecture

```
Trade Republic API → tr_client.py → OpenFIGI (ISIN → ticker) → write_firestore.py → Firestore
                                                              → generate_markdown.py → GitHub API → openwealthlab repo
```

## Quick Start

### 1. Install dependencies

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

### 2. Configure environment

```bash
cp .env.example .env
# Edit .env with your Trade Republic credentials and service account key
```

### 3. Login to Trade Republic (first time)

```bash
python main.py setup
```

This saves session cookies locally and prints a base64-encoded version for CI use.

### 4. Run the pipeline

```bash
# Current week (default) — fetches dividends + portfolio, writes to Firestore, pushes markdown
python main.py run

# Run only dividends or only portfolio
python main.py run --dividends
python main.py run --portfolio

# Specific weeks (backfill) — fetches + writes, but skips markdown push by default
python main.py run --weeks 2026-W17 2026-W01

# Backfill with markdown push
python main.py run --weeks 2026-W17 --push-dividend-md --push-portfolio-md

# Preview without writing
python main.py run --dry-run

# Verbose logging
python main.py run -v debug
```

### Pipeline Steps

Each pipeline (dividends + portfolio) follows the same flow:

1. **Fetch** — Query Trade Republic for dividend payments / buy+sell transactions in the given weeks
2. **Enrich** — Resolve ISINs to tickers via OpenFIGI (cached in Firestore `instrument_mappings`)
3. **Write** — Upsert documents to Firestore (idempotent, safe to re-run)
4. **Markdown** — Generate weekly report stubs and push to `derHeinzer/openwealthlab` via GitHub API

Step 4 is skipped when using `--weeks` (backfill mode) unless `--push-dividend-md` / `--push-portfolio-md` is given.
When markdown is not pushed, Gemini commentary generation and week-over-week aggregation are also skipped.

## GCP Deployment (Cloud Run Job)

The pipeline runs as a Cloud Run Job triggered weekly by Cloud Scheduler. Cost: **$0** (within free tier).

### Setup

```bash
chmod +x deploy/setup-gcp.sh
./deploy/setup-gcp.sh
```

This creates:
- Artifact Registry repository
- Cloud Run Job with secrets mounted from Secret Manager
- Cloud Scheduler trigger (Sunday 18:00 UTC)

### Required Secrets (GCP Secret Manager)

| Secret | Purpose |
|---|---|
| `FIREBASE_SERVICE_ACCOUNT_KEY` | Service Account JSON for Firestore |
| `TR_PHONE_NUMBER` | Trade Republic phone number |
| `TR_PIN` | Trade Republic PIN |
| `TR_COOKIES_BASE64` | Session cookies (from `python main.py setup`) |
| `OWL_GITHUB_TOKEN` | PAT with `repo` scope for pushing markdown stubs |

### Manual trigger

```bash
gcloud run jobs execute dividend-pipeline --region=europe-west1
```

## Project Structure

```
main.py                          # CLI entry point
config/settings.py               # Configuration from env vars
src/
  shared/
    auth.py                      # Google OAuth2 (JWT → access token)
    firestore_client.py          # Firestore REST API client
    github_client.py             # GitHub API for pushing files
    tr_client.py                 # Trade Republic API via pytr
    week_utils.py                # ISO week helpers
    openfigi_client.py           # OpenFIGI v3 ISIN → ticker resolution
    isin_mapping.py              # Firestore-cached ISIN enrichment
  dividends/
    collect.py                   # Pipeline orchestrator (dividends + portfolio)
    write_firestore.py           # Write dividends to Firestore
    generate_markdown.py         # Generate & push dividend MD stubs
  portfolio/
    write_firestore.py           # Write transactions to Firestore
    generate_markdown.py         # Generate & push portfolio MD stubs
deploy/setup-gcp.sh             # GCP infrastructure setup
Dockerfile                       # Container for Cloud Run
tests/                           # pytest tests
```

## Tests

```bash
python -m pytest tests/ -v
```
