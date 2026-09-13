from datetime import UTC, date, datetime
from hashlib import sha256
from pathlib import Path

import pytest

from edgar_monitor.models import FilingRecord
from edgar_monitor.observability import read_run_records
from edgar_monitor.pipeline import run_pipeline
from edgar_monitor.sec_client import FetchedSource, SourceFetchError

FIXTURE_PATH = Path(__file__).parent / "fixtures" / "sample_master.idx"


def make_fetched_source(source_date: date, payload: str) -> FetchedSource:
    return FetchedSource(
        source_date=source_date,
        source_url="https://example.test/master.idx",
        payload=payload,
        payload_sha256=sha256(payload.encode("utf-8")).hexdigest(),
        payload_bytes=len(payload.encode("utf-8")),
        fetched_at=datetime(2026, 9, 13, 12, 0, tzinfo=UTC),
        attempts=1,
    )


def make_existing_record() -> FilingRecord:
    return FilingRecord(
        cik="320193",
        company_name="Existing Company",
        form_type="8-K",
        filing_date=date(2026, 5, 1),
        filename="edgar/data/320193/0000320193-26-000999.txt",
        accession_number="0000320193-26-000999",
        source_line_number=1,
    )


def test_run_pipeline_creates_curated_data_and_run_ledger(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    payload = FIXTURE_PATH.read_text(encoding="utf-8")
    source_date = date(2026, 9, 10)

    monkeypatch.setattr(
        "edgar_monitor.pipeline.fetch_daily_master_index",
        lambda _source_date, _client: make_fetched_source(source_date, payload),
    )

    result = run_pipeline(
        source_dates=(source_date,),
        client=object(),  # type: ignore[arg-type]
        existing_records=(),
        output_directory=tmp_path / "curated",
        ledger_path=tmp_path / "run_ledger.jsonl",
        run_id="successful-run",
    )

    assert result.run_record.status == "succeeded"
    assert result.run_record.raw_rows == 4
    assert result.run_record.validated_records == 4
    assert result.run_record.quarantined_records == 0
    assert result.run_record.target_records == 3
    assert result.run_record.inserted_records == 3
    assert list((tmp_path / "curated").rglob("*.parquet"))
    assert read_run_records(tmp_path / "run_ledger.jsonl") == (result.run_record,)


def test_run_pipeline_preserves_existing_records_after_fetch_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source_date = date(2026, 9, 10)

    def raise_fetch_error(_source_date: date, _client: object) -> FetchedSource:
        raise SourceFetchError("temporary SEC outage")

    monkeypatch.setattr(
        "edgar_monitor.pipeline.fetch_daily_master_index",
        raise_fetch_error,
    )

    result = run_pipeline(
        source_dates=(source_date,),
        client=object(),  # type: ignore[arg-type]
        existing_records=(make_existing_record(),),
        output_directory=tmp_path / "curated",
        ledger_path=tmp_path / "run_ledger.jsonl",
        run_id="failed-run",
    )

    assert result.run_record.status == "failed"
    assert result.run_record.source_dates_failed == 1
    assert result.run_record.inserted_records == 0
    assert len(result.merge_result.records) == 1
    assert list((tmp_path / "curated").rglob("*.parquet"))


def test_run_pipeline_records_schema_failure_without_writing_empty_state(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source_date = date(2026, 9, 10)

    monkeypatch.setattr(
        "edgar_monitor.pipeline.fetch_daily_master_index",
        lambda _source_date, _client: make_fetched_source(
            source_date,
            "not a valid SEC index",
        ),
    )

    result = run_pipeline(
        source_dates=(source_date,),
        client=object(),  # type: ignore[arg-type]
        existing_records=(),
        output_directory=tmp_path / "curated",
        ledger_path=tmp_path / "run_ledger.jsonl",
        run_id="schema-failure-run",
    )

    assert result.run_record.status == "failed"
    assert result.run_record.source_dates_failed == 1
    assert result.run_record.error_message is not None
    assert not (tmp_path / "curated").exists()