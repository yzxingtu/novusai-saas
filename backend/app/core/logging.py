"""
日志管理模块 / Logging Management Module

提供按模块独立的日志文件和统一的日志格式
Provides per-module independent log files and unified log format.

日志分类 / Log categories:
- app: 应用日志（默认） / Application logs (default)
- error: 错误日志 / Error logs
- db: 数据库日志 / Database logs
- task: 计划任务日志 / Scheduled task logs
- queue: 队列日志 / Queue logs
- captcha / storage / auth / impersonate: 见 LogCategoryEnum

文件命名与轮转 / File naming and rotation:
- 当前文件: {category}.log
- 按大小轮转（RotatingFileHandler，约 10MB 触发），备份命名为 {category}.log.1, .2, ...
- 各分类保留 backupCount 个备份（app 等 30 个，error 90 个）
"""

import contextlib
import logging
import os
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Literal

from app.core.config import settings
from app.enums.log import LogCategoryEnum


class _WindowsSafeRotatingFileHandler(RotatingFileHandler):
    """
    Windows 安全的 RotatingFileHandler / Windows-safe RotatingFileHandler.

    多进程（FastAPI + Celery Worker）同时写同一日志文件时，
    标准 RotatingFileHandler.doRollover() 使用 os.rename()，
    在 Windows 上会因文件被占用抛出 PermissionError (WinError 32)。

    修复策略：捕获 PermissionError，跳过本次轮转继续写入当前文件。
    下次达到 maxBytes 时再尝试轮转。
    """

    def doRollover(self) -> None:
        if os.name != "nt":
            return super().doRollover()

        with contextlib.suppress(PermissionError):
            super().doRollover()

# 日志格式
DEFAULT_FORMAT = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
DETAILED_FORMAT = (
    "%(asctime)s | %(levelname)-8s | %(name)s | "
    "%(filename)s:%(lineno)d | %(funcName)s | %(message)s"
)
JSON_FORMAT = (
    '{"time": "%(asctime)s", "level": "%(levelname)s", "logger": "%(name)s", '
    '"file": "%(filename)s", "line": %(lineno)d, "message": "%(message)s"}'
)

# 日志级别映射
LOG_LEVELS = {
    "DEBUG": logging.DEBUG,
    "INFO": logging.INFO,
    "WARNING": logging.WARNING,
    "ERROR": logging.ERROR,
    "CRITICAL": logging.CRITICAL,
}

# 分类日志器名称前缀
_CATEGORY_LOGGER_PREFIX = "novusai."


