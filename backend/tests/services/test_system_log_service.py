from __future__ import annotations

import os
import shutil
from datetime import datetime, timedelta
from pathlib import Path

from app.services.system.system_log_service import (
    LOG_SCOPE_CATEGORY,
    LOG_SCOPE_CURRENT_FILE,
    SystemLogService,
)

_BASE_TEMP_DIR = (
    Path(__file__).resolve().parents[2]
    / ".codex-temp"
    / "pytest-temp"
    / "system-log-service"
)


def _build_service(log_dir: Path) -> SystemLogService:
    service = SystemLogService.__new__(SystemLogService)
    service._log_dir = log_dir
    return service


def _make_test_dir(name: str) -> Path:
    path = _BASE_TEMP_DIR / name
    shutil.rmtree(path, ignore_errors=True)
    path.mkdir(parents=True, exist_ok=True)
    return path


def _write_log(path: Path, content: str, *, mtime: datetime | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    if mtime is not None:
        timestamp = mtime.timestamp()
        os.utime(path, (timestamp, timestamp))


def test_read_log_file_filters_entries_by_keyword_and_date() -> None:
    test_dir = _make_test_dir("keyword-date")
    service = _build_service(test_dir)
    log_path = test_dir / "app.2026-04-11.log"
    _write_log(
        log_path,
        "\n".join(
            [
                "2026-04-10 10:00:00 | INFO | old line",
                "2026-04-11 11:00:00 | ERROR | target exploded",
                '  File "worker.py", line 1, in run',
                "Traceback (most recent call last):",
                "2026-04-12 12:00:00 | INFO | newer line",
            ]
        ),
    )

    result = service.read_log_file(
        filename=log_path.name,
        keyword="exploded",
        start_date=datetime(2026, 4, 11).date(),
        end_date=datetime(2026, 4, 11).date(),
        scope=LOG_SCOPE_CURRENT_FILE,
    )

    assert result is not None
    assert result.total_entries == 1
    assert result.total_lines == 3
    assert result.items == [
        ("app.2026-04-11.log", 2, "2026-04-11 11:00:00 | ERROR | target exploded"),
        ("app.2026-04-11.log", 3, '  File "worker.py", line 1, in run'),
        ("app.2026-04-11.log", 4, "Traceback (most recent call last):"),
    ]


def test_list_log_files_marks_daily_file_as_current_when_present() -> None:
    test_dir = _make_test_dir("daily-current")
    service = _build_service(test_dir)
    today = datetime.now().date()
    current_daily = test_dir / f"app.{today.isoformat()}.log"
    legacy_current = test_dir / "app.log"
    rotated = test_dir / "app.log.1"

    _write_log(current_daily, "2026-04-16 08:00:00 | INFO | daily")
    _write_log(legacy_current, "2026-04-15 08:00:00 | INFO | legacy")
    _write_log(rotated, "2026-04-14 08:00:00 | INFO | rotated")

    files = {item.name: item for item in service.list_log_files(category="app")}

    assert files[current_daily.name].is_current is True
    assert files[legacy_current.name].is_current is False
    assert files[rotated.name].is_current is False


def test_read_log_file_supports_category_scope_across_files() -> None:
    test_dir = _make_test_dir("category-scope")
    service = _build_service(test_dir)
    older_path = test_dir / "app.2026-04-10.log"
    newer_path = test_dir / "app.2026-04-11.log"
    base_time = datetime(2026, 4, 11, 12, 0, 0)

    _write_log(
        older_path,
        "2026-04-10 08:00:00 | INFO | older entry",
        mtime=base_time - timedelta(days=1),
    )
    _write_log(
        newer_path,
        "2026-04-11 09:00:00 | INFO | newer entry",
        mtime=base_time,
    )

    result = service.read_log_file(
        filename=newer_path.name,
        page=1,
        page_size=10,
        reverse=True,
        scope=LOG_SCOPE_CATEGORY,
    )

    assert result is not None
    assert result.scope == LOG_SCOPE_CATEGORY
    assert result.category == "app"
    assert result.searched_files == 2
    assert result.total_entries == 2
    assert [item.file_name for item in result.items] == [
        "app.2026-04-11.log",
        "app.2026-04-10.log",
    ]


def test_delete_log_file_blocks_current_daily_file_but_allows_legacy_file() -> None:
    test_dir = _make_test_dir("delete-guard")
    service = _build_service(test_dir)
    today = datetime.now().date()
    current_daily = test_dir / f"app.{today.isoformat()}.log"
    legacy_current = test_dir / "app.log"

    _write_log(current_daily, "2026-04-16 08:00:00 | INFO | current")
    _write_log(legacy_current, "2026-04-15 08:00:00 | INFO | legacy")

    assert service.delete_log_file(current_daily.name) is False
    assert service.delete_log_file(legacy_current.name) is True
    assert legacy_current.exists() is False
