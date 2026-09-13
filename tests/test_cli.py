from datetime import date
from pathlib import Path

from edgar_monitor.cli import (
    promote_curated_state,
    run_scheduled_pipeline,
)
from edgar_monitor.scheduling import ScheduledSourcePlan


def test_promote_curated_state_replaces_old_state(tmp_path: Path) -> None:
    curated_directory = tmp_path / "curated"
    next_curated_directory = tmp_path / "next_curated"

    curated_directory.mkdir()
    (curated_directory / "old_state.txt").write_text("old", encoding="utf-8")

    next_curated_directory.mkdir()
    (next_curated_directory / "new_state.txt").write_text(
        "new",
        encoding="utf-8",
    )

    promoted = promote_curated_state(
        next_curated_directory,
        curated_directory,
    )

    assert promoted is True
    assert (curated_directory / "new_state.txt").read_text(encoding="utf-8") == "new"
    assert not (curated_directory / "old_state.txt").exists()
    assert not next_curated_directory.exists()


def test_promote_curated_state_returns_false_without_new_state(
    tmp_path: Path,
) -> None:
    promoted = promote_curated_state(
        tmp_path / "next_curated",
        tmp_path / "curated",
    )

    assert promoted is False


def test_run_scheduled_pipeline_uses_planned_dates(
    tmp_path: Path,
    monkeypatch,
) -> None:
    planned_dates = (
        date(2026, 9, 9),
        date(2026, 9, 10),
        date(2026, 9, 11),
    )
    captured_dates: list[tuple[date, ...]] = []

    monkeypatch.setattr(
        "edgar_monitor.cli.build_scheduled_source_plan",
        lambda **_kwargs: ScheduledSourcePlan(
            run_date=date(2026, 9, 13),
            source_dates=planned_dates,
            failed_source_dates=(),
        ),
    )
    monkeypatch.setattr(
        "edgar_monitor.cli.run_dates_pipeline",
        lambda **kwargs: captured_dates.append(kwargs["source_dates"]) or 0,
    )

    exit_code = run_scheduled_pipeline(
        run_date=date(2026, 9, 13),
        user_agent="Example contact@example.com",
        state_directory=tmp_path / "state",
        lookback_days=3,
    )

    assert exit_code == 0
    assert captured_dates == [planned_dates]