class LogManager:
    """
    日志管理器 / Log manager.

    提供按模块独立的日志配置，支持分类日志和日期轮转
    """

    _initialized: bool = False
    _log_dir: Path | None = None
    _loggers: dict[str, logging.Logger] = {}
    _category_loggers: dict[str, logging.Logger] = {}
    _log_level: int = logging.INFO

    @classmethod
    def init(
        cls,
        log_dir: str | None = None,
        log_level: str | None = None,
        enable_console: bool = True,
        enable_file: bool = True,
    ) -> None:
        """
        初始化日志系统 / Initialize logging system.

        Args:
            log_dir: 日志目录
            log_level: 日志级别
            enable_console: 是否启用控制台输出
            enable_file: 是否启用文件输出
        """
        if cls._initialized:
            return

        # 设置日志目录
        cls._log_dir = Path(log_dir or settings.LOG_DIR)
        cls._log_dir.mkdir(parents=True, exist_ok=True)

        # 获取日志级别
        cls._log_level = LOG_LEVELS.get(
            (log_level or settings.LOG_LEVEL).upper(),
            logging.INFO
        )

        # 配置根日志器
        root_logger = logging.getLogger()
        root_logger.setLevel(cls._log_level)

        # 清除已有处理器
        root_logger.handlers.clear()

        # 添加控制台处理器
        if enable_console:
            console_handler = cls._create_console_handler(cls._log_level)
            root_logger.addHandler(console_handler)

        # 添加文件处理器
        if enable_file:
            # 主日志文件（app.log）- 按日期轮转
            app_handler = cls._create_timed_handler(
                LogCategoryEnum.APP.value,
                cls._log_level,
                backup_count=30,
            )
            root_logger.addHandler(app_handler)

            # 错误日志单独文件（error.log）- 按日期轮转
            error_handler = cls._create_timed_handler(
                LogCategoryEnum.ERROR.value,
                logging.ERROR,
                backup_count=90,  # 错误日志保留更久
            )
            root_logger.addHandler(error_handler)

            # 初始化分类日志器（db/task/queue）
            cls._init_category_loggers()

        # 调整第三方库日志级别
        logging.getLogger("uvicorn").setLevel(logging.INFO)
        logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
        logging.getLogger("httpx").setLevel(logging.WARNING)
        logging.getLogger("httpcore").setLevel(logging.WARNING)

        # SQLAlchemy 日志重定向到 db 分类
        cls._setup_sqlalchemy_logging()

        cls._initialized = True

    @classmethod
    def _init_category_loggers(cls) -> None:
        """
        初始化分类日志器 / Initialize category loggers.

        为需要独立文件的分类创建日志器和文件处理器
        """
        # 需要独立文件的分类（app/error 已经通过根日志器处理）
        categories = [
            LogCategoryEnum.DB,
            LogCategoryEnum.TASK,
            LogCategoryEnum.QUEUE,
            LogCategoryEnum.CAPTCHA,
            LogCategoryEnum.STORAGE,
            LogCategoryEnum.AUTH,
            LogCategoryEnum.IMPERSONATE,
        ]

        for category in categories:
            logger_name = f"{_CATEGORY_LOGGER_PREFIX}{category.value}"
            logger = logging.getLogger(logger_name)
            logger.setLevel(cls._log_level)
            logger.disabled = False  # 确保 logger 未被禁用
            logger.propagate = False  # 不向上传播，避免重复记录

            # 添加文件处理器
            handler = cls._create_timed_handler(
                category.value,
                cls._log_level,
                backup_count=30,
            )
            logger.addHandler(handler)

            # 控制台输出（开发环境）
            if settings.DEBUG:
                console_handler = cls._create_console_handler(cls._log_level)
                logger.addHandler(console_handler)

            cls._category_loggers[category.value] = logger

    @classmethod
    def _setup_sqlalchemy_logging(cls) -> None:
        """
        配置 SQLAlchemy 日志 / Configure SQLAlchemy logging.

        将 SQLAlchemy 日志重定向到 db 分类日志器（仅文件，不输出到控制台）
        """
        # 获取 db 日志器
        db_logger = cls._category_loggers.get(LogCategoryEnum.DB.value)
        if db_logger is None:
            return

        # 配置 SQLAlchemy engine 日志
        sa_logger = logging.getLogger("sqlalchemy.engine")
        sa_level = logging.DEBUG if settings.DEBUG else logging.WARNING
        sa_logger.setLevel(sa_level)
        sa_logger.propagate = False  # 不向根日志器传播

        # 清除已有处理器，复用 db 分类日志器的文件处理器（避免重复打开同一文件）
        # Windows 上两个 RotatingFileHandler 指向同一文件会导致轮转时 PermissionError
        sa_logger.handlers.clear()
        for h in db_logger.handlers:
            if isinstance(h, RotatingFileHandler):
                sa_logger.addHandler(h)
                break

    @classmethod
    def _create_console_handler(cls, level: int) -> logging.StreamHandler:
        """创建控制台处理器 / Create console handler."""
        handler = logging.StreamHandler(sys.stdout)
        handler.setLevel(level)

        # 开发环境使用详细格式
        fmt = DETAILED_FORMAT if settings.DEBUG else DEFAULT_FORMAT
        formatter = logging.Formatter(fmt, datefmt="%Y-%m-%d %H:%M:%S")
        handler.setFormatter(formatter)

        return handler

    @classmethod
    def _create_file_handler(
        cls,
        name: str,
        level: int,
        max_bytes: int = 10 * 1024 * 1024,  # 10MB
        backup_count: int = 5,
    ) -> RotatingFileHandler:
        """
        创建文件处理器（按大小轮转） / Create file handler (size-based rotation).

        Args:
            name: 日志文件名（不含扩展名） / Log file name (no extension).
            level: 日志级别 / Log level.
            max_bytes: 单个文件最大字节数 / Max bytes per file.
            backup_count: 保留备份文件数 / Number of backup files.
        """
        if cls._log_dir is None:
            raise RuntimeError("LogManager not initialized")

        log_file = cls._log_dir / f"{name}.log"
        handler = _WindowsSafeRotatingFileHandler(
            log_file,
            maxBytes=max_bytes,
            backupCount=backup_count,
            encoding="utf-8",
        )
        handler.setLevel(level)

        formatter = logging.Formatter(DETAILED_FORMAT, datefmt="%Y-%m-%d %H:%M:%S")
        handler.setFormatter(formatter)

        return handler

    @classmethod
    def _create_timed_handler(
        cls,
        name: str,
        level: int,
        when: Literal["midnight", "D", "H", "M"] = "midnight",
        backup_count: int = 30,
    ) -> _WindowsSafeRotatingFileHandler:
        """
        创建文件处理器（按大小轮转，避免 Windows 文件占用问题）/ Create timed file handler (size-based, Windows-safe).

        Windows 不允许重命名被占用的文件，TimedRotatingFileHandler 会失败。
        使用 _WindowsSafeRotatingFileHandler 按大小轮转，轮转失败时静默跳过。

        Args:
            name: 日志文件名
            level: 日志级别
            when: 轮转时机（忽略，保留参数兼容性）
            backup_count: 保留备份数
        """
        _ = when
        if cls._log_dir is None:
            raise RuntimeError("LogManager not initialized")

        log_file = cls._log_dir / f"{name}.log"
        handler = _WindowsSafeRotatingFileHandler(
            log_file,
            maxBytes=10 * 1024 * 1024,  # 10MB
            backupCount=backup_count,
            encoding="utf-8",
        )
        handler.setLevel(level)

        formatter = logging.Formatter(DETAILED_FORMAT, datefmt="%Y-%m-%d %H:%M:%S")
        handler.setFormatter(formatter)

        return handler

    @classmethod
    def get_logger(
        cls,
        name: str,
        *,
        separate_file: bool = False,
        level: int | None = None,
    ) -> logging.Logger:
        """
        获取模块日志器 / Get module logger.

        Args:
            name: 日志器名称（通常为模块名）
            separate_file: 是否使用独立日志文件
            level: 日志级别（可选）

        Returns:
            配置好的日志器

        Example:
            logger = LogManager.get_logger(__name__)
            logger.info("Hello")

            # 独立日志文件
            audit_logger = LogManager.get_logger("audit", separate_file=True)
        """
        # 确保已初始化
        if not cls._initialized:
            cls.init()

        # 检查缓存
        cache_key = f"{name}:{separate_file}"
        if cache_key in cls._loggers:
            return cls._loggers[cache_key]

        logger = logging.getLogger(name)

        # 设置级别：优先使用指定级别，否则使用全局配置级别
        effective_level = level if level is not None else cls._log_level
        logger.setLevel(effective_level)

        # 添加独立文件处理器
        if separate_file and cls._log_dir:
            # 使用简化的文件名
            file_name = name.split(".")[-1]
            # 使用相同的有效级别
            handler = cls._create_timed_handler(file_name, effective_level)
            logger.addHandler(handler)

            # 独立文件 logger 也输出到控制台（开发环境）
            if settings.DEBUG:
                console_handler = cls._create_console_handler(effective_level)
                logger.addHandler(console_handler)

            # 不向上传播，避免重复记录到 app.log
            logger.propagate = False

        cls._loggers[cache_key] = logger
        return logger

    @classmethod
    def get_category_logger(cls, category: LogCategoryEnum | str) -> logging.Logger:
        """
        获取分类日志器 / Get category logger.

        Args:
            category: 日志分类（LogCategoryEnum 或字符串）

        Returns:
            分类日志器

        Example:
            db_logger = LogManager.get_category_logger(LogCategoryEnum.DB)
            db_logger.info("Executing query...")
        """
        if not cls._initialized:
            cls.init()

        category_value = category.value if isinstance(category, LogCategoryEnum) else category

        # app/error 使用根日志器
        if category_value in (LogCategoryEnum.APP.value, LogCategoryEnum.ERROR.value):
            return logging.getLogger()

        # 其他分类使用独立日志器
        logger = cls._category_loggers.get(category_value)
        if logger is None:
            # 回退到根日志器
            return logging.getLogger()
        return logger

    @classmethod
    def get_app_logger(cls) -> logging.Logger:
        """
        获取应用日志器 / Get app logger.

        记录到 logs/app.log
        """
        return cls.get_category_logger(LogCategoryEnum.APP)

    @classmethod
    def get_error_logger(cls) -> logging.Logger:
        """
        获取错误日志器 / Get error logger.

        记录到 logs/error.log（仅 ERROR 级别以上）
        """
        return cls.get_category_logger(LogCategoryEnum.ERROR)

    @classmethod
    def get_db_logger(cls) -> logging.Logger:
        """
        获取数据库日志器 / Get db logger.

        记录到 logs/db.log
        """
        return cls.get_category_logger(LogCategoryEnum.DB)

    @classmethod
    def get_task_logger(cls) -> logging.Logger:
        """
        获取计划任务日志器 / Get task logger.

        记录到 logs/task.log
        """
        return cls.get_category_logger(LogCategoryEnum.TASK)

    @classmethod
    def get_queue_logger(cls) -> logging.Logger:
        """
        获取队列日志器 / Get queue logger.

        记录到 logs/queue.log
        """
        return cls.get_category_logger(LogCategoryEnum.QUEUE)

    @classmethod
    def get_captcha_logger(cls) -> logging.Logger:
        """
        获取验证码日志器 / Get captcha logger.

        记录到 logs/captcha.log
        """
        return cls.get_category_logger(LogCategoryEnum.CAPTCHA)

    @classmethod
    def get_storage_logger(cls) -> logging.Logger:
        """
        获取存储日志器 / Get storage logger.

        记录到 logs/storage.log
        """
        return cls.get_category_logger(LogCategoryEnum.STORAGE)

    @classmethod
    def get_auth_logger(cls) -> logging.Logger:
        """
        获取认证日志器 / Get auth logger.

        记录到 logs/auth.log
        """
        return cls.get_category_logger(LogCategoryEnum.AUTH)

    @classmethod
    def get_impersonate_logger(cls) -> logging.Logger:
        """
        获取一键登录审计日志器 / Get impersonate audit logger.

        记录到 logs/impersonate.log
        """
        return cls.get_category_logger(LogCategoryEnum.IMPERSONATE)

    @classmethod
    def get_log_dir(cls) -> Path | None:
        """获取日志目录路径 / Get log directory path."""
        return cls._log_dir

    @classmethod
    def list_log_files(cls) -> list[Path]:
        """
        列出日志目录中的所有日志文件 / List all log files in log directory.

        Returns:
            日志文件路径列表 / List of log file paths.
        """
        if cls._log_dir is None:
            return []
        return sorted(cls._log_dir.glob("*.log*"))


