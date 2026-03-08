"""
租户操作日志 API

提供租户内操作日志查询接口（只读）
"""

from fastapi import HTTPException, Request, status

from app.core.base_controller import TenantController
from app.core.base_schema import PageResponse
from app.core.deps import ActiveTenantAdmin, DbSession, QueryParams
from app.core.i18n import _
from app.core.response import success
from app.enums.rbac import PermissionScope
from app.rbac.decorators import MenuConfig, action_read, permission_resource
from app.schemas.system import OperationLogListResponse, OperationLogResponse
from app.schemas.system.operation_log import OperatorSelectItem
from app.services.system import OperationLogService


@permission_resource(
    resource="operation_log",
    name="menu.tenant.operation_log",  # i18n key
    scope=PermissionScope.ALL_TENANTS,
    parent_resource="logs",
    menu=MenuConfig(
        icon="lucide:file-text",
        path="/system/operation-logs",
        component="tenant/system/operation-logs/index",
        parent="logs",
        sort_order=10,
    )
)
class TenantOperationLogController(TenantController):
    """
    租户操作日志控制器

    提供租户内操作日志查询接口，租户只能查看本租户的日志，无删除权限
    """

    prefix = "/operation-logs"
    tags = ["Tenant Operation Logs"]

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

        @router.get("/operators", summary="获取操作人下拉列表")
        @action_read("action.operation_log.list")
        async def list_operators(
            request: Request,
            db: DbSession,
            current_admin: ActiveTenantAdmin,
            search: str | None = None,
            user_type: str | None = None,
            page: int | None = None,
            page_size: int = 10,
        ):
            """
            获取当前租户操作日志中的去重操作人列表

            支持两种模式：
            - 分页模式（传 page 参数）：返回 {items, total, page, page_size} 供 ApiSelect 使用
            - 全量模式（不传 page）：返回完整列表（含头像）供表格头像映射

            权限: operation_log:list
            """
            service = OperationLogService(db)

            if page is not None:
                # 分页模式：供 ApiSelect 远程搜索
                items, total = await service.get_tenant_operators_select(
                    tenant_id=current_admin.tenant_id,
                    search=search,
                    user_type=user_type,
                    page=page,
                    page_size=page_size,
                )
                return success(
                    data={
                        "items": items,
                        "total": total,
                        "page": page,
                        "page_size": page_size,
                    },
                    message=_("common.success"),
                )

            # 全量模式：返回含头像的完整列表
            operators = await service.get_tenant_operators(current_admin.tenant_id)
            return success(
                data=[OperatorSelectItem(**op) for op in operators],
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
                data=OperationLogResponse.from_model(log),
                message=_("common.success"),
            )


# 导出路由器
router = TenantOperationLogController.get_router()

__all__ = ["router", "TenantOperationLogController"]
