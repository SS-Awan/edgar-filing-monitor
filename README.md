# EDGAR Filing Monitor

A reliable batch pipeline for SEC EDGAR daily filing-index data.

## Status

**Under development.** The repository currently contains the initial project structure and architecture. No live SEC ingestion, pipeline metrics, automated schedule, or public dashboard has been implemented yet.

## Planned pipeline

```text
SEC daily index
→ raw artifact
→ validation and quarantine
→ DuckDB merge
→ partitioned Parquet state
→ run ledger and dashboard data
→ GitHub Pages
```

## Intended scope

The pipeline will process SEC daily-index records for:

* 10-K filings
* 10-Q filings
* 8-K filings

It is designed to demonstrate validation, provenance checksums, accession-number idempotency, rolling-lookback recovery, quarantined invalid records, and pipeline observability.

## Storage approach

Recurring data will not be committed to Git. The repository stores code, documentation, and small fixed test fixtures only. Short-lived GitHub Actions artifacts will hold operational state, while SEC archives remain the source of historical raw data.

## Technology direction

Python, httpx, Pydantic, DuckDB, Parquet, pytest, GitHub Actions, and GitHub Pages.

## Project structure

```text
src/edgar_monitor/   Application package
tests/               Automated tests and fixed fixtures
docs/                Architecture and technical decisions
```
