"""Run the EDGAR Filing Monitor pipeline from the command line."""
from __future__ import annotations

import argparse
import os
import shutil
import sys
import uuid
from datetime import date
from pathlib import Path

from edgar_monitor.curation import read_partitioned_parquet
from edgar_monitor.pipeline import run_pipeline
from edgar_monitor.scheduling import build_scheduled_source_plan
from edgar_monitor.sec_client import create_sec_client


def parse_source_date(value: str) -> date:
    """Parse a source date supplied as YYYY-MM-DD."""
    try:
        return date.fromisoformat(value)
    except ValueError as error:
        raise argparse.ArgumentTypeError(
            "Source date must use YYYY-MM-DD, for example 2026-09-10."
        ) from error


def promote_curated_state(
    next_curated_directory: Path,
    curated_directory: Path,
) -> bool:
    """Replace curated state only after a successful pipeline run."""
    if not next_curated_directory.exists():
        return False

    rollback_directory = curated_directory.with_name("curated_previous")

    if rollback_directory.exists():
        shutil.rmtree(rollback_directory)

    if curated_directory.exists():
        curated_directory.replace(rollback_directory)

    try:
        next_curated_directory.replace(curated_directory)
    except Exception:
        if rollback_directory.exists():
            rollback_directory.replace(curated_directory)
        raise
    else:
        if rollback_directory.exists():
            shutil.rmtree(rollback_directory)

    return True


def print_run_summary(run_record: object, promoted: bool) -> None:
    """Print the fields recorded by the pipeline run ledger."""
    model_dump = getattr(run_record, "model_dump")
    summary = model_dump(mode="json")

    print("\nPipeline run summary")
    print("-" * 40)

    for field_name, value in summary.items():
        print(f"{field_name}: {value}")

    print(f"curated_state_promoted: {promoted}")


def run_dates_pipeline(
    source_dates: tuple[date, ...],
    user_agent: str,
    state_directory: Path,
    run_id: str | None = None,
) -> int:
    """Run one or more SEC source dates and safely promote curated state."""
    state_directory.mkdir(parents=True, exist_ok=True)

    curated_directory = state_directory / "curated"
    next_curated_directory = state_directory / "next_curated"
    ledger_path = state_directory / "run_ledger.jsonl"
    raw_directory = state_directory.parent / "raw"

    if next_curated_directory.exists():
        shutil.rmtree(next_curated_directory)

    existing_records = read_partitioned_parquet(curated_directory)

    with create_sec_client(user_agent) as client:
        result = run_pipeline(
            source_dates=source_dates,
            client=client,
            existing_records=existing_records,
            output_directory=next_curated_directory,
            ledger_path=ledger_path,
            run_id=run_id or str(uuid.uuid4()),
            raw_directory=raw_directory,
        )

    promoted = False
    if result.run_record.status == "succeeded":
        promoted = promote_curated_state(
            next_curated_directory,
            curated_directory,
        )
    elif next_curated_directory.exists():
        shutil.rmtree(next_curated_directory)

    print_run_summary(result.run_record, promoted)

    return 0 if result.run_record.status == "succeeded" else 1


def run_local_pipeline(
    source_date: date,
    user_agent: str,
    state_directory: Path,
    run_id: str | None = None,
) -> int:
    """Run one manually selected SEC source date."""
    return run_dates_pipeline(
        source_dates=(source_date,),
        user_agent=user_agent,
        state_directory=state_directory,
        run_id=run_id,
    )


def run_scheduled_pipeline(
    run_date: date,
    user_agent: str,
    state_directory: Path,
    lookback_days: int,
) -> int:
    """Run the rolling lookback plus previously failed source dates."""
    ledger_path = state_directory / "run_ledger.jsonl"
    plan = build_scheduled_source_plan(
        run_date=run_date,
        ledger_path=ledger_path,
        lookback_days=lookback_days,
    )

    planned_dates = ", ".join(
        source_date.isoformat() for source_date in plan.source_dates
    )
    print(f"Scheduled source dates: {planned_dates}")

    return run_dates_pipeline(
        source_dates=plan.source_dates,
        user_agent=user_agent,
        state_directory=state_directory,
    )


def build_parser() -> argparse.ArgumentParser:
    """Build the command-line argument parser."""
    parser = argparse.ArgumentParser(
        description="Run the EDGAR Filing Monitor."
    )

    run_mode = parser.add_mutually_exclusive_group(required=True)
    run_mode.add_argument(
        "--source-date",
        type=parse_source_date,
        help="Run one SEC daily index date in YYYY-MM-DD format.",
    )
    run_mode.add_argument(
        "--scheduled",
        action="store_true",
        help="Run the rolling business-day lookback plan.",
    )

    parser.add_argument(
        "--run-date",
        type=parse_source_date,
        help="Date used to calculate a scheduled lookback.",
    )
    parser.add_argument(
        "--lookback-days",
        type=int,
        default=7,
        help="Business days included in a scheduled run. Default: 7.",
    )
    parser.add_argument(
        "--state-dir",
        type=Path,
        default=Path("data/state"),
        help="Ignored local directory for Parquet state and the run ledger.",
    )
    return parser


def main() -> int:
    """Run the command-line application."""
    parser = build_parser()
    arguments = parser.parse_args()

    user_agent = os.getenv("SEC_USER_AGENT", "").strip()
    if not user_agent:
        parser.error(
            "SEC_USER_AGENT is required. Set it to an identifying value with "
            "your contact email before running the pipeline."
        )

    if arguments.source_date is not None:
        return run_local_pipeline(
            source_date=arguments.source_date,
            user_agent=user_agent,
            state_directory=arguments.state_dir,
        )

    return run_scheduled_pipeline(
        run_date=arguments.run_date or date.today(),
        user_agent=user_agent,
        state_directory=arguments.state_dir,
        lookback_days=arguments.lookback_days,
    )


if __name__ == "__main__":
    sys.exit(main())