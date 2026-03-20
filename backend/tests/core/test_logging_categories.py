from __future__ import annotations

from pathlib import Path

from loguru import logger as loguru_logger

from app.core.logging import LogManager


def _reset_log_manager() -> None:
    LogManager._initialized = False
    LogManager._log_dir = None
    LogManager._loggers = {}
    LogManager._category_loggers = {}
    loguru_logger.remove()


def test_task_and_queue_loggers_write_to_dedicated_files(tmp_path: Path) -> None:
    _reset_log_manager()
    try:
        LogManager.init(log_dir=str(tmp_path), enable_console=False, enable_file=True)

        task_logger = LogManager.get_logger("task")
        queue_logger = LogManager.get_logger("queue")

        task_logger.info("task-category-message")
        queue_logger.info("queue-category-message")

        task_log = (tmp_path / "task.log").read_text(encoding="utf-8")
        queue_log = (tmp_path / "queue.log").read_text(encoding="utf-8")
        app_log = (tmp_path / "app.log").read_text(encoding="utf-8")

        assert "task-category-message" in task_log
        assert "queue-category-message" in queue_log
        assert "task-category-message" not in app_log
        assert "queue-category-message" not in app_log
    finally:
        _reset_log_manager()
