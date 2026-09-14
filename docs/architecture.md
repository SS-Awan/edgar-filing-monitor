# Architecture

## Purpose

EDGAR Filing Monitor is a scheduled batch pipeline for SEC EDGAR daily filing-index metadata. It retrieves daily source indexes, validates the records, preserves raw-source provenance, maintains a curated dataset for selected filing forms, and publishes pipeline-health metrics through a static dashboard.

The pipeline targets 10-K, 10-Q, and 8-K index records. It does not scrape filing-document contents.

## System flow

```text
SEC daily master index
  |
  v
SEC HTTP client
  |
  v
Checksum-addressed raw snapshot + provenance JSON
  |
  v
Master-index parser
  |
  v
Validation and quarantine
  |
  v
Target-form curation
  |
  v
Composite-key idempotent merge
  |
  v
Partitioned Parquet curated state + JSONL run ledger
  |
  v
DuckDB dashboard aggregation
  |
  v
Static JSON dashboard data
  |
  v
GitHub Pages
```

## Components

| Component | Responsibility |
| --- | --- |
| `sec_client.py` | Builds daily SEC index URLs, sends compliant HTTP requests, and returns fetched-source metadata. |
| `raw_storage.py` | Writes content-addressed raw payloads and JSON provenance metadata, including SHA-256 checksum, source URL, fetch time, and attempt count. |
| `index_parser.py` | Parses the SEC master-index header and pipe-delimited rows into structured raw records. |
| `validation.py` | Enforces required-field, date, filename, form-type, and accession-number rules; invalid records are quarantined. |
| `curation.py` | Selects target forms and merges records using the composite `(CIK, accession_number)` relationship key. |
| `planning.py` | Plans rolling lookback dates, manual backfills, failed-date retries, weekends, and SEC market holidays. |
| `pipeline.py` | Orchestrates fetch, raw persistence, parse, validate, curate, merge, state promotion, and run-ledger recording. |
| `observability.py` | Persists and reads JSONL run records. |
| `dashboard_data.py` | Queries curated Parquet state through DuckDB and writes static dashboard JSON. |
| `cli.py` | Provides one-date and scheduled command-line execution modes. |
| `scripts/build_dashboard_data.py` | Generates `site/data/dashboard.json` for local preview and GitHub Pages deployment. |

## Data contracts

### Raw source

Each successful SEC fetch produces:

```text
data/raw/source_date=YYYY-MM-DD/
  master.<sha256>.idx
  master.<sha256>.json
```

The metadata JSON records:

- Source date
- Source URL
- Fetch timestamp
- Request attempt count
- Payload byte count
- Payload SHA-256 checksum
- Payload filename

The checksum makes the stored raw payload traceable and allows identical source content to be recognized.

### Curated state

Curated filing relationships are stored as partitioned Parquet files:

```text
data/state/curated/
  filing_year=YYYY/
    form_type=8-K/
    form_type=10-Q/
    form_type=10-K/
```

The primary relationship key is:

```text
(CIK, accession_number)
```

An accession number alone is not sufficient. Live SEC index data showed that a single accession can appear under more than one CIK relationship, so the pipeline preserves those relationships rather than collapsing them.

### Run ledger

Every run appends one JSON object to:

```text
data/state/run_ledger.jsonl
```

A record includes run ID, status, timestamps, planned/succeeded/failed source-date counts, raw/validated/quarantined/target row counts, insert/update/unchanged counts, and failure details when applicable.

## Reliability model

### Date planning

Scheduled mode starts from the most recently completed dates and plans a rolling lookback window. It excludes:

- Weekends
- SEC market holidays
- Future dates

Previously failed eligible dates are included in later plans so a transient source failure can be retried.

The SEC holiday logic was added after a real scheduled run encountered Labor Day, when no daily index was published.

### Validation and quarantine

Rows that fail validation are isolated from curated state with an explicit reason. The pipeline reports both validated and quarantined counts in the run ledger and dashboard.

### Idempotency

Before writing curated state, the pipeline compares target relationships using `(CIK, accession_number)`.

Each target relationship is classified as:

- Inserted
- Updated
- Unchanged

This allows repeated runs over the same source dates without duplicating curated relationships.

### Atomic promotion

A pipeline run may fetch and process several dates. Curated state is promoted only when all planned source dates succeed.

If one date fails:

1. The run is recorded as failed.
2. Failure details remain in the JSONL ledger.
3. Existing curated state remains intact.
4. The failed date stays eligible for future retry.

This prevents partial data from replacing known-good curated state.

## Storage and version-control boundary

Git stores only durable project assets:

- Application code
- Tests and fixed fixtures
- Documentation
- Workflow definitions
- Dashboard HTML, CSS, and JavaScript

Git does not store recurring operational data:

```text
data/raw/
data/state/
site/data/
```

GitHub Actions artifacts carry rolling operational state:

| Artifact | Contents | Retention |
| --- | --- | ---: |
| `edgar-pipeline-state` | Curated Parquet state and run ledger | 7 days |
| `edgar-raw-snapshots` | Raw SEC source snapshots and provenance metadata | 30 days |
| `github-pages` | Generated static dashboard deployment | Managed by GitHub Pages |

The SEC archive remains the authoritative historical source.

## GitHub Actions

### Continuous integration

`ci.yml` runs the pytest suite on every push and pull request.

### Scheduled pipeline and deployment

`scheduled_pipeline.yml` runs on weekdays and supports manual dispatch.

The workflow:

1. Restores the latest available state and raw-snapshot artifacts.
2. Runs the scheduled pipeline using `SEC_USER_AGENT` from a GitHub Actions secret.
3. Generates dashboard JSON from the resulting curated state and ledger.
4. Uploads refreshed state and raw-snapshot artifacts.
5. Deploys the static `site/` directory to GitHub Pages after a successful ingest job.

The deployment job depends on successful ingestion. A failed ingestion does not replace the public dashboard.

## Security and operational configuration

The SEC User-Agent is stored as the `SEC_USER_AGENT` GitHub Actions secret. It is not committed to the repository.

Local execution receives the same value through an environment variable in the active terminal session.

## Non-goals

This project deliberately does not include:

- Full EDGAR filing-document scraping
- A long-term cloud data warehouse
- A database API or React application
- Spark, Kafka, Airflow, Docker, Kubernetes, or cloud infrastructure

The goal is a focused, explainable, entry-level data-engineering system with reliable ingestion, state management, and observability.