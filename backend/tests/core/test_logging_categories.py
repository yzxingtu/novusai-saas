from __future__ import annotations

import logging
import shutil
import tempfile
from pathlib import Path

from loguru import logger as loguru_logger

from app.core.logging import LogManager


def _reset_log_manager() -> None:
    LogManager._initialized = False
    LogManager._log_dir = None
    LogManager._loggers = {}
    LogManager._category_loggers = {}
    loguru_logger.remove()


def test_task_and_queue_loggers_write_to_dedicated_files() -> None:
    _reset_log_manager()
    temp_dir = Path(tempfile.mkdtemp(prefix="novusai-log-test-"))
    try:
        LogManager.init(log_dir=str(temp_dir), enable_console=False, enable_file=True)

        task_logger = LogManager.get_logger("task")
        queue_logger = LogManager.get_logger("queue")

        task_logger.info("task-category-message")
        queue_logger.info("queue-category-message")

        task_log = (temp_dir / "task.log").read_text(encoding="utf-8")
        queue_log = (temp_dir / "queue.log").read_text(encoding="utf-8")
        app_log = (temp_dir / "app.log").read_text(encoding="utf-8")

        assert "task-category-message" in task_log
        assert "queue-category-message" in queue_log
        assert "task-category-message" not in app_log
        assert "queue-category-message" not in app_log
    finally:
        _reset_log_manager()
        shutil.rmtree(temp_dir, ignore_errors=True)


def test_cli_env_can_disable_file_logging_by_default(
    monkeypatch,
) -> None:
    _reset_log_manager()
    monkeypatch.setenv("NOVUSAI_CLI_DISABLE_FILE_LOGGING", "1")
    temp_dir = Path(tempfile.mkdtemp(prefix="novusai-log-test-"))
    try:
        LogManager.init(log_dir=str(temp_dir), enable_console=False)

        cli_logger = LogManager.get_logger("cli")
        cli_logger.info("cli-message")

        assert list(temp_dir.glob("*.log")) == []
    finally:
        monkeypatch.delenv("NOVUSAI_CLI_DISABLE_FILE_LOGGING", raising=False)
        _reset_log_manager()
        shutil.rmtree(temp_dir, ignore_errors=True)


def test_intercept_handler_preserves_third_party_logging_extra() -> None:
    _reset_log_manager()
    temp_dir = Path(tempfile.mkdtemp(prefix="novusai-log-test-"))
    try:
        LogManager.init(log_dir=str(temp_dir), enable_console=False, enable_file=True)

        logging.getLogger("socketio.server").warning(
            "Cannot receive from redis... retrying in 1 secs",
            extra={"redis_exception": "Timeout reading from redis.example:6379"},
        )

        app_log = (temp_dir / "app.log").read_text(encoding="utf-8")
        assert "Cannot receive from redis... retrying in 1 secs" in app_log
        assert "redis_exception='Timeout reading from redis.example:6379'" in app_log
    finally:
        _reset_log_manager()
        shutil.rmtree(temp_dir, ignore_errors=True)
