"""Preserve bounded raw SEC snapshots with provenance metadata."""
from __future__ import annotations

import json
import shutil
from dataclasses import dataclass
from datetime import date, timedelta
from hashlib import sha256
from pathlib import Path

from edgar_monitor.sec_client import FetchedSource

DEFAULT_RAW_RETENTION_DAYS = 30


@dataclass(frozen=True)
class RawSnapshot:
    """Locations and provenance for one preserved SEC source payload."""

    source_date: date
    payload_path: Path
    metadata_path: Path
    payload_sha256: str
    payload_bytes: int


def source_date_directory(raw_directory: Path, source_date: date) -> Path:
    """Return the partition directory for one SEC source date."""
    return raw_directory / f"source_date={source_date.isoformat()}"


def write_raw_snapshot(
    fetched_source: FetchedSource,
    raw_directory: Path,
) -> RawSnapshot:
    """Write a checksum-addressed raw payload and its provenance metadata.

    A repeated fetch of identical content resolves to the same file. If SEC
    republishes a source date with changed content, its new checksum creates a
    distinct payload rather than overwriting the previous version.
    """
    payload_bytes = fetched_source.payload.encode("utf-8")
    calculated_checksum = sha256(payload_bytes).hexdigest()

    if calculated_checksum != fetched_source.payload_sha256:
        raise ValueError(
            "Fetched source checksum does not match its payload content."
        )

    destination_directory = source_date_directory(
        raw_directory,
        fetched_source.source_date,
    )
    destination_directory.mkdir(parents=True, exist_ok=True)

    payload_path = (
        destination_directory / f"master.{calculated_checksum}.idx"
    )
    metadata_path = (
        destination_directory / f"master.{calculated_checksum}.json"
    )

    if not payload_path.exists():
        payload_path.write_bytes(payload_bytes)

    metadata = {
        "source_date": fetched_source.source_date.isoformat(),
        "source_url": fetched_source.source_url,
        "payload_sha256": calculated_checksum,
        "payload_bytes": len(payload_bytes),
        "fetched_at": fetched_source.fetched_at.isoformat(),
        "attempts": fetched_source.attempts,
        "payload_file": payload_path.name,
    }

    if not metadata_path.exists():
        metadata_path.write_text(
            json.dumps(metadata, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )

    return RawSnapshot(
        source_date=fetched_source.source_date,
        payload_path=payload_path,
        metadata_path=metadata_path,
        payload_sha256=calculated_checksum,
        payload_bytes=len(payload_bytes),
    )


def prune_raw_snapshots(
    raw_directory: Path,
    today: date,
    retention_days: int = DEFAULT_RAW_RETENTION_DAYS,
) -> int:
    """Remove date partitions older than the configured retention window."""
    if retention_days < 1:
        raise ValueError("retention_days must be at least 1.")

    if not raw_directory.exists():
        return 0

    cutoff_date = today - timedelta(days=retention_days)
    deleted_partitions = 0

    for candidate in raw_directory.iterdir():
        if not candidate.is_dir() or not candidate.name.startswith(
            "source_date="
        ):
            continue

        raw_date = candidate.name.removeprefix("source_date=")

        try:
            source_date = date.fromisoformat(raw_date)
        except ValueError:
            continue

        if source_date < cutoff_date:
            shutil.rmtree(candidate)
            deleted_partitions += 1

    return deleted_partitions