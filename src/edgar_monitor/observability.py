"""Persist and read pipeline-run metadata for observability."""

from __future__ import annotations

from datetime import datetime
import json
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field, model_validator


class PipelineRunRecord(BaseModel):
    """Metrics and outcome for one pipeline execution."""

    run_id: str = Field(min_length=1)
    status: Literal["succeeded", "failed"]
    started_at: datetime
    finished_at: datetime
    source_dates_planned: int = Field(ge=0)
    source_dates_succeeded: int = Field(ge=0)
    source_dates_failed: int = Field(ge=0)
    raw_rows: int = Field(ge=0)
    validated_records: int = Field(ge=0)
    quarantined_records: int = Field(ge=0)
    target_records: int = Field(ge=0)
    inserted_records: int = Field(ge=0)
    updated_records: int = Field(ge=0)
    unchanged_records: int = Field(ge=0)
    error_message: str | None = None

    @model_validator(mode="after")
    def validate_timestamps_and_source_counts(self) -> "PipelineRunRecord":
        if self.finished_at < self.started_at:
            raise ValueError("finished_at must not be earlier than started_at.")

        completed_source_dates = (
            self.source_dates_succeeded + self.source_dates_failed
        )
        if completed_source_dates > self.source_dates_planned:
            raise ValueError("Completed source dates cannot exceed planned source dates.")

        return self


def append_run_record(ledger_path: Path, record: PipelineRunRecord) -> None:
    """Append one run record as a JSON Lines entry."""
    ledger_path.parent.mkdir(parents=True, exist_ok=True)

    with ledger_path.open("a", encoding="utf-8") as ledger_file:
        ledger_file.write(record.model_dump_json() + "\n")


def read_run_records(ledger_path: Path) -> tuple[PipelineRunRecord, ...]:
    """Read all run records from a JSON Lines ledger."""
    if not ledger_path.exists():
        return ()

    with ledger_path.open(encoding="utf-8") as ledger_file:
        return tuple(
            PipelineRunRecord.model_validate_json(line)
            for line in ledger_file
            if line.strip()
        )