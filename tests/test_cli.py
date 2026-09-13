from pathlib import Path

from edgar_monitor.cli import promote_curated_state


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