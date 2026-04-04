from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path

import pytest


TRELLIS_SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
if str(TRELLIS_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(TRELLIS_SCRIPTS))

from common.task_utils import archive_task_complete, load_archive_ready_task


def _make_task_dir(tmp_path: Path, name: str = "04-04-demo-task") -> Path:
    task_dir = tmp_path / ".trellis" / "tasks" / name
    task_dir.mkdir(parents=True)
    return task_dir


@pytest.mark.parametrize(
    ("raw_task_json", "expected_fragment"),
    [
        (None, "must have task.json"),
        ("{}", "must contain an object"),
        ('{"status": "active"}', "must be marked completed"),
    ],
)
def test_archive_task_complete_rejects_unready_tasks(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    raw_task_json: str | None,
    expected_fragment: str,
) -> None:
    task_dir = _make_task_dir(tmp_path)
    task_json_path = task_dir / "task.json"
    if raw_task_json is not None:
        task_json_path.write_text(raw_task_json, encoding="utf-8")

    result = archive_task_complete(task_dir, tmp_path)

    captured = capsys.readouterr()
    assert result == {}
    assert task_dir.is_dir()
    assert expected_fragment in captured.err


def test_load_archive_ready_task_accepts_completed_status(tmp_path: Path) -> None:
    task_dir = _make_task_dir(tmp_path)
    (task_dir / "task.json").write_text('{"status": "completed"}', encoding="utf-8")

    data, error = load_archive_ready_task(task_dir)

    assert error is None
    assert data is not None
    assert data["status"] == "completed"


def test_archive_task_complete_stamps_completed_at_and_moves_task(tmp_path: Path) -> None:
    task_dir = _make_task_dir(tmp_path)
    (task_dir / "task.json").write_text('{"status": "completed"}', encoding="utf-8")

    result = archive_task_complete(task_dir, tmp_path)

    year_month = datetime.now().strftime("%Y-%m")
    archived_dir = tmp_path / ".trellis" / "tasks" / "archive" / year_month / task_dir.name
    archived_task_json = archived_dir / "task.json"

    assert result == {"archived_to": str(archived_dir)}
    assert not task_dir.exists()
    assert archived_dir.is_dir()
    assert archived_task_json.is_file()
    assert datetime.now().strftime("%Y-%m-%d") in archived_task_json.read_text(
        encoding="utf-8"
    )
