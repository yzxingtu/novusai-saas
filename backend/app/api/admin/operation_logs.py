"""
平台端操作日志管理 API

提供操作日志查询、详情、删除接口
"""

from fastapi import Request

from app.core.base_controller import GlobalController
from app.core.base_schema import PageResponse
from app.core.deps import DbSession, ActiveAdmin, QueryParams
from app.core.i18n import _
from app.core.response import success
from app.enums.rbac import PermissionScope
from app.rbac.decorators import (
    permission_resource,
    action_read,
    action_delete,
    MenuConfig,
)
from app.schemas.system.operation_log import (
    OperationLogResponse,
    OperationLogListResponse,
    OperationLogDeleteRequest,
    OperatorSelectItem,
)
from app.services.system.operation_log_service import OperationLogService


@permission_resource(
    resource="operation_log",
    name="menu.admin.operation_log",  # i18n key
    scope=PermissionScope.ADMIN,    
    menu=MenuConfig(
        icon="lucide:file-text",
        path="/system/operation-logs",
        component="admin/system/operation-logs/index",
        parent="system_maintenance",
        sort_order=20,
    )
)
class AdminOperationLogController(GlobalController):
    """
    平台端操作日志控制器
    
    提供操作日志查询、详情、删除接口
    """
    
    prefix = "/operation-logs"
    tags = ["Operation Log Management"]
    service_class = OperationLogService
    
    def _register_routes(self) -> None:
        """注册路由"""
        router = self.router
        
        @router.get("", summary="获取操作日志列表")
        @action_read("action.operation_log.list")
        async def list_logs(
            request: Request,
            db: DbSession,
            spec: QueryParams,
            current_admin: ActiveAdmin,
        ):
            """
            获取操作日志列表（仅平台端日志）
            
            基于当前管理员权限过滤：
            - 超级管理员：可查看所有平台端日志
            - 普通管理员：只能查看自己及其角色子树下用户的日志
            
            支持 JSON:API 风格筛选参数:
            - filter[username][ilike]=xxx 用户名模糊搜索
            - filter[module]=auth 按模块筛选
            - filter[action]=login 按操作类型筛选
            - filter[response_code]=0 按响应码筛选
            - filter[ip][ilike]=192.168 按 IP 筛选
            - filter[created_at][gte]=2026-01-01 按时间筛选
            - sort=-created_at 排序
            - page[number]=1&page[size]=20 分页
            
            权限: operation_log:list
            """
            service = OperationLogService(db)
            items, total = await service.query_admin_logs_by_permission(
                admin=current_admin,
                spec=spec,
            )
            
            return success(
                data=PageResponse.create(
                    items=[OperationLogListResponse.from_model(item) for item in items],
                    total=total,
                    page=spec.page,
                    page_size=spec.size,
                ),
                message=_("common.success"),
            )
        
        @router.get("/operators", summary="获取操作人下拉列表")
        @action_read("action.operation_log.list")
        async def list_operators(
            request: Request,
            db: DbSession,
            current_admin: ActiveAdmin,
        ):
            """
            获取平台端操作日志中的去重操作人列表（含头像）
            
            用于搜索下拉选择和列表头像显示
            
            权限: operation_log:list
            """
            service = OperationLogService(db)
            operators = await service.get_admin_operators()
            return success(
                data=[OperatorSelectItem(**op) for op in operators],
                message=_("common.success"),
            )

        @router.get("/{log_id}", summary="获取操作日志详情")
        @action_read("action.operation_log.detail")
        async def get_log(
            request: Request,
            db: DbSession,
            log_id: int,
            current_admin: ActiveAdmin,
        ):
            """
            获取操作日志详情
            
            权限: operation_log:detail
            """
            service = OperationLogService(db)
            log = await service.get_by_id(log_id)
            
            if log is None:
                from fastapi import HTTPException, status
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=_("operation_log.not_found"),
                )
            
            return success(
                data=OperationLogResponse.from_model(log),
                message=_("common.success"),
            )
        
        @router.delete("", summary="批量删除操作日志")
        @action_delete("action.operation_log.delete")
        async def delete_logs(
            request: Request,
            db: DbSession,
            data: OperationLogDeleteRequest,
            current_admin: ActiveAdmin,
        ):
            """
            批量删除操作日志（软删除）
            
            权限: operation_log:delete
            """
            service = OperationLogService(db)
            deleted_count = await service.delete_logs(data.ids, soft=True)
            await db.commit()
            
            return success(
                data={"deleted_count": deleted_count},
                message=_("operation_log.deleted"),
            )


# 创建路由
router = AdminOperationLogController.get_router()


__all__ = ["router", "AdminOperationLogController"]
