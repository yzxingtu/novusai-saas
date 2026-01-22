"""
系统日志服务模块

提供文件日志的查询、读取、下载等功能
"""

import os
import re
from datetime import datetime
from pathlib import Path
from typing import NamedTuple

from app.core.config import settings
from app.core.logging import LogManager
from app.enums.log import LogCategoryEnum


class LogFileInfo(NamedTuple):
    """日志文件信息"""
    name: str
    category: str
    size: int
    modified_at: datetime
    is_current: bool  # 是否为当前活动日志文件


class LogCategoryInfo(NamedTuple):
    """日志分类信息"""
    code: str
    name: str
    description: str
    file_count: int
    total_size: int


class LogContentPage(NamedTuple):
    """日志内容分页结果"""
    lines: list[str]
    total_lines: int
    page: int
    page_size: int
    has_more: bool


class SystemLogService:
    """
    系统日志服务
    
    提供文件日志的管理功能，包括：
    - 日志分类列表
    - 日志文件列表
    - 日志内容读取（分页）
    - 日志文件下载路径
    - 日志文件删除
    """
    
    # 日志分类描述映射
    _CATEGORY_DESCRIPTIONS = {
        LogCategoryEnum.APP.value: "应用运行日志，记录系统运行状态",
        LogCategoryEnum.ERROR.value: "错误日志，记录系统错误和异常",
        LogCategoryEnum.DB.value: "数据库日志，记录 SQL 查询和数据库操作",
        LogCategoryEnum.TASK.value: "计划任务日志，记录定时任务执行情况",
        LogCategoryEnum.QUEUE.value: "队列日志，记录消息队列处理情况",
    }
    
    # 日志分类显示名称
    _CATEGORY_NAMES = {
        LogCategoryEnum.APP.value: "应用日志",
        LogCategoryEnum.ERROR.value: "错误日志",
        LogCategoryEnum.DB.value: "数据库日志",
        LogCategoryEnum.TASK.value: "任务日志",
        LogCategoryEnum.QUEUE.value: "队列日志",
    }
    
    def __init__(self) -> None:
        """初始化服务"""
        # 确保 LogManager 已初始化
        if not LogManager._initialized:
            LogManager.init()
        
        self._log_dir = LogManager.get_log_dir()
        if self._log_dir is None:
            self._log_dir = Path(settings.LOG_DIR)
    
    def _validate_path(self, file_path: Path) -> bool:
        """
        验证文件路径安全性
        
        防止路径穿越攻击，确保文件在日志目录内
        
        Args:
            file_path: 待验证的文件路径
            
        Returns:
            路径是否安全
        """
        if self._log_dir is None:
            return False
        
        try:
            # 解析为绝对路径
            resolved_path = file_path.resolve()
            resolved_log_dir = self._log_dir.resolve()
            
            # 检查是否在日志目录内
            return str(resolved_path).startswith(str(resolved_log_dir))
        except (OSError, ValueError):
            return False
    
    def _parse_log_filename(self, filename: str) -> tuple[str, str | None]:
        """
        解析日志文件名，提取分类和日期
        
        支持的格式：
        - {category}.log (当前日志)
        - {category}.log.2026-01-20 (历史日志)
        
        Args:
            filename: 日志文件名
            
        Returns:
            (category, date_str) 元组，date_str 为 None 表示当前日志
        """
        # 匹配 {category}.log.{date}
        match = re.match(r'^([a-z_]+)\.log\.(\d{4}-\d{2}-\d{2})$', filename)
        if match:
            return match.group(1), match.group(2)
        
        # 匹配 {category}.log
        match = re.match(r'^([a-z_]+)\.log$', filename)
        if match:
            return match.group(1), None
        
        return "", None
    
    def list_categories(self) -> list[LogCategoryInfo]:
        """
        获取日志分类列表
        
        Returns:
            日志分类信息列表
        """
        categories = []
        
        for category in LogCategoryEnum:
            category_value = category.value
            
            # 统计该分类的文件数和总大小
            file_count = 0
            total_size = 0
            
            if self._log_dir:
                for file_path in self._log_dir.glob(f"{category_value}.log*"):
                    if file_path.is_file():
                        file_count += 1
                        total_size += file_path.stat().st_size
            
            categories.append(LogCategoryInfo(
                code=category_value,
                name=self._CATEGORY_NAMES.get(category_value, category_value),
                description=self._CATEGORY_DESCRIPTIONS.get(category_value, ""),
                file_count=file_count,
                total_size=total_size,
            ))
        
        return categories
    
    def list_log_files(
        self,
        category: str | None = None,
    ) -> list[LogFileInfo]:
        """
        获取日志文件列表
        
        Args:
            category: 日志分类（可选，为空时返回所有分类）
            
        Returns:
            日志文件信息列表，按修改时间倒序
        """
        if self._log_dir is None:
            return []
        
        files: list[LogFileInfo] = []
        
        # 确定要搜索的模式
        if category:
            patterns = [f"{category}.log*"]
        else:
            patterns = [f"{cat.value}.log*" for cat in LogCategoryEnum]
        
        for pattern in patterns:
            for file_path in self._log_dir.glob(pattern):
                if not file_path.is_file():
                    continue
                
                # 解析文件名
                parsed_category, date_str = self._parse_log_filename(file_path.name)
                if not parsed_category:
                    continue
                
                # 如果指定了分类，验证匹配
                if category and parsed_category != category:
                    continue
                
                stat = file_path.stat()
                files.append(LogFileInfo(
                    name=file_path.name,
                    category=parsed_category,
                    size=stat.st_size,
                    modified_at=datetime.fromtimestamp(stat.st_mtime),
                    is_current=(date_str is None),
                ))
        
        # 按修改时间倒序排序
        files.sort(key=lambda f: f.modified_at, reverse=True)
        return files
    
    def read_log_file(
        self,
        filename: str,
        page: int = 1,
        page_size: int = 100,
        reverse: bool = True,
    ) -> LogContentPage | None:
        """
        分页读取日志文件内容
        
        Args:
            filename: 日志文件名
            page: 页码（从 1 开始）
            page_size: 每页行数
            reverse: 是否倒序（最新的在前）
            
        Returns:
            日志内容分页结果，文件不存在或路径不安全时返回 None
        """
        if self._log_dir is None:
            return None
        
        file_path = self._log_dir / filename
        
        # 安全验证
        if not self._validate_path(file_path):
            return None
        
        if not file_path.exists() or not file_path.is_file():
            return None
        
        try:
            # 读取所有行
            with open(file_path, "r", encoding="utf-8", errors="replace") as f:
                all_lines = f.readlines()
            
            total_lines = len(all_lines)
            
            # 倒序处理
            if reverse:
                all_lines = all_lines[::-1]
            
            # 分页
            start = (page - 1) * page_size
            end = start + page_size
            page_lines = all_lines[start:end]
            
            # 去除每行末尾的换行符
            page_lines = [line.rstrip("\n\r") for line in page_lines]
            
            has_more = end < total_lines
            
            return LogContentPage(
                lines=page_lines,
                total_lines=total_lines,
                page=page,
                page_size=page_size,
                has_more=has_more,
            )
        except (OSError, IOError):
            return None
    
    def get_log_file_path(self, filename: str) -> Path | None:
        """
        获取日志文件的绝对路径（用于下载）
        
        Args:
            filename: 日志文件名
            
        Returns:
            文件绝对路径，不存在或路径不安全时返回 None
        """
        if self._log_dir is None:
            return None
        
        file_path = self._log_dir / filename
        
        # 安全验证
        if not self._validate_path(file_path):
            return None
        
        if not file_path.exists() or not file_path.is_file():
            return None
        
        return file_path.resolve()
    
    def delete_log_file(self, filename: str) -> bool:
        """
        删除日志文件
        
        注意：不允许删除当前活动日志文件（{category}.log）
        
        Args:
            filename: 日志文件名
            
        Returns:
            是否删除成功
        """
        if self._log_dir is None:
            return False
        
        file_path = self._log_dir / filename
        
        # 安全验证
        if not self._validate_path(file_path):
            return False
        
        if not file_path.exists() or not file_path.is_file():
            return False
        
        # 不允许删除当前活动日志文件
        parsed_category, date_str = self._parse_log_filename(filename)
        if date_str is None:
            # 当前活动日志文件，不允许删除
            return False
        
        try:
            os.remove(file_path)
            return True
        except OSError:
            return False
    
    def get_log_stats(self) -> dict:
        """
        获取日志统计信息
        
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
    "LogFileInfo",
    "LogCategoryInfo",
    "LogContentPage",
]
