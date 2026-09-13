from datetime import UTC, date, datetime
from hashlib import sha256
from pathlib import Path

import pytest

from edgar_monitor.pipeline import run_pipeline
from edgar_monitor.sec_client import FetchedSource


def make_fetched_source(source_date: date) -> FetchedSource:
    """Create a fixed current-format SEC response for a pipeline test."""
    payload = """Description: Daily Index of EDGAR Dissemination Feed

CIK|Company Name|Form Type|Date Filed|File Name
------------------------------------------------
320193|APPLE INC|10-K|20260910|edgar/data/320193/0000320193-26-000001.txt
"""
    payload_bytes = payload.encode("utf-8")

    return FetchedSource(
        source_date=source_date,
        source_url="https://example.test/master.idx",
        payload=payload,
        payload_sha256=sha256(payload_bytes).hexdigest(),
        payload_bytes=len(payload_bytes),
        fetched_at=datetime(2026, 9, 13, 12, 0, tzinfo=UTC),
        attempts=1,
    )


def test_pipeline_preserves_raw_snapshot_and_prunes_expired_data(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source_date = date(2026, 9, 10)
    raw_directory = tmp_path / "raw"
    expired_directory = raw_directory / "source_date=2026-08-01"
    expired_directory.mkdir(parents=True)

    monkeypatch.setattr(
        "edgar_monitor.pipeline.fetch_daily_master_index",
        lambda _source_date, _client: make_fetched_source(source_date),
    )

    result = run_pipeline(
        source_dates=(source_date,),
        client=object(),  # type: ignore[arg-type]
        existing_records=(),
        output_directory=tmp_path / "next_curated",
        ledger_path=tmp_path / "run_ledger.jsonl",
        run_id="raw-snapshot-test",
        raw_directory=raw_directory,
        retention_today=date(2026, 9, 13),
    )

    snapshot_directory = raw_directory / "source_date=2026-09-10"

    assert result.run_record.status == "succeeded"
    assert len(list(snapshot_directory.glob("*.idx"))) == 1
    assert len(list(snapshot_directory.glob("*.json"))) == 1
    assert not expired_directory.exists()