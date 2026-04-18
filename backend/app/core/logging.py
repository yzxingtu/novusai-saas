"""
日志管理模块 / Logging Management Module

提供按模块独立的日志文件和统一的日志格式（基于 Loguru 适配器）
Provides per-module independent log files and unified log format (Loguru adapter).

日志分类 / Log categories:
- app: 应用日志（默认）/ Application logs (default)
- error: 错误日志 / Error logs
- db: 数据库日志 / Database logs
- task: 计划任务日志 / Scheduled task logs
- queue: 队列日志 / Queue logs
- captcha / storage / auth / impersonate: 见 LogCategoryEnum

每条日志自动附带 trace_id（来自 TraceIdMiddleware 的 ContextVar）
Each log automatically includes trace_id from TraceIdMiddleware's ContextVar.
"""

import atexit
import contextlib
import logging
import signal
import sys
from pathlib import Path

from loguru import logger

from app.core.config import settings
from app.enums.log import LogCategoryEnum

# 保持活动日志文件名稳定（app.log / task.log 等），并继续按天轮转历史文件。
# 这能兼容系统日志读取、trace 检索与现有测试所依赖的文件名约定。
# Keep active log filenames stable (app.log / task.log / ...) while still
# rotating daily so downstream log readers and tests can rely on the canonical
# current-file names.
_DAILY_ROTATION = "00:00"

# Log levels / 日志级别
LOG_LEVELS = {
    "DEBUG": "DEBUG",
    "INFO": "INFO",
    "WARNING": "WARNING",
    "ERROR": "ERROR",
    "CRITICAL": "CRITICAL",
}

# 分类日志器名称前缀 / Category logger name prefix
_CATEGORY_LOGGER_PREFIX = "novusai."


class InterceptHandler(logging.Handler):
    """
    将标准 logging 重定向到 Loguru / Intercept standard logging to Loguru.

    SQLAlchemy、uvicorn、celery 等第三方库的日志通过此 Handler 进入 Loguru。
    Third-party libs (SQLAlchemy, uvicorn, celery) logs are redirected to Loguru.
    """

    def __init__(self, category: str | None = None) -> None:
        super().__init__()
        self._category = category

    def emit(self, record: logging.LogRecord) -> None:
        try:
            level = logger.level(record.levelname).name
        except ValueError:
            level = record.levelno

        # 使用 stdlib 的 logger 名（如 uvicorn.error、websockets.server），勿用 opt(depth=…)，
        # 否则 Loguru 会把 {name} 解析成 logging/__init__（显示为 logging | callHandlers）。
        # Use stdlib logger name; avoid opt(depth=…) which misattributes {name} to logging module.
        bind_kw: dict[str, str] = {"log_logger": record.name}
        if self._category:
            bind_kw["category"] = self._category
        logger.bind(**bind_kw).opt(exception=record.exc_info).log(
            level, record.getMessage()
        )


def _ignore_sigint_on_shutdown() -> None:
    """
    atexit 中第一个执行：屏蔽后续 Ctrl+C，避免 Loguru 文件 sink 清理被中断。
    First atexit callback: ignore SIGINT during shutdown to prevent Loguru
    file sink cleanup from being interrupted by KeyboardInterrupt.
    """
    with contextlib.suppress(ValueError, OSError):
        signal.signal(signal.SIGINT, signal.SIG_IGN)


def _patch_trace_id(record: dict) -> None:
    """Inject trace_id into log record for request correlation / 注入 trace_id 用于请求关联"""
    try:
        from app.middleware.trace import trace_id_var

        record["extra"]["trace_id"] = trace_id_var.get() or ""
    except ImportError:
        record["extra"]["trace_id"] = ""
    # 与 InterceptHandler 的 log_logger 对齐，格式串统一用 {extra[log_logger]} / Align with InterceptHandler
    record["extra"].setdefault("log_logger", record["name"])


