"""
企业操作日志 API / Tenant Operation Log API

提供企业内操作日志查询接口（只读）
Provides tenant operation log query endpoints (read-only)
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
    name="menu.tenant.operation_log",  # i18n key / 菜单 i18n 键名
    scope=PermissionScope.TENANT,
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
    企业操作日志控制器 / Tenant Operation Log Controller

    提供企业内操作日志查询接口，企业只能查看本企业的日志，无删除权限
    Provides tenant operation log query endpoints, tenant can only view own logs, no delete permission
    """

    prefix = "/operation-logs"
    tags = ["Tenant Operation Logs"]

    def _register_routes(self) -> None:
        """注册路由 / Register routes"""
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
            获取当前企业的操作日志列表 / Get current tenant operation log list

            基于当前管理员权限过滤 / Filtered by current admin permissions:
            - 企业所有者：可查看本企业所有日志 / Tenant owner: can view all tenant logs
            - 普通管理员：只能查看自己及其角色子树下用户的日志 / Regular admin: can only view own and subordinate role users' logs

            支持 JSON:API 风格筛选参数 / Supports JSON:API filter params:
            - filter[trace_id]=xxx 按追踪 ID 精确筛选 / Exact filter by trace ID
            - filter[username][ilike]=xxx 用户名模糊搜索 / Username fuzzy search
            - filter[module]=AUTH 按模块筛选 / Filter by module
            - filter[action]=CREATE 按操作类型筛选 / Filter by action type
            - filter[status_code]=200 按状态码筛选 / Filter by status code
            - filter[ip][ilike]=192.168 按IP模糊搜索 / IP fuzzy search
            - filter[created_at][gte]=2024-01-01 按创建时间范围筛选 / Filter by creation time range
            - sort=-created_at 排序 / Sorting
            - page[number]=1&page[size]=20 分页 / Pagination

            权限 / Permission: operation_log:list
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
            获取当前企业操作日志中的去重操作人列表 / Get deduplicated operator list from tenant operation logs

            支持两种模式 / Supports two modes:
            - 分页模式（传 page 参数）：返回 {items, total, page, page_size} 供 ApiSelect 使用 / Paginated mode (with page param): returns {items, total, page, page_size} for ApiSelect
            - 全量模式（不传 page）：返回完整列表（含头像）供表格头像映射 / Full mode (without page): returns complete list (with avatars) for table avatar mapping

            权限 / Permission: operation_log:list
            """
            service = OperationLogService(db)

            if page is not None:
                # 分页模式：供 ApiSelect 远程搜索 / Paginated mode: for ApiSelect remote search
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

            # 全量模式：返回含头像的完整列表 / Full mode: return complete list with avatars
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
            获取操作日志详情 / Get operation log details

            权限 / Permission: operation_log:detail
            """
            service = OperationLogService(db)
            log = await service.get_by_id(log_id)

            if log is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=_("operation_log.not_found"),
                )

            # 企业隔离：只能查看本企业的日志 / Tenant isolation: can only view own tenant's logs
            if log.tenant_id != current_admin.tenant_id:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=_("operation_log.not_found"),
                )

            return success(
                data=OperationLogResponse.from_model(log),
                message=_("common.success"),
            )


# 导出路由器 / Export router
router = TenantOperationLogController.get_router()

__all__ = ["router", "TenantOperationLogController"]
