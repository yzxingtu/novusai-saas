"""
平台端系统日志管理 API / Platform System Log Management API

提供文件日志的查看、下载、删除接口 / Provides file log viewing, downloading, and deletion endpoints
"""

from datetime import date, datetime
from typing import Literal

from fastapi import HTTPException, Query, Request, status
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from app.core.base_controller import GlobalController
from app.core.deps import ActiveAdmin, DbSession
from app.core.i18n import _
from app.core.response import success
from app.enums.rbac import PermissionScope
from app.rbac.decorators import (
    MenuConfig,
    action_delete,
    action_read,
    permission_resource,
)
from app.services.system import SystemLogService

# ============ Schemas / 数据模型 ============


class LogCategoryResponse(BaseModel):
    """日志分类响应 / Log category response"""

    code: str = Field(..., description=_("api.param.code"))
    name: str = Field(..., description=_("api.param.name"))
    description: str = Field(..., description=_("api.param.desc"))
    file_count: int = Field(..., description=_("api.param.file_count"))
    total_size: int = Field(..., description=_("api.param.total_size"))


class LogFileResponse(BaseModel):
    """日志文件响应 / Log file response"""

    name: str = Field(..., description=_("api.param.filename"))
    category: str = Field(..., description=_("api.param.code"))
    size: int = Field(..., description=_("api.param.size"))
    modified_at: datetime = Field(..., description=_("api.param.modified_at"))
    is_current: bool = Field(..., description=_("api.param.is_current"))


class LogContentLineItemResponse(BaseModel):
    """日志行项响应 / Log content line item response"""

    file_name: str = Field(..., description=_("api.param.filename"))
    line_number: int = Field(..., description=_("api.param.line_number"))
    content: str = Field(..., description=_("api.param.content"))


class LogContentResponse(BaseModel):
    """日志内容响应 / Log content response"""

    filename: str = Field(..., description=_("api.param.filename"))
    category: str = Field(..., description=_("api.param.log_category"))
    scope: Literal["current_file", "category"] = Field(
        ..., description=_("api.param.scope")
    )
    lines: list[str] = Field(..., description=_("api.param.lines"))
    items: list[LogContentLineItemResponse] = Field(
        ..., description=_("api.param.items")
    )
    total_lines: int = Field(..., description=_("api.param.total_lines"))
    total_entries: int = Field(..., description=_("api.param.total"))
    searched_files: int = Field(..., description=_("api.param.total_files"))
    page: int = Field(..., description=_("api.param.page"))
    page_size: int = Field(..., description=_("api.param.page_size"))
    has_more: bool = Field(..., description=_("api.param.has_more"))


class LogStatsResponse(BaseModel):
    """日志统计响应 / Log statistics response"""

    total_files: int = Field(..., description=_("api.param.total_files"))
    total_size: int = Field(..., description=_("api.param.total_size"))
    categories: list[LogCategoryResponse] = Field(
        ..., description=_("api.param.categories")
    )


# ============ Controller / 控制器 ============