def get_logger(name: str, *, separate_file: bool = False) -> logging.Logger:
    """
    获取日志器的便捷函数 / Get logger convenience function.

    Args:
        name: 日志器名称 / Logger name.
        separate_file: 是否使用独立日志文件 / Whether to use separate log file.

    Returns:
        logging.Logger

    Example:
        from app.core.logging import get_logger

        logger = get_logger(__name__)
        logger.info("Processing request")
    """
    return LogManager.get_logger(name, separate_file=separate_file)


def get_app_logger() -> logging.Logger:
    """获取应用日志器 / Get application logger."""
    return LogManager.get_app_logger()


def get_db_logger() -> logging.Logger:
    """获取数据库日志器 / Get database logger."""
    return LogManager.get_db_logger()


def get_task_logger() -> logging.Logger:
    """获取计划任务日志器 / Get scheduled task logger."""
    return LogManager.get_task_logger()


def get_queue_logger() -> logging.Logger:
    """获取队列日志器 / Get queue logger."""
    return LogManager.get_queue_logger()


def get_captcha_logger() -> logging.Logger:
    """获取验证码日志器 / Get captcha logger."""
    return LogManager.get_captcha_logger()


def get_storage_logger() -> logging.Logger:
    """获取存储日志器 / Get storage logger."""
    return LogManager.get_storage_logger()


