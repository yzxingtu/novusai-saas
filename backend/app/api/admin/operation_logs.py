"""
平台端操作日志管理 API / Platform Operation Log API

提供操作日志查询、详情、删除接口
Provides operation log query, detail, delete endpoints.
"""

from fastapi import Query, Request

from app.core.base_controller import GlobalController
from app.core.base_schema import PageResponse
from app.core.deps import ActiveAdmin, DbSession, QueryParams
from app.core.i18n import _
from app.core.response import serialize_datetime_for_api, success
from app.enums.rbac import PermissionScope
from app.rbac.decorators import (
    MenuConfig,
    action_delete,
    action_read,
    permission_resource,
)
from app.schemas.system.operation_log import (
    OperationLogDeleteRequest,
    OperatorSelectItem,
)
from app.services.system.operation_log_service import OperationLogService


@permission_resource(
    resource="operation_log",
    name="menu.admin.operation_log",  # i18n key / 菜单 i18n 键名
    scope=PermissionScope.ADMIN,
    parent_resource="system_maintenance",
    menu=MenuConfig(
        icon="lucide:file-text",
        path="/system/operation-logs",
        component="admin/system/operation-logs/index",
        parent="logs",
        sort_order=10,
    ),
)
class AdminOperationLogController(GlobalController):
    """
    平台端操作日志控制器 / Platform Operation Log Controller

    提供操作日志查询、详情、删除接口 / Provides operation log query, detail, delete endpoints
    """

    prefix = "/operation-logs"
    tags = ["Operation Log Management"]
    service_class = OperationLogService

    def _register_routes(self) -> None:
        """注册路由 / Register routes"""
        router = self.router

        @router.get("", summary="获取操作日志列表 / Get operation log list")
        @action_read("action.operation_log.list")
        async def list_logs(
            request: Request,
            db: DbSession,
            spec: QueryParams,
            current_admin: ActiveAdmin,
        ):
            """
            获取操作日志列表（仅平台端日志） / Get operation log list (platform logs only)

            基于当前管理员权限过滤 / Filtered based on current admin permissions:
            - 超级管理员：可查看所有平台端日志 / Super admin: can view all platform logs
            - 普通管理员：只能查看自己及其角色子树下用户的日志 / Regular admin: own logs and role subtree users' logs only

            支持 JSON:API 风格筛选参数 / Supports JSON:API style filter params:
            - filter[trace_id]=xxx 按追踪 ID 精确筛选 / Exact filter by trace ID
            - filter[username][ilike]=xxx 用户名模糊搜索 / Username fuzzy search
            - filter[module]=auth 按模块筛选 / Filter by module
            - filter[action]=login 按操作类型筛选 / Filter by action type
            - filter[response_code]=0 按响应码筛选 / Filter by response code
            - filter[ip][ilike]=192.168 按 IP 筛选 / Filter by IP
            - filter[created_at][gte]=2026-01-01 按时间筛选 / Filter by time
            - sort=-created_at 排序 / Sort
            - page[number]=1&page[size]=20 分页 / Pagination

            权限 / Permission: operation_log:list
            """
            service = OperationLogService(db)
            items, total = await service.query_admin_logs_by_permission(
                admin=current_admin,
                spec=spec,
            )
            serialized_items = await service.serialize_logs(items)

            return success(
                data=PageResponse.create(
                    items=serialized_items,
                    total=total,
                    page=spec.page,
                    page_size=spec.size,
                ),
                message=_("common.success"),
            )

        @router.get("/operators", summary="获取操作人下拉列表 / Get operator list")
        @action_read("action.operation_log.list")
        async def list_operators(
            request: Request,
            db: DbSession,
            current_admin: ActiveAdmin,
            search: str | None = None,
            page: int | None = None,
            page_size: int = Query(10, ge=1, le=100),
        ):
            """
            获取平台端操作日志中的去重操作人列表（含头像） / Get deduplicated operator list from platform logs (with avatar)

            支持两种模式 / Supports two modes:
            - 分页模式（传 page 参数）：返回 {items, total, page, page_size} 供远程下拉使用
            - 全量模式（不传 page）：返回完整列表，兼容旧逻辑

            权限 / Permission: operation_log:list
            """
            service = OperationLogService(db)

            if page is not None:
                items, total = await service.get_admin_operators_select(
                    search=search,
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

            operators = await service.get_admin_operators()
            return success(
                data=[OperatorSelectItem(**op) for op in operators],
                message=_("common.success"),
            )

        @router.get(
            "/export", summary="导出操作日志 CSV / Export operation logs as CSV"
        )
        @action_read("action.operation_log.list")
        async def export_logs(
            request: Request,
            db: DbSession,
            spec: QueryParams,
            current_admin: ActiveAdmin,
        ):
            """
            导出操作日志为 CSV（最多 10000 条） / Export operation logs as CSV (max 10000 records)

            支持与列表相同的筛选参数 / Supports same filter params as list

            权限 / Permission: operation_log:list
            """
            from app.core.csv_export import MAX_EXPORT_ROWS, csv_streaming_response

            spec.size = MAX_EXPORT_ROWS
            spec.page = 1
            service = OperationLogService(db)
            items, _total = await service.query_admin_logs_by_permission(
                admin=current_admin,
                spec=spec,
            )
            serialized_items = await service.serialize_logs(items)

            rows = [
                {
                    "id": item.get("id", ""),
                    "username": item.get("display_name")
                    or item.get("nickname")
                    or item.get("username")
                    or "",
                    "module": item.get("module_label") or item.get("module") or "-",
                    "action": item.get("action_label") or item.get("action") or "-",
                    "ip": item.get("ip") or "",
                    "response_code": item.get("response_code", ""),
                    "created_at": (
                        item.get("created_at")
                        if isinstance(item.get("created_at"), str)
                        else serialize_datetime_for_api(item.get("created_at"))
                        or str(item.get("created_at", ""))
                    ),
                }
                for item in serialized_items
            ]

            columns = [
                {"field": "id", "header": "ID"},
                {"field": "username", "header": _("operation_log.username")},
                {"field": "module", "header": _("operation_log.module")},
                {"field": "action", "header": _("operation_log.action")},
                {"field": "ip", "header": "IP"},
                {"field": "response_code", "header": _("operation_log.response_code")},
                {"field": "created_at", "header": _("common.createdAt")},
            ]

            return csv_streaming_response(rows, columns, "operation_logs.csv")

        @router.get("/{log_id}", summary="获取操作日志详情 / Get operation log detail")
        @action_read("action.operation_log.detail")
        async def get_log(
            request: Request,
            db: DbSession,
            log_id: int,
            current_admin: ActiveAdmin,
        ):
            """
            获取操作日志详情 / Get operation log detail

            权限 / Permission: operation_log:detail
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
                data=await service.serialize_log(log),
                message=_("common.success"),
            )

        @router.delete("", summary="批量删除操作日志 / Batch delete operation logs")
        @action_delete("action.operation_log.delete")
        async def delete_logs(
            request: Request,
            db: DbSession,
            data: OperationLogDeleteRequest,
            current_admin: ActiveAdmin,
        ):
            """
            批量删除操作日志（软删除） / Batch delete operation logs (soft delete)

            权限 / Permission: operation_log:delete
            """
            service = OperationLogService(db)
            deleted_count = await service.delete_logs(data.ids, soft=True)
            await db.commit()

            return success(
                data={"deleted_count": deleted_count},
                message=_("operation_log.deleted"),
            )


# 创建路由 / Create router
router = AdminOperationLogController.get_router()


__all__ = ["router", "AdminOperationLogController"]
