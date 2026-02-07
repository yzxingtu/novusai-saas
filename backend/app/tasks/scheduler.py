"""
数据库驱动的动态调度器

从数据库加载定时任务配置，注册到 Celery Beat 调度
支持运行时动态添加/移除调度
"""

from celery.schedules import crontab
from celery.utils.log import get_logger as celery_get_logger

from app.celery_app import celery_app
from app.core.config import settings
from app.core.database import sync_session_factory
from app.core.logging import LogManager
from app.models.system.periodic_task import PeriodicTask

logger = LogManager.get_logger("queue")


def parse_cron_expression(expression: str) -> crontab:
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


def load_periodic_tasks_from_db() -> dict:
    schedule = {}
    session = sync_session_factory()
    try:
        tasks = (
            session.query(PeriodicTask)
            .filter(
                PeriodicTask.is_active == True,  # noqa: E712
                PeriodicTask.is_deleted == False,  # noqa: E712
            )
            .all()
        )

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
                    f"Skipping periodic task '{task.name}': "
                    f"invalid schedule configuration"
                )
                continue

            schedule[task.name] = entry
            logger.info(
                f"Loaded periodic task: {task.name} -> {task.task_path} "
                f"({task.schedule_type})"
            )

    except Exception as e:
        logger.error(f"Failed to load periodic tasks from DB: {e}")
    finally:
        session.close()

    return schedule


def setup_periodic_tasks() -> None:
    db_schedule = load_periodic_tasks_from_db()

    beat_schedule = {**celery_app.conf.beat_schedule} if celery_app.conf.beat_schedule else {}
    beat_schedule.update(db_schedule)
    celery_app.conf.beat_schedule = beat_schedule

    logger.info(
        f"Periodic tasks loaded: {len(db_schedule)} from DB, "
        f"{len(beat_schedule)} total"
    )


def refresh_schedule() -> None:
    setup_periodic_tasks()
    logger.info("Periodic task schedule refreshed from DB")
