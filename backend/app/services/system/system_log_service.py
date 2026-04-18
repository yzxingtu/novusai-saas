"""
系统日志服务模块 / System Log Service

提供文件日志的查询、读取、下载等功能
Provides file log query, read, download functions.
"""

import os
import re
from datetime import date, datetime
from pathlib import Path
from typing import Literal, NamedTuple

from app.core.config import settings
from app.core.logging import LogManager
from app.enums.log import LogCategoryEnum

LogSearchScope = Literal["current_file", "category"]

LOG_SCOPE_CURRENT_FILE: LogSearchScope = "current_file"
LOG_SCOPE_CATEGORY: LogSearchScope = "category"

_LOG_HEADER_PATTERN = re.compile(
    r"^(?P<timestamp>\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2})\s+\|\s+(?P<level>[^|]+?)\s+\|"
)


class ParsedLogFilename(NamedTuple):
    """解析后的日志文件名信息 / Parsed log filename metadata."""

    category: str
    file_date: date | None
    has_rotation_suffix: bool
    is_legacy_current: bool


class LogFileInfo(NamedTuple):
    """日志文件信息 / Log file info."""

    name: str
    category: str
    size: int
    modified_at: datetime
    is_current: bool  # 是否为当前活动日志文件 / policy guard


class LogCategoryInfo(NamedTuple):
    """日志分类信息 / Log category info."""

    code: str
    name: str
    description: str
    file_count: int
    total_size: int


class LogContentLineItem(NamedTuple):
    """日志行项 / Log content line item."""

    file_name: str
    line_number: int
    content: str


class LogContentPage(NamedTuple):
    """日志内容分页结果 / Log content paged result."""

    filename: str
    category: str
    scope: LogSearchScope
    lines: list[str]
    items: list[LogContentLineItem]
    total_lines: int
    total_entries: int
    searched_files: int
    page: int
    page_size: int
    has_more: bool


class LogEntry(NamedTuple):
    """日志块 / Parsed log entry."""

    file_name: str
    start_line: int
    lines: list[str]
    timestamp: datetime | None
    level: str | None


