from __future__ import annotations

from collections.abc import Iterator

from celery import Celery

from app.tasks.scheduler import ReloadingPersistentScheduler


def _build_scheduler(
    tmp_path,
    monkeypatch,
    loader_results: list[dict | None],
) -> ReloadingPersistentScheduler:
    app = Celery("test-beat")
    app.conf.beat_schedule = {}
    app.conf.enable_utc = True
    app.conf.result_expires = None
    app.conf.timezone = "UTC"

    values: Iterator[dict | None] = iter(loader_results)
    last_value = loader_results[-1]

    def fake_loader(*, return_none_on_error: bool = False):
        _ = return_none_on_error
        try:
            return next(values)
        except StopIteration:
            return last_value

    monkeypatch.setattr("app.tasks.scheduler.load_task_schedules_from_db", fake_loader)

    scheduler = ReloadingPersistentScheduler(
        app=app,
        schedule_filename=str(tmp_path / "celerybeat-schedule"),
    )
    scheduler.db_schedule_reload_interval = 0
    return scheduler


def test_reloading_scheduler_recovers_after_startup_db_outage(
    tmp_path,
    monkeypatch,
) -> None:
    db_schedule = {
        "db-task": {
            "task": "app.tasks.scheduled.system_health_check",
            "schedule": 60.0,
        }
    }
    scheduler = _build_scheduler(tmp_path, monkeypatch, [None, db_schedule])
    try:
        assert "db-task" not in scheduler.schedule

        scheduler.refresh_db_schedule(force=True)

        assert "db-task" in scheduler.schedule
        assert scheduler._db_entry_names == {"db-task"}
    finally:
        scheduler.close()


def test_reloading_scheduler_keeps_last_good_schedule_on_db_failure(
    tmp_path,
    monkeypatch,
) -> None:
    db_schedule = {
        "db-task": {
            "task": "app.tasks.scheduled.system_health_check",
            "schedule": 60.0,
        }
    }
    scheduler = _build_scheduler(tmp_path, monkeypatch, [db_schedule, None])
    try:
        assert "db-task" in scheduler.schedule

        scheduler.refresh_db_schedule(force=True)

        assert "db-task" in scheduler.schedule
        assert scheduler._db_entry_names == {"db-task"}
    finally:
        scheduler.close()


def test_reloading_scheduler_removes_db_entries_on_successful_empty_reload(
    tmp_path,
    monkeypatch,
) -> None:
    db_schedule = {
        "db-task": {
            "task": "app.tasks.scheduled.system_health_check",
            "schedule": 60.0,
        }
    }
    scheduler = _build_scheduler(tmp_path, monkeypatch, [db_schedule, {}])
    try:
        assert "db-task" in scheduler.schedule

        scheduler.refresh_db_schedule(force=True)

        assert "db-task" not in scheduler.schedule
        assert scheduler._db_entry_names == set()
    finally:
        scheduler.close()


def test_reloading_scheduler_recovers_when_create_schedule_hits_eoferror(
    tmp_path,
    monkeypatch,
) -> None:
    original_create_schedule = ReloadingPersistentScheduler._create_schedule
    create_calls = {"count": 0}

    def flaky_create_schedule(self) -> None:
        create_calls["count"] += 1
        if create_calls["count"] == 1:
            raise EOFError("Ran out of input")
        original_create_schedule(self)

    monkeypatch.setattr(
        ReloadingPersistentScheduler,
        "_create_schedule",
        flaky_create_schedule,
    )

    scheduler = _build_scheduler(tmp_path, monkeypatch, [{}])
    try:
        assert create_calls["count"] == 2
        assert isinstance(scheduler.schedule, dict)
    finally:
        scheduler.close()
