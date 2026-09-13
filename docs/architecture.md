# Architecture

## Purpose

EDGAR Filing Monitor is a scheduled batch pipeline that collects SEC EDGAR daily filing-index data, validates it, maintains a rolling curated dataset of 10-K, 10-Q, and 8-K filings, and publishes pipeline-health metrics.

## Data flow

SEC daily index
→ raw artifact
→ validation and quarantine
→ DuckDB merge
→ partitioned Parquet state
→ run ledger and dashboard data
→ GitHub Pages

## Storage boundary

Recurring raw payloads, Parquet files, DuckDB files, run ledgers, and generated dashboard data are not committed to Git.

Git stores only application code, tests, documentation, and small fixed test fixtures. GitHub Actions artifacts hold short-lived operational state; the SEC archive remains the authoritative historical source.

## Reliability principles

- Accession number is the filing idempotency key.
- Each run uses a rolling lookback window.
- Source payloads receive SHA-256 checksums for provenance.
- Invalid rows are quarantined with a reason instead of silently loaded.
- Failed source dates remain eligible for retry.
- Schema changes stop unsafe state replacement.