def get_auth_logger() -> logging.Logger:
    """获取认证日志器 / Get auth logger."""
    return LogManager.get_auth_logger()


def get_impersonate_logger() -> logging.Logger:
    """获取一键登录审计日志器 / Get impersonate audit logger."""
    return LogManager.get_impersonate_logger()


def init_logging() -> None:
    """初始化日志系统 / Initialize logging system."""
    LogManager.init()


# ============================================
# LoggerMixin - 日志器混入类
# ============================================

class LoggerMixin:
    """
    日志器混入类 / Logger mixin.

    提供延迟加载的 logger 属性，避免模块导入时 LogManager 未初始化的问题。
    Provides lazy logger property to avoid LogManager not initialized at import.

    使用方式 1 - 默认使用 app 日志 / Usage 1 - default app logger:
        class MyService(LoggerMixin):
            def do_something(self):
                self.logger.info("Doing something")

    使用方式 2 - 指定日志分类 / Usage 2 - specify category:
        class CaptchaProvider(LoggerMixin):
            _log_category = LogCategoryEnum.CAPTCHA

    使用方式 3 - 多重继承 / Usage 3 - multiple inheritance:
        class AttachmentService(BaseService, LoggerMixin):
            _log_category = LogCategoryEnum.STORAGE
    """

    # 子类可覆盖此属性指定日志分类
    _log_category: LogCategoryEnum | None = None

    # 类级别日志器缓存
    __class_loggers: dict[type, logging.Logger] = {}

    @property
    def logger(self) -> logging.Logger:
        """
        获取日志器（延迟加载，类级别缓存） / Get logger (lazy, class-level cache).
        """
        cls = self.__class__
        if cls not in LoggerMixin.__class_loggers:
            if self._log_category is not None:
                LoggerMixin.__class_loggers[cls] = LogManager.get_category_logger(
                    self._log_category
                )
            else:
                # 默认使用 app 日志器
                LoggerMixin.__class_loggers[cls] = LogManager.get_app_logger()

        logger = LoggerMixin.__class_loggers[cls]
        # 确保 logger 未被禁用（uvicorn --reload 可能会禁用 logger）
        if logger.disabled:
            logger.disabled = False
        return logger


