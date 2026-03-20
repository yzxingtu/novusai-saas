"""
企业端 AI 调用日志 API / Tenant AI Call Log API

提供企业端 AI 调用日志查询接口（自动按 tenant_id 过滤）
Provides tenant AI call log query endpoints (auto-filtered by tenant_id)
"""

from fastapi import Request

from app.core.base_controller import TenantController
from app.core.base_schema import PageResponse
from app.core.deps import ActiveTenantAdmin, DbSession, QueryParams
from app.core.i18n import _
from app.core.response import success
from app.enums.rbac import PermissionScope
from app.exceptions import AuthorizationException, NotFoundException
from app.rbac.decorators import (
    MenuConfig,
    action_read,
    permission_resource,
)
from app.repositories.ai import AICallLogRepository


@permission_resource(
    resource="ai_tenant_call_log",
    name="menu.tenant.ai_call_log",
    scope=PermissionScope.ALL_TENANTS,
    parent_resource="ai_analytics",
    menu=MenuConfig(
        icon="lucide:scroll-text",
        path="/ai/call-logs",
        component="ai/call-logs/index",
        parent="ai_analytics",
        sort_order=40,
    ),
)
class TenantAICallLogController(TenantController):
    """
    企业 AI 调用日志控制器 / Tenant AI Call Log Controller

    提供企业端调用日志查询（自动按 tenant_id 过滤）
    Provides tenant call log query (auto-filtered by tenant_id)
    """

    prefix = "/ai/call-logs"
    tags = [_("menu.tags.tenant_ai_call_log")]

    def _register_routes(self) -> None:
        """注册路由 / Register routes"""
        router = self.router

        @router.get("", summary="查询 AI 调用日志列表")
        @action_read("action.ai_tenant_call_log.list")
        async def list_call_logs(
            request: Request,
            db: DbSession,
            spec: QueryParams,
            tenant_admin: ActiveTenantAdmin,
        ):
            """
            查询当前企业的 AI 调用日志列表 / Query current tenant AI call log list

            自动按 tenant_id 过滤，支持 JSON:API 筛选 / Auto-filtered by tenant_id, supports JSON:API filtering:
            - filter[model_id]: 模型 ID / model ID
            - filter[status]: 调用状态 / call status
            - filter[created_at][gte]: 创建时间 >= / created_at >=
            - filter[created_at][lte]: 创建时间 <= / created_at <=

            权限 / Permission: ai_tenant_call_log:list
            """
            from app.schemas.common.query import FilterRule

            repo = AICallLogRepository(db)

            # 强制注入 tenant_id 过滤 / Force inject tenant_id filter
            forced = [
                FilterRule(
                    field="tenant_id",
                    operator="eq",
                    value=tenant_admin.tenant_id,
                ),
            ]

            items, total = await repo.query_list_with_names(
                spec,
                forced_filters=forced,
                include_tenant_names=False,
                include_caller_names=True,
            )

            return success(
                data=PageResponse.create(
                    items=items,
                    total=total,
                    page=spec.page,
                    page_size=spec.size,
                ),
                message=_("common.success"),
            )

        @router.get("/{log_id}", summary="获取调用日志详情")
        @action_read("action.ai_tenant_call_log.detail")
        async def get_call_log_detail(
            request: Request,
            db: DbSession,
            log_id: int,
            tenant_admin: ActiveTenantAdmin,
        ):
            """
            获取调用日志详情（含完整请求和响应体） / Get call log details (with full request and response body)

            仅允许查看自己企业的日志
            Only allows viewing own tenant's logs

            权限 / Permission: ai_tenant_call_log:detail
            """
            repo = AICallLogRepository(db)
            log = await repo.get_by_id(log_id)

            if not log:
                raise NotFoundException(message=_("ai.error.call_log_not_found"))

            # 确保只能看自己企业的日志 / Ensure can only view own tenant's logs
            if log.tenant_id != tenant_admin.tenant_id:
                raise AuthorizationException(message=_("common.forbidden"))

            payload = (
                await repo.enrich_logs_to_dicts(
                    [log],
                    include_tenant_names=False,
                    include_caller_names=True,
                    include_payload=True,
                )
            )[0]
            return success(data=payload, message=_("common.success"))


# 导出路由器 / Export router
router = TenantAICallLogController.get_router()

__all__ = ["router", "TenantAICallLogController"]
