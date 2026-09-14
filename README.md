# EDGAR Filing Monitor

A production-style batch data pipeline that monitors SEC EDGAR daily filing-index data, validates source records, preserves raw-data provenance, maintains idempotent curated state, and publishes operational metrics to a live dashboard.

**Live dashboard:** [SS-Awan.github.io/edgar-filing-monitor](https://ss-awan.github.io/edgar-filing-monitor/)

## What it does

The pipeline collects the SEC daily master index, then processes 10-K, 10-Q, and 8-K filing metadata through a controlled workflow:

```text
SEC daily index
  -> checksum-addressed raw snapshot
  -> schema validation and quarantine
  -> target-form selection
  -> composite-key idempotent merge
  -> partitioned Parquet curated state
  -> DuckDB dashboard query
  -> GitHub Pages deployment
```

This project processes filing-index metadata only. It does not scrape full filing documents or attempt to mirror all SEC EDGAR data.

## Verified deployment results

The latest verified GitHub Actions deployment processed seven completed SEC filing dates and published the resulting dashboard.

| Metric | Latest verified result |
| --- | ---: |
| Source dates succeeded | 7 of 7 |
| Source rows received | 29,422 |
| Validated records | 29,422 |
| Quarantined records | 0 |
| Curated CIK + accession relationships | 1,555 |
| Unique companies | 1,222 |
| New relationships inserted | 886 |
| Unchanged relationships | 669 |
| Automated tests | 42 passing |

These numbers are operational output, not fixed repository data. The live dashboard updates after successful scheduled runs.

## Why this is a data-engineering project

The project focuses on reliable data operations rather than only downloading and displaying a dataset:

- Fetches directly from SEC daily-index endpoints with a declared User-Agent.
- Stores raw source payloads using SHA-256 content checksums and JSON provenance metadata.
- Validates required fields and quarantines invalid rows rather than silently loading them.
- Uses `(CIK, accession_number)` as the idempotency key.
- Maintains partitioned Parquet state by filing year and form type.
- Uses DuckDB to query curated state for dashboard metrics.
- Records every run in a JSONL ledger with row counts, insert/update/unchanged counts, and failure details.
- Uses a rolling business-day lookback, failed-date retries, and SEC market-holiday exclusion.
- Promotes curated state only after a fully successful run, avoiding partial-state replacement.
- Runs tests on every push and pull request through GitHub Actions.
- Restores and republishes rolling state through GitHub Actions artifacts instead of committing operational data to Git.

## Architecture

Detailed design notes are in [docs/architecture.md](docs/architecture.md).

```text
                         GitHub Actions
                              |
                              v
SEC daily index -> Python pipeline -> raw snapshots
                              |
                              v
                  validation + quarantine
                              |
                              v
            Parquet curated state + JSONL run ledger
                              |
                              v
                       DuckDB queries
                              |
                              v
                  static dashboard JSON
                              |
                              v
                        GitHub Pages
```

## Repository structure

```text
.github/workflows/
  ci.yml                     Run automated tests on push and pull request
  scheduled_pipeline.yml     Restore state, ingest, publish artifacts and deploy Pages

src/edgar_monitor/
  cli.py                     Command-line entry point
  sec_client.py              SEC HTTP client and daily-index retrieval
  index_parser.py            Daily master-index parsing
  validation.py              Schema and quality validation
  curation.py                Target form selection and idempotent merge logic
  raw_storage.py             Checksum-addressed raw snapshot storage
  planning.py                Lookback, backfill, retry, and holiday planning
  pipeline.py                End-to-end orchestration
  observability.py           JSONL run-ledger persistence
  dashboard_data.py          DuckDB-backed dashboard-data generation

scripts/
  build_dashboard_data.py    Build site/data/dashboard.json from pipeline state

site/
  index.html                 Static dashboard page
  styles.css                 Dashboard styling
  app.js                     Dashboard rendering logic

tests/
  Fixed fixtures and automated unit/integration-style tests
```

## Run locally

### 1. Create and activate a virtual environment

```cmd
python -m venv .venv
.venv\Scripts\activate
```

### 2. Install the project

```cmd
python -m pip install --upgrade pip
pip install -e ".[dev]"
```

### 3. Set the SEC User-Agent for the current terminal

SEC requests require a descriptive User-Agent with contact information.

```cmd
set "SEC_USER_AGENT=Your Name EDGAR Filing Monitor your-email@example.com"
```

### 4. Run a one-date ingestion

```cmd
python -m edgar_monitor.cli --source-date 2026-09-10
```

### 5. Run the scheduled lookback mode

```cmd
python -m edgar_monitor.cli --scheduled --lookback-days 7
```

### 6. Run tests

```cmd
pytest
git diff --check
```

### 7. Generate and preview the dashboard locally

```cmd
python scripts\build_dashboard_data.py
python -m http.server 8000 --directory site
```

Open <http://localhost:8000>.

## Automation and state handling

The scheduled GitHub Actions workflow runs on weekdays and can also be triggered manually.

It restores the latest available state artifact, runs the pipeline, then uploads:

- `edgar-pipeline-state` — curated Parquet state and run ledger, retained for 7 days.
- `edgar-raw-snapshots` — raw SEC payload snapshots and provenance metadata, retained for 30 days.
- `github-pages` — the newly generated static dashboard deployment artifact.

Operational data is intentionally excluded from Git:

```text
data/raw/
data/state/
site/data/
```

The source code, tests, workflow definitions, and dashboard UI remain version-controlled. The operational dataset and dashboard JSON are regenerated from artifact-backed state.

## Reliability behavior

| Scenario | Pipeline behavior |
| --- | --- |
| Weekend or SEC market holiday | Excluded from planned source dates |
| Temporary SEC fetch failure | Failed date remains eligible for a later retry |
| Invalid row | Quarantined with a validation reason |
| Duplicate CIK + accession pair | Counted as unchanged, not inserted again |
| One or more source dates fail | Curated-state promotion is blocked |
| Successful run | Curated state, run ledger, raw snapshots, and dashboard are updated |

## Limitations

- The pipeline tracks daily-index metadata for 10-K, 10-Q, and 8-K forms; it does not parse filing document contents.
- GitHub Actions artifacts are rolling operational storage, not a permanent historical warehouse.
- GitHub Actions schedules are best-effort; the manual workflow trigger remains available for recovery and backfills.
- SEC availability and response behavior can affect a run, which is why the project records failures and retains source-date retry eligibility.

## Data source

SEC EDGAR daily master indexes:

<https://www.sec.gov/Archives/edgar/daily-index/>

## Technology

Python, httpx, Pydantic, DuckDB, Parquet, pytest, GitHub Actions, and GitHub Pages.