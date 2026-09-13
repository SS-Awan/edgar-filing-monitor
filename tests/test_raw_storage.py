from dataclasses import replace
from datetime import UTC, date, datetime
from hashlib import sha256
from pathlib import Path

import pytest

from edgar_monitor.raw_storage import (
    prune_raw_snapshots,
    write_raw_snapshot,
)
from edgar_monitor.sec_client import FetchedSource


def make_fetched_source(payload: str = "example SEC payload") -> FetchedSource:
    payload_bytes = payload.encode("utf-8")

    return FetchedSource(
        source_date=date(2026, 9, 10),
        source_url=(
            "https://www.sec.gov/Archives/edgar/daily-index/"
            "2026/QTR3/master.20260910.idx"
        ),
        payload=payload,
        payload_sha256=sha256(payload_bytes).hexdigest(),
        payload_bytes=len(payload_bytes),
        fetched_at=datetime(2026, 9, 13, 12, 0, tzinfo=UTC),
        attempts=1,
    )


def test_write_raw_snapshot_preserves_payload_and_metadata(
    tmp_path: Path,
) -> None:
    fetched_source = make_fetched_source()

    snapshot = write_raw_snapshot(fetched_source, tmp_path)

    assert snapshot.payload_path.read_text(encoding="utf-8") == (
        "example SEC payload"
    )
    assert snapshot.metadata_path.exists()
    assert snapshot.payload_sha256 == fetched_source.payload_sha256
    assert snapshot.payload_bytes == fetched_source.payload_bytes


def test_write_raw_snapshot_is_idempotent_for_identical_payload(
    tmp_path: Path,
) -> None:
    fetched_source = make_fetched_source()

    first_snapshot = write_raw_snapshot(fetched_source, tmp_path)
    second_snapshot = write_raw_snapshot(fetched_source, tmp_path)

    assert first_snapshot == second_snapshot
    assert len(list(tmp_path.rglob("*.idx"))) == 1
    assert len(list(tmp_path.rglob("*.json"))) == 1


def test_write_raw_snapshot_rejects_checksum_mismatch(
    tmp_path: Path,
) -> None:
    fetched_source = make_fetched_source()
    invalid_source = replace(
        fetched_source,
        payload_sha256="not-a-valid-checksum",
    )

    with pytest.raises(ValueError, match="checksum"):
        write_raw_snapshot(invalid_source, tmp_path)


def test_prune_raw_snapshots_removes_only_expired_partitions(
    tmp_path: Path,
) -> None:
    expired_directory = tmp_path / "source_date=2026-08-01"
    retained_directory = tmp_path / "source_date=2026-09-10"
    unrelated_directory = tmp_path / "notes"

    expired_directory.mkdir()
    retained_directory.mkdir()
    unrelated_directory.mkdir()

    deleted_partitions = prune_raw_snapshots(
        tmp_path,
        today=date(2026, 9, 13),
        retention_days=30,
    )

    assert deleted_partitions == 1
    assert not expired_directory.exists()
    assert retained_directory.exists()
    assert unrelated_directory.exists()