class CaptchaLoggerMixin(LoggerMixin):
    """验证码模块日志器混入类 / Captcha logger mixin."""
    _log_category = LogCategoryEnum.CAPTCHA


class StorageLoggerMixin(LoggerMixin):
    """存储模块日志器混入类 / Storage logger mixin."""
    _log_category = LogCategoryEnum.STORAGE


class AuthLoggerMixin(LoggerMixin):
    """认证模块日志器混入类 / Auth logger mixin."""
    _log_category = LogCategoryEnum.AUTH


class TaskLoggerMixin(LoggerMixin):
    """任务模块日志器混入类 / Task logger mixin."""
    _log_category = LogCategoryEnum.TASK


class QueueLoggerMixin(LoggerMixin):
    """队列模块日志器混入类 / Queue logger mixin."""
    _log_category = LogCategoryEnum.QUEUE


class DbLoggerMixin(LoggerMixin):
    """数据库模块日志器混入类 / DB logger mixin."""
    _log_category = LogCategoryEnum.DB


class ImpersonateLoggerMixin(LoggerMixin):
    """一键登录审计日志器混入类 / Impersonate audit logger mixin."""
    _log_category = LogCategoryEnum.IMPERSONATE


__all__ = [
    "LogManager",
    "get_logger",
    "get_app_logger",
    "get_db_logger",
    "get_task_logger",
    "get_queue_logger",
    "get_captcha_logger",
    "get_storage_logger",
    "get_auth_logger",
    "get_impersonate_logger",
    "init_logging",
    # Mixin 类
    "LoggerMixin",
    "CaptchaLoggerMixin",
    "StorageLoggerMixin",
    "AuthLoggerMixin",
    "TaskLoggerMixin",
    "QueueLoggerMixin",
    "DbLoggerMixin",
    "ImpersonateLoggerMixin",
]
