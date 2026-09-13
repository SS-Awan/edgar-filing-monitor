"""Build compact dashboard data from curated Parquet state and run history."""
from __future__ import annotations

import json
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

import duckdb

from edgar_monitor.observability import read_run_records


def format_date(value: date | datetime | None) -> str | None:
    """Convert a date-like database value into a JSON-friendly string."""
    return value.isoformat() if value is not None else None


def build_dashboard_data(
    curated_directory: Path,
    ledger_path: Path,
    generated_at: datetime | None = None,
) -> dict[str, Any]:
    """Query curated Parquet state and return dashboard-ready metrics."""
    run_records = (
        read_run_records(ledger_path) if ledger_path.exists() else ()
    )
    parquet_files = list(curated_directory.rglob("*.parquet"))

    dashboard_data: dict[str, Any] = {
        "generated_at": (
            generated_at or datetime.now(UTC)
        ).isoformat(),
        "latest_run": (
            run_records[-1].model_dump(mode="json")
            if run_records
            else None
        ),
        "recent_runs": [
            record.model_dump(mode="json") for record in run_records[-10:]
        ],
        "dataset": {
            "curated_relationships": 0,
            "unique_companies": 0,
            "earliest_filing_date": None,
            "latest_filing_date": None,
        },
        "form_type_counts": [],
        "filings_by_date": [],
        "top_companies": [],
    }

    if not parquet_files:
        return dashboard_data

    parquet_glob = (curated_directory / "**" / "*.parquet").as_posix()

    with duckdb.connect(database=":memory:") as connection:
        dataset_row = connection.execute(
            """
            SELECT
                COUNT(*) AS curated_relationships,
                COUNT(DISTINCT cik) AS unique_companies,
                MIN(filing_date) AS earliest_filing_date,
                MAX(filing_date) AS latest_filing_date
            FROM read_parquet(?)
            """,
            [parquet_glob],
        ).fetchone()

        form_type_rows = connection.execute(
            """
            SELECT form_type, COUNT(*) AS filing_count
            FROM read_parquet(?)
            GROUP BY form_type
            ORDER BY filing_count DESC, form_type
            """,
            [parquet_glob],
        ).fetchall()

        filing_date_rows = connection.execute(
            """
            SELECT filing_date, COUNT(*) AS filing_count
            FROM read_parquet(?)
            GROUP BY filing_date
            ORDER BY filing_date
            """,
            [parquet_glob],
        ).fetchall()

        company_rows = connection.execute(
            """
            SELECT
                cik,
                company_name,
                COUNT(*) AS filing_count
            FROM read_parquet(?)
            GROUP BY cik, company_name
            ORDER BY filing_count DESC, company_name
            LIMIT 10
            """,
            [parquet_glob],
        ).fetchall()

    if dataset_row is None:
        return dashboard_data

    dashboard_data["dataset"] = {
        "curated_relationships": dataset_row[0],
        "unique_companies": dataset_row[1],
        "earliest_filing_date": format_date(dataset_row[2]),
        "latest_filing_date": format_date(dataset_row[3]),
    }
    dashboard_data["form_type_counts"] = [
        {
            "form_type": row[0],
            "filing_count": row[1],
        }
        for row in form_type_rows
    ]
    dashboard_data["filings_by_date"] = [
        {
            "filing_date": format_date(row[0]),
            "filing_count": row[1],
        }
        for row in filing_date_rows
    ]
    dashboard_data["top_companies"] = [
        {
            "cik": row[0],
            "company_name": row[1],
            "filing_count": row[2],
        }
        for row in company_rows
    ]

    return dashboard_data


def write_dashboard_data(
    curated_directory: Path,
    ledger_path: Path,
    output_path: Path,
    generated_at: datetime | None = None,
) -> dict[str, Any]:
    """Build and write dashboard data as formatted JSON."""
    dashboard_data = build_dashboard_data(
        curated_directory=curated_directory,
        ledger_path=ledger_path,
        generated_at=generated_at,
    )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(dashboard_data, indent=2) + "\n",
        encoding="utf-8",
    )

    return dashboard_data