@permission_resource(
    resource="system_log",
    name="menu.admin.system_log",  # i18n key / 菜单 i18n 键名
    scope=PermissionScope.ADMIN,
    parent_resource="system_maintenance",
    menu=MenuConfig(
        icon="lucide:file-code-2",
        path="/system-mgmt/system-logs",
        component="admin/system/system-logs/index",
        parent="logs",
        sort_order=20,
    ),
)
class AdminSystemLogController(GlobalController):
    """
    平台端系统日志控制器 / Platform System Log Controller

    提供文件日志的查看、下载、删除接口
    Provides file log viewing, downloading, and deletion endpoints
    """

    prefix = "/system-logs"
    tags = ["System Log Management"]

    def _register_routes(self) -> None:
        """注册路由 / Register routes"""
        router = self.router

        @router.get("/stats", summary="获取日志统计")
        @action_read("action.system_log.stats")
        async def get_log_stats(
            request: Request,
            db: DbSession,
            current_admin: ActiveAdmin,
        ):
            """
            获取日志统计信息 / Get log statistics

            返回总文件数、总大小及各分类统计
            Returns total files, total size, and statistics per category

            Permission: system_log:stats
            """
            service = SystemLogService()
            stats = service.get_log_stats()

            return success(
                data=LogStatsResponse(
                    total_files=stats["total_files"],
                    total_size=stats["total_size"],
                    categories=[
                        LogCategoryResponse(**cat) for cat in stats["categories"]
                    ],
                ),
                message=_("common.success"),
            )

        @router.get("/categories", summary="获取日志分类列表")
        @action_read("action.system_log.categories")
        async def list_categories(
            request: Request,
            db: DbSession,
            current_admin: ActiveAdmin,
        ):
            """
            获取日志分类列表 / Get log category list

            返回所有日志分类及其统计信息
            Returns all log categories with their statistics

            Permission: system_log:categories
            """
            service = SystemLogService()
            categories = service.list_categories()

            return success(
                data=[
                    LogCategoryResponse(
                        code=cat.code,
                        name=cat.name,
                        description=cat.description,
                        file_count=cat.file_count,
                        total_size=cat.total_size,
                    )
                    for cat in categories
                ],
                message=_("common.success"),
            )

        @router.get("/files", summary="获取日志文件列表")
        @action_read("action.system_log.files")
        async def list_files(
            request: Request,
            db: DbSession,
            current_admin: ActiveAdmin,
            category: str = Query(None, description=_("api.param.log_category")),
        ):
            """
            获取日志文件列表 / Get log file list

            可按分类筛选，按修改时间倒序排列
            Filter by category, sorted by modification time in descending order

            Permission: system_log:files
            """
            service = SystemLogService()
            files = service.list_log_files(category=category)

            return success(
                data=[
                    LogFileResponse(
                        name=f.name,
                        category=f.category,
                        size=f.size,
                        modified_at=f.modified_at,
                        is_current=f.is_current,
                    )
                    for f in files
                ],
                message=_("common.success"),
            )

        @router.get("/files/{filename}/content", summary="读取日志文件内容")
        @action_read("action.system_log.read")
        async def read_file_content(
            request: Request,
            db: DbSession,
            current_admin: ActiveAdmin,
            filename: str,
            page: int = Query(1, ge=1, description=_("api.param.page")),
            page_size: int = Query(
                100, ge=1, le=500, description=_("api.param.page_size")
            ),
            reverse: bool = Query(True, description=_("api.param.reverse")),
            keyword: str | None = Query(None, description=_("api.param.search")),
            start_date: date | None = Query(
                None, description=_("api.param.start_date")
            ),
            end_date: date | None = Query(None, description=_("api.param.end_date")),
            scope: Literal["current_file", "category"] = Query(
                "current_file",
                description=_("api.param.scope"),
            ),
        ):
            """
            分页读取日志文件内容 / Read log file content with pagination

            支持关键词、日期范围，以及当前文件/分类全量检索。
            Supports keyword/date-range filters and current-file/category-wide search.

            Permission: system_log:read
            """
            if start_date and end_date and start_date > end_date:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=_("system_log.invalid_date_range"),
                )

            service = SystemLogService()
            content = service.read_log_file(
                filename=filename,
                page=page,
                page_size=page_size,
                reverse=reverse,
                keyword=keyword,
                start_date=start_date,
                end_date=end_date,
                scope=scope,
            )

            if content is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=_("system_log.file_not_found"),
                )

            return success(
                data=LogContentResponse(
                    filename=content.filename,
                    category=content.category,
                    scope=content.scope,
                    lines=content.lines,
                    items=[
                        LogContentLineItemResponse(
                            file_name=item.file_name,
                            line_number=item.line_number,
                            content=item.content,
                        )
                        for item in content.items
                    ],
                    total_lines=content.total_lines,
                    total_entries=content.total_entries,
                    searched_files=content.searched_files,
                    page=content.page,
                    page_size=content.page_size,
                    has_more=content.has_more,
                ),
                message=_("common.success"),
            )

        @router.get("/files/{filename}/download", summary="下载日志文件")
        @action_read("action.system_log.download")
        async def download_file(
            request: Request,
            db: DbSession,
            current_admin: ActiveAdmin,
            filename: str,
        ):
            """
            下载日志文件 / Download log file

            Permission: system_log:download
            """
            service = SystemLogService()
            file_path = service.get_log_file_path(filename)

            if file_path is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=_("system_log.file_not_found"),
                )

            return FileResponse(
                path=file_path,
                filename=filename,
                media_type="text/plain; charset=utf-8",
            )

        @router.delete("/files/{filename}", summary="删除日志文件")
        @action_delete("action.system_log.delete")
        async def delete_file(
            request: Request,
            db: DbSession,
            current_admin: ActiveAdmin,
            filename: str,
        ):
            """
            删除日志文件 / Delete log file

            注意：不允许删除当前活动日志文件（如 app.log）
            Note: Current active log files (e.g. app.log) cannot be deleted

            Permission: system_log:delete
            """
            service = SystemLogService()

            # 检查文件是否存在 / Check if file exists
            file_path = service.get_log_file_path(filename)
            if file_path is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=_("system_log.file_not_found"),
                )

            # 尝试删除 / Attempt deletion
            deleted = service.delete_log_file(filename)

            if not deleted:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=_("system_log.cannot_delete_current"),
                )

            return success(
                data={"deleted": filename},
                message=_("system_log.deleted"),
            )


# 创建路由 / Create router
router = AdminSystemLogController.get_router()


__all__ = ["router", "AdminSystemLogController"]