class SystemLogService:
    """
    系统日志服务 / System log service.

    提供文件日志的管理功能，包括：/ Provides file log management:
    - 日志分类列表 / Log category list
    - 日志文件列表 / Log file list
    - 日志内容读取（分页）/ Log content read (paged)
    - 日志文件下载路径 / Log file download path
    - 日志文件删除 / Log file delete
    """

    # 日志分类描述映射 / Log category description mapping
    _CATEGORY_DESCRIPTIONS = {
        LogCategoryEnum.APP.value: "应用运行日志，记录系统运行状态",
        LogCategoryEnum.ERROR.value: "错误日志，记录系统错误和异常",
        LogCategoryEnum.DB.value: "数据库日志，记录 SQL 查询和数据库操作",
        LogCategoryEnum.TASK.value: "原始任务日志，记录 Celery 任务执行过程中的原始文件日志",
        LogCategoryEnum.QUEUE.value: "原始队列日志，记录 Celery 队列、Worker 与调度器的原始文件日志",
        LogCategoryEnum.CAPTCHA.value: "验证码日志，记录验证码生成和校验",
        LogCategoryEnum.STORAGE.value: "存储日志，记录文件上传下载操作",
        LogCategoryEnum.AUTH.value: "认证日志，记录登录、登出和 Token 操作",
        LogCategoryEnum.IMPERSONATE.value: "一键登录审计日志，记录模拟登录操作",
    }

    # 日志分类显示名称 / Log category display names
    _CATEGORY_NAMES = {
        LogCategoryEnum.APP.value: "应用日志",
        LogCategoryEnum.ERROR.value: "错误日志",
        LogCategoryEnum.DB.value: "数据库日志",
        LogCategoryEnum.TASK.value: "原始任务日志",
        LogCategoryEnum.QUEUE.value: "原始队列日志",
        LogCategoryEnum.CAPTCHA.value: "验证码日志",
        LogCategoryEnum.STORAGE.value: "存储日志",
        LogCategoryEnum.AUTH.value: "认证日志",
        LogCategoryEnum.IMPERSONATE.value: "一键登录审计",
    }

    def __init__(self) -> None:
        """初始化服务 / Initialize service."""
        # 确保 LogManager 已初始化
        if not LogManager._initialized:
            LogManager.init()

        self._log_dir = LogManager.get_log_dir()
        if self._log_dir is None:
            self._log_dir = Path(settings.LOG_DIR)

    def _validate_path(self, file_path: Path) -> bool:
        """
        验证文件路径安全性 / Validate path safety (prevent path traversal).

        防止路径穿越攻击，确保文件在日志目录内。

        Args:
            file_path: 待验证的文件路径 / Path to validate.

        Returns:
            路径是否安全 / Whether path is safe.
        """
        if self._log_dir is None:
            return False

        try:
            resolved_path = file_path.resolve()
            resolved_log_dir = self._log_dir.resolve()
            return str(resolved_path).startswith(str(resolved_log_dir))
        except (OSError, ValueError):
            return False

    def _parse_log_filename(self, filename: str) -> ParsedLogFilename | None:
        """
        解析日志文件名，提取分类与日期信息 / Parse log filename metadata.

        兼容以下格式：
        - {category}.log
        - {category}.log.{n}
        - {category}.log.YYYY-MM-DD
        - {category}.YYYY-MM-DD.log
        - {category}.YYYY-MM-DD.log.{n}
        """
        match = re.match(r"^([a-z_]+)\.log$", filename)
        if match:
            return ParsedLogFilename(
                category=match.group(1),
                file_date=None,
                has_rotation_suffix=False,
                is_legacy_current=True,
            )

        match = re.match(r"^([a-z_]+)\.log\.(\d+)$", filename)
        if match:
            return ParsedLogFilename(
                category=match.group(1),
                file_date=None,
                has_rotation_suffix=True,
                is_legacy_current=False,
            )

        match = re.match(r"^([a-z_]+)\.log\.(\d{4}-\d{2}-\d{2})$", filename)
        if match:
            return ParsedLogFilename(
                category=match.group(1),
                file_date=date.fromisoformat(match.group(2)),
                has_rotation_suffix=True,
                is_legacy_current=False,
            )

        match = re.match(r"^([a-z_]+)\.(\d{4}-\d{2}-\d{2})\.log$", filename)
        if match:
            return ParsedLogFilename(
                category=match.group(1),
                file_date=date.fromisoformat(match.group(2)),
                has_rotation_suffix=False,
                is_legacy_current=False,
            )

        match = re.match(r"^([a-z_]+)\.(\d{4}-\d{2}-\d{2})\.log\.(\d+)$", filename)
        if match:
            return ParsedLogFilename(
                category=match.group(1),
                file_date=date.fromisoformat(match.group(2)),
                has_rotation_suffix=True,
                is_legacy_current=False,
            )

        return None

    def _get_log_glob_patterns(self, category: str) -> list[str]:
        """获取分类日志文件 glob 模式 / Get glob patterns for one category."""
        return [
            f"{category}.log*",
            f"{category}.*.log",
            f"{category}.*.log.*",
        ]

    def _collect_category_log_paths(self, category: str) -> list[Path]:
        """收集某一分类下的日志文件 / Collect log paths for one category."""
        if self._log_dir is None:
            return []

        collected: dict[str, Path] = {}
        for pattern in self._get_log_glob_patterns(category):
            for file_path in self._log_dir.glob(pattern):
                if not file_path.is_file():
                    continue
                parsed = self._parse_log_filename(file_path.name)
                if parsed is None or parsed.category != category:
                    continue
                try:
                    resolved = str(file_path.resolve())
                except OSError:
                    resolved = str(file_path)
                collected[resolved] = file_path
        return list(collected.values())

    def _get_current_daily_log_name(
        self,
        category: str,
        *,
        today: date | None = None,
    ) -> str:
        """获取当前按日拆分的日志文件名 / Get current daily log filename."""
        current_day = today or datetime.now().date()
        return f"{category}.{current_day.isoformat()}.log"

    def _is_current_log_file(self, filename: str, parsed: ParsedLogFilename) -> bool:
        """判断文件是否为当前活动日志文件 / Check whether file is active."""
        if self._log_dir is None or parsed.has_rotation_suffix:
            return False

        today = datetime.now().date()
        current_daily_name = self._get_current_daily_log_name(
            parsed.category, today=today
        )
        current_daily_exists = (self._log_dir / current_daily_name).exists()

        if filename == current_daily_name and parsed.file_date == today:
            return True

        return parsed.is_legacy_current and not current_daily_exists

    def _parse_log_header(self, line: str) -> tuple[datetime | None, str | None]:
        """解析日志头 / Parse log line header."""
        match = _LOG_HEADER_PATTERN.match(line)
        if match is None:
            return None, None

        timestamp = match.group("timestamp")
        level = match.group("level").strip().upper()

        try:
            return datetime.strptime(timestamp, "%Y-%m-%d %H:%M:%S"), level
        except ValueError:
            return None, None

    def _read_entries_from_file(self, file_path: Path) -> list[LogEntry]:
        """按日志块读取文件 / Read file into grouped log entries."""
        entries: list[LogEntry] = []
        current_lines: list[str] = []
        current_timestamp: datetime | None = None
        current_level: str | None = None
        current_start_line = 1

        with open(file_path, encoding="utf-8", errors="replace") as file_obj:
            for line_number, raw_line in enumerate(file_obj, start=1):
                line = raw_line.rstrip("\n\r")
                timestamp, level = self._parse_log_header(line)

                if timestamp is not None:
                    if current_lines:
                        entries.append(
                            LogEntry(
                                file_name=file_path.name,
                                start_line=current_start_line,
                                lines=current_lines,
                                timestamp=current_timestamp,
                                level=current_level,
                            )
                        )
                    current_lines = [line]
                    current_timestamp = timestamp
                    current_level = level
                    current_start_line = line_number
                    continue

                if not current_lines:
                    current_start_line = line_number
                current_lines.append(line)

        if current_lines:
            entries.append(
                LogEntry(
                    file_name=file_path.name,
                    start_line=current_start_line,
                    lines=current_lines,
                    timestamp=current_timestamp,
                    level=current_level,
                )
            )

        return entries

    def _entry_matches(
        self,
        entry: LogEntry,
        *,
        keyword: str | None,
        start_date: date | None,
        end_date: date | None,
    ) -> bool:
        """判断日志块是否匹配筛选条件 / Check whether one log entry matches."""
        normalized_keyword = (keyword or "").strip().lower()
        if normalized_keyword and not any(
            normalized_keyword in line.lower() for line in entry.lines
        ):
            return False

        if start_date is None and end_date is None:
            return True

        if entry.timestamp is None:
            return False

        entry_date = entry.timestamp.date()
        if start_date is not None and entry_date < start_date:
            return False
        return end_date is None or entry_date <= end_date

    def _sort_paths_by_mtime(self, paths: list[Path], *, reverse: bool) -> list[Path]:
        """按修改时间排序文件路径 / Sort paths by modification time."""
        return sorted(
            paths,
            key=lambda path: (path.stat().st_mtime, path.name),
            reverse=reverse,
        )

    def list_categories(self) -> list[LogCategoryInfo]:
        """
        获取日志分类列表 / Get log category list.

        Returns:
            日志分类信息列表 / List of log category info.
        """
        categories = []

        for category in LogCategoryEnum:
            category_value = category.value
            files = self.list_log_files(category=category_value)

            categories.append(
                LogCategoryInfo(
                    code=category_value,
                    name=self._CATEGORY_NAMES.get(category_value, category_value),
                    description=self._CATEGORY_DESCRIPTIONS.get(category_value, ""),
                    file_count=len(files),
                    total_size=sum(file.size for file in files),
                )
            )

        return categories

    def list_log_files(
        self,
        category: str | None = None,
    ) -> list[LogFileInfo]:
        """
        获取日志文件列表 / Get log file list.

        Args:
            category: 日志分类（可选，为空时返回所有分类）

        Returns:
            日志文件信息列表，按修改时间倒序
        """
        if self._log_dir is None:
            return []

        target_categories = (
            [category] if category else [cat.value for cat in LogCategoryEnum]
        )
        files: list[LogFileInfo] = []

        for category_value in target_categories:
            for file_path in self._collect_category_log_paths(category_value):
                parsed = self._parse_log_filename(file_path.name)
                if parsed is None:
                    continue

                stat = file_path.stat()
                files.append(
                    LogFileInfo(
                        name=file_path.name,
                        category=parsed.category,
                        size=stat.st_size,
                        modified_at=datetime.fromtimestamp(stat.st_mtime),
                        is_current=self._is_current_log_file(file_path.name, parsed),
                    )
                )

        files.sort(key=lambda item: item.modified_at, reverse=True)
        return files

    def read_log_file(
        self,
        filename: str,
        page: int = 1,
        page_size: int = 100,
        reverse: bool = True,
        keyword: str | None = None,
        start_date: date | None = None,
        end_date: date | None = None,
        scope: LogSearchScope = LOG_SCOPE_CURRENT_FILE,
    ) -> LogContentPage | None:
        """
        分页读取日志文件内容 / Read log file content (paginated).

        按日志块分页，便于日期范围和关键词检索时保留堆栈上下文。
        Paginates by log entry blocks so filtered traceback context stays intact.
        """
        if self._log_dir is None:
            return None

        parsed_filename = self._parse_log_filename(filename)
        if parsed_filename is None:
            return None

        file_path = self._log_dir / filename
        if not self._validate_path(file_path):
            return None

        if scope == LOG_SCOPE_CURRENT_FILE:
            if not file_path.exists() or not file_path.is_file():
                return None
            source_files = [file_path]
        else:
            source_files = self._collect_category_log_paths(parsed_filename.category)
            if not source_files:
                return LogContentPage(
                    filename=filename,
                    category=parsed_filename.category,
                    scope=scope,
                    lines=[],
                    items=[],
                    total_lines=0,
                    total_entries=0,
                    searched_files=0,
                    page=page,
                    page_size=page_size,
                    has_more=False,
                )
            source_files = self._sort_paths_by_mtime(source_files, reverse=reverse)

        page_start = (page - 1) * page_size
        page_end = page_start + page_size

        items: list[LogContentLineItem] = []
        total_entries = 0
        total_lines = 0
        searched_files = 0

        for source_file in source_files:
            searched_files += 1
            try:
                entries = self._read_entries_from_file(source_file)
            except OSError:
                continue

            ordered_entries = reversed(entries) if reverse else entries
            for entry in ordered_entries:
                if not self._entry_matches(
                    entry,
                    keyword=keyword,
                    start_date=start_date,
                    end_date=end_date,
                ):
                    continue

                if page_start <= total_entries < page_end:
                    items.extend(
                        LogContentLineItem(
                            file_name=entry.file_name,
                            line_number=entry.start_line + offset,
                            content=line,
                        )
                        for offset, line in enumerate(entry.lines)
                    )

                total_entries += 1
                total_lines += len(entry.lines)

        has_more = total_entries > page_end

        return LogContentPage(
            filename=filename,
            category=parsed_filename.category,
            scope=scope,
            lines=[item.content for item in items],
            items=items,
            total_lines=total_lines,
            total_entries=total_entries,
            searched_files=searched_files,
            page=page,
            page_size=page_size,
            has_more=has_more,
        )

    def get_log_file_path(self, filename: str) -> Path | None:
        """
        获取日志文件的绝对路径（用于下载）/ Get log file absolute path (for download).

        Args:
            filename: 日志文件名

        Returns:
            文件绝对路径，不存在或路径不安全时返回 None
        """
        if self._log_dir is None:
            return None

        file_path = self._log_dir / filename

        if not self._validate_path(file_path):
            return None

        if not file_path.exists() or not file_path.is_file():
            return None

        return file_path.resolve()

    def delete_log_file(self, filename: str) -> bool:
        """
        删除日志文件 / Delete log file.

        注意：不允许删除当前活动日志文件。

        Args:
            filename: 日志文件名

        Returns:
            是否删除成功
        """
        if self._log_dir is None:
            return False

        file_path = self._log_dir / filename
        if not self._validate_path(file_path):
            return False

        if not file_path.exists() or not file_path.is_file():
            return False

        parsed = self._parse_log_filename(filename)
        if parsed is None:
            return False

        if self._is_current_log_file(filename, parsed):
            return False

        try:
            os.remove(file_path)
            return True
        except OSError:
            return False

    def get_log_stats(self) -> dict:
        """
        获取日志统计信息 / Get log statistics.

        Returns:
            包含总文件数、总大小、各分类统计的字典
        """
        categories = self.list_categories()

        total_files = sum(cat.file_count for cat in categories)
        total_size = sum(cat.total_size for cat in categories)

        return {
            "total_files": total_files,
            "total_size": total_size,
            "categories": [
                {
                    "code": cat.code,
                    "name": cat.name,
                    "description": cat.description,
                    "file_count": cat.file_count,
                    "total_size": cat.total_size,
                }
                for cat in categories
            ],
        }


__all__ = [
    "SystemLogService",
    "LogCategoryInfo",
    "LogContentLineItem",
    "LogContentPage",
    "LogFileInfo",
    "LogSearchScope",
    "LOG_SCOPE_CATEGORY",
    "LOG_SCOPE_CURRENT_FILE",
]
