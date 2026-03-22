"""
Database-driven dynamic scheduler / 数据库驱动的动态调度器

Loads periodic task configuration from DB and registers with Celery Beat scheduler.
从数据库加载定时任务配置，注册到 Celery Beat 调度
Supports runtime dynamic addition/removal of schedules.
支持运行时动态添加/移除调度
"""

from __future__ import annotations

import time

from celery import __version__ as celery_version
from celery.beat import PersistentScheduler
from celery.schedules import crontab

from app.celery_app import celery_app
from app.core.database import sync_session_factory
from app.core.logging import LogManager
from app.models.system.periodic_task import PeriodicTask

logger = LogManager.get_logger("queue")


def parse_cron_expression(expression: str) -> crontab:
    """Parse cron expression string to Celery crontab object / 将 cron 表达式字符串解析为 Celery crontab 对象"""
    parts = expression.strip().split()
    if len(parts) != 5:
        raise ValueError(f"Invalid cron expression: {expression}")

    return crontab(
        minute=parts[0],
        hour=parts[1],
        day_of_month=parts[2],
        month_of_year=parts[3],
        day_of_week=parts[4],
    )


def _build_periodic_schedule(tasks: list[PeriodicTask]) -> dict[str, dict]:
    schedule: dict[str, dict] = {}
    for task in tasks:
        entry = {
            "task": task.task_path,
            "args": list(task.args.values()) if task.args else (),
            "kwargs": task.kwargs or {},
        }

        if task.schedule_type == "cron" and task.cron_expression:
            entry["schedule"] = parse_cron_expression(task.cron_expression)
        elif task.schedule_type == "interval" and task.interval_seconds:
            entry["schedule"] = float(task.interval_seconds)
        else:
            logger.warning(
                f"Skipping periodic task '{task.name}': invalid schedule configuration"
            )
            continue

        schedule[task.name] = entry
        logger.info(
            f"Loaded periodic task: {task.name} -> {task.task_path} "
            f"({task.schedule_type})"
        )
    return schedule


def load_periodic_tasks_from_db(
    *,
    return_none_on_error: bool = False,
) -> dict | None:
    """Load periodic tasks from DB and return schedule dict / 从数据库加载定时任务并返回调度配置字典"""
    session = sync_session_factory()
    try:
        tasks = (
            session.query(PeriodicTask)
            .filter(
                PeriodicTask.is_active.is_(True),  # noqa: E712
                PeriodicTask.is_deleted.is_(False),  # noqa: E712
            )
            .all()
        )
        return _build_periodic_schedule(tasks)
    except Exception as e:
        logger.error(f"Failed to load periodic tasks from DB: {e}")
        if return_none_on_error:
            return None
        return {}
    finally:
        session.close()


class ReloadingPersistentScheduler(PersistentScheduler):
    """
    Persistent beat scheduler with DB auto-refresh / 支持数据库自动重载的持久化 Beat 调度器

    Keeps the last good DB-driven schedule when startup or refresh hits a
    transient DB outage, and retries on later ticks.
    启动或重载时如果数据库短暂不可用，会保留上一份可用调度，并在后续 tick 中重试。
    """

    db_schedule_reload_interval = 60.0

    def __init__(self, *args, **kwargs):
        self._db_entry_names: set[str] = set()
        self._last_db_schedule_reload_at: float | None = None
        super().__init__(*args, **kwargs)

    def setup_schedule(self) -> None:
        try:
            self._store = self._open_schedule()
            self._store.keys()
        except Exception as exc:  # pylint: disable=broad-except
            self._store = self._destroy_open_corrupted_schedule(exc)

        self._create_schedule()

        tz = self.app.conf.timezone
        stored_tz = self._store.get("tz")
        if stored_tz is not None and stored_tz != tz:
            self._store.clear()
        utc = self.app.conf.enable_utc
        stored_utc = self._store.get("utc_enabled")
        if stored_utc is not None and stored_utc != utc:
            self._store.clear()

        self._store.setdefault("entries", {})
        self.update_from_dict(self.app.conf.beat_schedule or {})
        self.install_default_entries(self.schedule)
        self._store.update(
            {
                "__version__": celery_version,
                "tz": tz,
                "utc_enabled": utc,
            }
        )
        self.sync()

        static_names = set(self.app.conf.beat_schedule or {})
        if "celery.backend_cleanup" in self.schedule:
            static_names.add("celery.backend_cleanup")
        self._db_entry_names = set(self.schedule) - static_names

        self.refresh_db_schedule(force=True)

    def tick(self, *args, **kwargs):
        self.refresh_db_schedule()
        return super().tick(*args, **kwargs)

    def refresh_db_schedule(self, *, force: bool = False) -> None:
        now = time.monotonic()
        if (
            not force
            and self._last_db_schedule_reload_at is not None
            and (now - self._last_db_schedule_reload_at)
            < self.db_schedule_reload_interval
        ):
            return

        self._last_db_schedule_reload_at = now

        db_schedule = load_periodic_tasks_from_db(return_none_on_error=True)
        if db_schedule is None:
            return

        static_schedule = dict(self.app.conf.beat_schedule or {})
        if "celery.backend_cleanup" in self.schedule:
            static_schedule["celery.backend_cleanup"] = self.schedule[
                "celery.backend_cleanup"
            ]

        merged_schedule = {**static_schedule, **db_schedule}
        previous_db_entry_names = set(self._db_entry_names)

        self.merge_inplace(merged_schedule)
        self._db_entry_names = set(db_schedule)
        self.old_schedulers = None
        self._heap = None
        self.sync()

        if force or previous_db_entry_names != self._db_entry_names:
            logger.info(
                "Beat DB schedule refreshed: db_tasks={} total={}",
                len(self._db_entry_names),
                len(self.schedule),
            )


def setup_periodic_tasks() -> None:
    """Register DB periodic tasks to Celery Beat schedule / 将数据库定时任务注册到 Celery Beat 调度"""
    db_schedule = load_periodic_tasks_from_db() or {}

    beat_schedule = (
        {**celery_app.conf.beat_schedule} if celery_app.conf.beat_schedule else {}
    )
    beat_schedule.update(db_schedule)
    celery_app.conf.beat_schedule = beat_schedule

    logger.info(
        f"Periodic tasks loaded: {len(db_schedule)} from DB, {len(beat_schedule)} total"
    )


def refresh_schedule() -> None:
    """Refresh periodic task schedule from DB / 从数据库刷新定时任务调度"""
    setup_periodic_tasks()
    logger.info("Periodic task schedule refreshed from DB")
