"""
租户操作日志 API

提供租户内操作日志查询接口（只读）
"""

from fastapi import HTTPException, Request, status

from app.core.base_controller import TenantController
from app.core.base_schema import PageResponse
from app.core.deps import DbSession, QueryParams, ActiveTenantAdmin
from app.core.i18n import _
from app.core.response import success
from app.enums.rbac import PermissionScope
from app.rbac.decorators import permission_resource, action_read, MenuConfig
from app.schemas.system import OperationLogResponse, OperationLogListResponse
from app.services.system import OperationLogService


@permission_resource(
    resource="operation_log",
    name="menu.tenant.operation_log",  # i18n key
    scope=PermissionScope.TENANT,
    menu=MenuConfig(
        icon="lucide:file-text",
        path="/system/operation-logs",
        component="tenant/system/operation-logs/index",
        parent="system",  # 父菜单: 权限管理
        sort_order=20,
    )
)
class TenantOperationLogController(TenantController):
    """
    租户操作日志控制器
    
    提供租户内操作日志查询接口，租户只能查看本租户的日志，无删除权限
    """
    
    prefix = "/operation-logs"
    tags = ["租户操作日志"]
    
    def _register_routes(self) -> None:
        """注册路由"""
        router = self.router
        
        @router.get("", summary="获取操作日志列表")
        @action_read("action.operation_log.list")
        async def list_operation_logs(
            request: Request,
            db: DbSession,
            spec: QueryParams,
            current_admin: ActiveTenantAdmin,
        ):
            """
            获取当前租户的操作日志列表
            
            基于当前管理员权限过滤：
            - 租户所有者：可查看本租户所有日志
            - 普通管理员：只能查看自己及其角色子树下用户的日志
            
            支持 JSON:API 风格筛选参数:
            - filter[username][ilike]=xxx 用户名模糊搜索
            - filter[module]=AUTH 按模块筛选
            - filter[action]=CREATE 按操作类型筛选
            - filter[status_code]=200 按状态码筛选
            - filter[ip][ilike]=192.168 按IP模糊搜索
            - filter[created_at][gte]=2024-01-01 按创建时间范围筛选
            - sort=-created_at 排序
            - page[number]=1&page[size]=20 分页
            
            权限: operation_log:list
            """
            service = OperationLogService(db)
            items, total = await service.query_tenant_logs_by_permission(
                tenant_admin=current_admin,
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
        
        @router.get("/{log_id}", summary="获取操作日志详情")
        @action_read("action.operation_log.detail")
        async def get_operation_log(
            request: Request,
            db: DbSession,
            log_id: int,
            current_admin: ActiveTenantAdmin,
        ):
            """
            获取操作日志详情
            
            权限: operation_log:detail
            """
            service = OperationLogService(db)
            log = await service.get_by_id(log_id)
            
            if log is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=_("operation_log.not_found"),
                )
            
            # 租户隔离：只能查看本租户的日志
            if log.tenant_id != current_admin.tenant_id:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=_("operation_log.not_found"),
                )
            
            return success(
                data=OperationLogResponse.from_model(log, scope="tenant"),
                message=_("common.success"),
            )


# 导出路由器
router = TenantOperationLogController.get_router()

__all__ = ["router", "TenantOperationLogController"]
