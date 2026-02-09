"""
租户端 AI 调用日志 API

提供租户端 AI 调用日志查询接口（自动按 tenant_id 过滤）
"""

from fastapi import Request

from app.core.base_controller import TenantController
from app.core.deps import DbSession, QueryParams, ActiveTenantAdmin
from app.core.base_schema import PageResponse
from app.core.i18n import _
from app.core.response import success
from app.enums.rbac import PermissionScope
from app.exceptions import NotFoundException, AuthorizationException
from app.rbac.decorators import (
    permission_resource,
    MenuConfig,
    action_read,
)
from app.repositories.ai import AICallLogRepository


@permission_resource(
    resource="ai_tenant_call_log",
    name="menu.tenant.ai_call_log",
    scope=PermissionScope.TENANT,
    menu=MenuConfig(
        icon="lucide:scroll-text",
        path="/ai/call-logs",
        component="ai/call-logs/index",
        parent="ai_mgmt",
        sort_order=40,
    ),
)
class TenantAICallLogController(TenantController):
    """
    租户 AI 调用日志控制器

    提供租户端调用日志查询（自动按 tenant_id 过滤）
    """

    prefix = "/ai/call-logs"
    tags = ["AI 调用日志"]

    def _register_routes(self) -> None:
        """注册路由"""
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
            查询当前租户的 AI 调用日志列表

            自动按 tenant_id 过滤，支持 JSON:API 筛选:
            - filter[model_id]: 模型 ID
            - filter[status]: 调用状态
            - filter[created_at][gte]: 创建时间 >=
            - filter[created_at][lte]: 创建时间 <=

            权限: ai_tenant_call_log:list
            """
            repo = AICallLogRepository(db)

            # 强制注入 tenant_id 过滤
            if not spec.filters:
                spec.filters = {}
            spec.filters["tenant_id"] = {"eq": tenant_admin.tenant_id}

            items, total = await repo.query_list(spec)

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
            获取调用日志详情（含完整请求和响应体）

            仅允许查看自己租户的日志

            权限: ai_tenant_call_log:detail
            """
            repo = AICallLogRepository(db)
            log = await repo.get_by_id(log_id)

            if not log:
                raise NotFoundException(message=_("ai.error.call_log_not_found"))

            # 确保只能看自己租户的日志
            if log.tenant_id != tenant_admin.tenant_id:
                raise AuthorizationException(message=_("common.forbidden"))

            return success(data=log, message=_("common.success"))


# 导出路由器
router = TenantAICallLogController.get_router()

__all__ = ["router", "TenantAICallLogController"]
