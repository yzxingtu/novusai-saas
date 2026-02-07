"""
平台端系统日志管理 API

提供文件日志的查看、下载、删除接口
"""

from datetime import datetime

from fastapi import HTTPException, Query, Request, status
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from app.core.base_controller import GlobalController
from app.core.deps import DbSession, ActiveAdmin
from app.core.i18n import _
from app.core.response import success
from app.enums.rbac import PermissionScope
from app.rbac.decorators import (
    permission_resource,
    action_read,
    action_delete,
    MenuConfig,
)
from app.services.system import SystemLogService


# ============ Schemas ============

class LogCategoryResponse(BaseModel):
    """日志分类响应"""
    code: str = Field(..., description="分类代码")
    name: str = Field(..., description="分类名称")
    description: str = Field(..., description="分类描述")
    file_count: int = Field(..., description="文件数量")
    total_size: int = Field(..., description="总大小（字节）")


class LogFileResponse(BaseModel):
    """日志文件响应"""
    name: str = Field(..., description="文件名")
    category: str = Field(..., description="分类代码")
    size: int = Field(..., description="文件大小（字节）")
    modified_at: datetime = Field(..., description="最后修改时间")
    is_current: bool = Field(..., description="是否为当前活动日志")


class LogContentResponse(BaseModel):
    """日志内容响应"""
    lines: list[str] = Field(..., description="日志行内容")
    total_lines: int = Field(..., description="总行数")
    page: int = Field(..., description="当前页码")
    page_size: int = Field(..., description="每页行数")
    has_more: bool = Field(..., description="是否有更多")


class LogStatsResponse(BaseModel):
    """日志统计响应"""
    total_files: int = Field(..., description="总文件数")
    total_size: int = Field(..., description="总大小（字节）")
    categories: list[LogCategoryResponse] = Field(..., description="分类统计")


# ============ Controller ============

@permission_resource(
    resource="system_log",
    name="menu.admin.system_log",  # i18n key
    scope=PermissionScope.ADMIN,
    menu=MenuConfig(
        icon="lucide:file-code-2",
        path="/system-mgmt/system-logs",
        component="admin/system/system-logs/index",
        parent="system_maintenance",
        sort_order=30,
    )
)
class AdminSystemLogController(GlobalController):
    """
    平台端系统日志控制器
    
    提供文件日志的查看、下载、删除接口
    """
    
    prefix = "/system-logs"
    tags = ["系统日志管理"]
    
    def _register_routes(self) -> None:
        """注册路由"""
        router = self.router
        
        @router.get("/stats", summary="获取日志统计")
        @action_read("action.system_log.stats")
        async def get_log_stats(
            request: Request,
            db: DbSession,
            current_admin: ActiveAdmin,
        ):
            """
            获取日志统计信息
            
            返回总文件数、总大小及各分类统计
            
            权限: system_log:stats
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
            获取日志分类列表
            
            返回所有日志分类及其统计信息
            
            权限: system_log:categories
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
            category: str = Query(None, description="日志分类"),
        ):
            """
            获取日志文件列表
            
            可按分类筛选，按修改时间倒序排列
            
            权限: system_log:files
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
            page: int = Query(1, ge=1, description="页码"),
            page_size: int = Query(100, ge=1, le=500, description="每页行数"),
            reverse: bool = Query(True, description="是否倒序（最新在前）"),
        ):
            """
            分页读取日志文件内容
            
            默认最新的日志在前（倒序）
            
            权限: system_log:read
            """
            service = SystemLogService()
            content = service.read_log_file(
                filename=filename,
                page=page,
                page_size=page_size,
                reverse=reverse,
            )
            
            if content is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=_("system_log.file_not_found"),
                )
            
            return success(
                data=LogContentResponse(
                    lines=content.lines,
                    total_lines=content.total_lines,
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
            下载日志文件
            
            权限: system_log:download
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
            删除日志文件
            
            注意：不允许删除当前活动日志文件（如 app.log）
            
            权限: system_log:delete
            """
            service = SystemLogService()
            
            # 检查文件是否存在
            file_path = service.get_log_file_path(filename)
            if file_path is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=_("system_log.file_not_found"),
                )
            
            # 尝试删除
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


# 创建路由
router = AdminSystemLogController.get_router()


__all__ = ["router", "AdminSystemLogController"]