class LogManager:
    """
    日志管理器（Loguru 适配器）/ Log manager (Loguru adapter).

    保持 LogManager 外部接口不变，内部使用 Loguru。
    External interface unchanged; internal implementation uses Loguru.
    """

    _initialized: bool = False
    _log_dir: Path | None = None
    _loggers: dict[str, object] = {}
    _category_loggers: dict[str, object] = {}
    _log_level: str = "INFO"

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
        """
        if cls._initialized:
            return

        cls._log_dir = Path(log_dir or settings.LOG_DIR)
        cls._log_dir.mkdir(parents=True, exist_ok=True)

        cls._log_level = (log_level or settings.LOG_LEVEL).upper()
        if cls._log_level not in LOG_LEVELS:
            cls._log_level = "INFO"

        # 清除 Loguru 默认 handler / Remove default Loguru handler
        logger.remove()

        # 日志格式（含 trace_id）/ Log format with trace_id
        base_fmt = (
            "<green>{time:YYYY-MM-DD HH:mm:ss}</green> | "
            "<level>{level: <8}</level> | "
            "<cyan>{extra[log_logger]}</cyan> | "
            "<cyan>[trace_id={extra[trace_id]}]</cyan> | "
            "{message}"
        )
        file_fmt = (
            "{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {extra[log_logger]} | "
            "[trace_id={extra[trace_id]}] | {message}"
        )

        # 配置 trace_id 注入 / Configure trace_id patcher
        logger.configure(patcher=_patch_trace_id)

        # 控制台输出 / Console sink（始终简洁格式；DEBUG 下也不再带 logging/callHandlers 栈帧）
        # Console always uses compact format; avoids logging/__init__ frame noise when DEBUG=True
        if enable_console:

            def _console_sink_filter(record: dict) -> bool:
                if (
                    not settings.LOG_DB_TO_CONSOLE
                    and record["extra"].get("category") == LogCategoryEnum.DB.value
                ):
                    return False
                if settings.LOG_QUIET_WEBSOCKET_HANDSHAKE:
                    msg = record["message"]
                    lg = record["extra"].get("log_logger") or ""
                    if (
                        lg == "uvicorn.error"
                        and "WebSocket" in msg
                        and "[accepted]" in msg
                    ):
                        return False
                    # uvicorn 把 WebSocketServerProtocol 的 logger 设成 uvicorn.error，websockets 的
                    # "connection open" 因此走 uvicorn.error 而非 websockets.server
                    if msg == "connection open" and lg in (
                        "uvicorn.error",
                        "websockets.server",
                    ):
                        return False
                return True

            logger.add(
                sys.stdout,
                format=base_fmt,
                level=cls._log_level,
                colorize=True,
                filter=_console_sink_filter,
            )

        # 文件输出 / File sinks
        if enable_file:

            def _log_path(category: str) -> Path:
                return cls._log_dir / f"{category}.log"

            # app.log / 主应用日志文件
            logger.add(
                _log_path("app"),
                format=file_fmt,
                level=cls._log_level,
                rotation=_DAILY_ROTATION,
                retention=30,
                filter=lambda r: r["extra"].get("category") in (None, "app", "error"),
            )
            # error.log (ERROR+ only) / 仅 ERROR 及以上
            logger.add(
                _log_path("error"),
                format=file_fmt,
                level="ERROR",
                rotation=_DAILY_ROTATION,
                retention=90,
                filter=lambda r: r["extra"].get("category") in (None, "app", "error"),
            )
            # 分类日志文件 / Category log files
            for cat in [
                LogCategoryEnum.DB,
                LogCategoryEnum.TASK,
                LogCategoryEnum.QUEUE,
                LogCategoryEnum.CAPTCHA,
                LogCategoryEnum.STORAGE,
                LogCategoryEnum.AUTH,
                LogCategoryEnum.IMPERSONATE,
            ]:
                logger.add(
                    _log_path(cat.value),
                    format=file_fmt,
                    level=cls._log_level,
                    rotation=_DAILY_ROTATION,
                    retention=30,
                    filter=lambda r, c=cat.value: r["extra"].get("category") == c,
                )

        # SQLAlchemy 等标准 logging 重定向 / Redirect stdlib logging to Loguru
        logging.basicConfig(handlers=[InterceptHandler()], level=0, force=True)
        for _name in (
            "uvicorn",
            "uvicorn.error",
            "uvicorn.access",
            "httpx",
            "httpcore",
        ):
            _lg = logging.getLogger(_name)
            _lg.handlers = [InterceptHandler()]
            _lg.propagate = False
        logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
        logging.getLogger("httpx").setLevel(logging.WARNING)
        logging.getLogger("httpcore").setLevel(logging.WARNING)
        # python-socketio / engineio 连接过程 INFO 较吵，开发时默认压低 / Quieter Socket.IO handshake logs
        logging.getLogger("engineio").setLevel(logging.WARNING)
        logging.getLogger("socketio").setLevel(logging.WARNING)

        # SQLAlchemy engine 重定向到 db 分类 / SQLAlchemy -> db category
        sa_logger = logging.getLogger("sqlalchemy.engine")
        sa_logger.setLevel(logging.DEBUG if settings.DEBUG else logging.WARNING)
        sa_logger.handlers = [InterceptHandler(category=LogCategoryEnum.DB.value)]
        sa_logger.propagate = False

        # 防止 Ctrl+C 退出时 Loguru 文件 sink 清理被 KeyboardInterrupt 中断
        # Prevent KeyboardInterrupt during Loguru file sink cleanup on Ctrl+C shutdown
        atexit.register(_ignore_sigint_on_shutdown)

        cls._initialized = True

    @classmethod
    def get_logger(
        cls,
        name: str,
        *,
        separate_file: bool = False,
        level: int | None = None,
    ) -> object:
        """
        获取模块日志器 / Get module logger.
        返回 Loguru 的 bound logger，接口兼容 logging.Logger。
        Returns Loguru bound logger; API compatible with logging.Logger.
        """
        if not cls._initialized:
            cls.init()

        _ = level  # Loguru 使用全局 level，此处保留参数兼容
        cache_key = f"{name}:{separate_file}"
        if cache_key in cls._loggers:
            return cls._loggers[cache_key]

        category_values = {cat.value for cat in LogCategoryEnum}
        # Preserve the documented API: known log categories should route to
        # their dedicated files, while arbitrary names remain module loggers.
        # 保持文档约定：已知日志分类写入专属文件，其余名称仍作为模块日志器使用。
        if name in category_values:
            bound = logger.bind(category=name)
        else:
            bound = logger.bind(module=name)
        cls._loggers[cache_key] = bound
        return bound

    @classmethod
    def get_category_logger(cls, category: LogCategoryEnum | str) -> object:
        """
        获取分类日志器 / Get category logger.
        """
        if not cls._initialized:
            cls.init()

        cv = category.value if isinstance(category, LogCategoryEnum) else category

        if cv in (LogCategoryEnum.APP.value, LogCategoryEnum.ERROR.value):
            return logger.bind(category=cv)

        return logger.bind(category=cv)

    @classmethod
    def get_app_logger(cls) -> object:
        """获取应用日志器 / Get app logger."""
        return cls.get_category_logger(LogCategoryEnum.APP)

    @classmethod
    def get_error_logger(cls) -> object:
        """获取错误日志器 / Get error logger."""
        return cls.get_category_logger(LogCategoryEnum.ERROR)

    @classmethod
    def get_db_logger(cls) -> object:
        """获取数据库日志器 / Get db logger."""
        return cls.get_category_logger(LogCategoryEnum.DB)

    @classmethod
    def get_task_logger(cls) -> object:
        """获取计划任务日志器 / Get task logger."""
        return cls.get_category_logger(LogCategoryEnum.TASK)

    @classmethod
    def get_queue_logger(cls) -> object:
        """获取队列日志器 / Get queue logger."""
        return cls.get_category_logger(LogCategoryEnum.QUEUE)

    @classmethod
    def get_captcha_logger(cls) -> object:
        """获取验证码日志器 / Get captcha logger."""
        return cls.get_category_logger(LogCategoryEnum.CAPTCHA)

    @classmethod
    def get_storage_logger(cls) -> object:
        """获取存储日志器 / Get storage logger."""
        return cls.get_category_logger(LogCategoryEnum.STORAGE)

    @classmethod
    def get_auth_logger(cls) -> object:
        """获取认证日志器 / Get auth logger."""
        return cls.get_category_logger(LogCategoryEnum.AUTH)

    @classmethod
    def get_impersonate_logger(cls) -> object:
        """获取一键登录审计日志器 / Get impersonate logger."""
        return cls.get_category_logger(LogCategoryEnum.IMPERSONATE)

    @classmethod
    def get_log_dir(cls) -> Path | None:
        """获取日志目录路径 / Get log directory path."""
        return cls._log_dir

    @classmethod
    def list_log_files(cls) -> list[Path]:
        """列出日志目录中的所有日志文件 / List all log files."""
        if cls._log_dir is None:
            return []
        return sorted(cls._log_dir.glob("*.log*"))


def get_logger(name: str, *, separate_file: bool = False) -> object:
    """获取日志器的便捷函数 / Get logger convenience function."""
    return LogManager.get_logger(name, separate_file=separate_file)


def get_app_logger() -> object:
    """获取应用日志器 / Get application logger."""
    return LogManager.get_app_logger()


def get_db_logger() -> object:
    """获取数据库日志器 / Get database logger."""
    return LogManager.get_db_logger()


def get_task_logger() -> object:
    """获取计划任务日志器 / Get scheduled task logger."""
    return LogManager.get_task_logger()


def get_queue_logger() -> object:
    """获取队列日志器 / Get queue logger."""
    return LogManager.get_queue_logger()


def get_captcha_logger() -> object:
    """获取验证码日志器 / Get captcha logger."""
    return LogManager.get_captcha_logger()


def get_storage_logger() -> object:
    """获取存储日志器 / Get storage logger."""
    return LogManager.get_storage_logger()


def get_auth_logger() -> object:
    """获取认证日志器 / Get auth logger."""
    return LogManager.get_auth_logger()


def get_impersonate_logger() -> object:
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
    提供延迟加载的 logger，返回 loguru.logger.bind(module=...)
    Provides lazy logger returning loguru.logger.bind(module=...)
    """

    _log_category: LogCategoryEnum | None = None
    __class_loggers: dict[type, object] = {}

    @property
    def logger(self) -> object:
        """获取日志器 / Get logger."""
        cls = self.__class__
        if cls not in LoggerMixin.__class_loggers:
            if self._log_category is not None:
                LoggerMixin.__class_loggers[cls] = LogManager.get_category_logger(
                    self._log_category
                )
            else:
                LoggerMixin.__class_loggers[cls] = logger.bind(module=cls.__name__)
        return LoggerMixin.__class_loggers[cls]


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
    "LoggerMixin",
    "CaptchaLoggerMixin",
    "StorageLoggerMixin",
    "AuthLoggerMixin",
    "TaskLoggerMixin",
    "QueueLoggerMixin",
    "DbLoggerMixin",
    "ImpersonateLoggerMixin",
]
