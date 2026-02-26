"""
AI 调用日志管理 API (Admin)

提供平台端 AI 调用日志查询和分析接口（平台管理员专用）
"""

from datetime import date
from typing import Optional

from fastapi import Query, Request

from app.core.base_controller import GlobalController
from app.core.deps import DbSession, QueryParams, ActiveAdmin
from app.core.base_schema import PageResponse
from app.core.i18n import _
from app.core.response import success
from app.enums.rbac import PermissionScope
from app.exceptions import NotFoundException
from app.rbac.decorators import (
    permission_resource,
    MenuConfig,
    action_read,
)
from app.services.ai import CallLogService


@permission_resource(
    resource="ai_call_log",
    name="menu.admin.ai_call_log",
    scope=PermissionScope.ADMIN_ONLY,
    menu=MenuConfig(
        icon="lucide:scroll-text",
        path="/ai/monitor/call-logs",
        component="ai/call-logs/index",
        parent="ai_ops",
        sort_order=10,
    ),
)
class AdminAICallLogController(GlobalController):
    """
    AI 调用日志控制器

    提供调用日志查询和统计分析接口
    """

    prefix = "/ai/call-logs"
    tags = [_("menu.tags.admin_ai_call_log")]

    def _register_routes(self) -> None:
        """注册路由"""
        router = self.router

        @router.get("", summary="查询 AI 调用日志列表")
        @action_read("action.ai_call_log.list")
        async def list_call_logs(
            request: Request,
            db: DbSession,
            spec: QueryParams,
            admin: ActiveAdmin,
        ):
            """
            查询 AI 调用日志列表

            支持 JSON:API 风格筛选:
            - filter[tenant_id]: 租户 ID
            - filter[model_id]: 模型 ID
            - filter[status]: 调用状态
            - filter[created_at][gte]: 创建时间 >=
            - filter[created_at][lte]: 创建时间 <=

            权限: ai_call_log:list
            """
            service = CallLogService(db)
            items, total = await service.query_list(spec)

            return success(
                data=PageResponse.create(
                    items=items,
                    total=total,
                    page=spec.page,
                    page_size=spec.size,
                ),
                message=_("common.success"),
            )

        @router.get("/statistics", summary="获取调用统计信息")
        @action_read("action.ai_call_log.statistics")
        async def get_statistics(
            request: Request,
            db: DbSession,
            admin: ActiveAdmin,
            tenant_id: Optional[int] = Query(None, description="租户 ID"),
            start_date: Optional[date] = Query(None, description="开始日期"),
            end_date: Optional[date] = Query(None, description="结束日期"),
            group_by: Optional[str] = Query(None, description="分组维度: daily/model/user，缺省返回汇总"),
        ):
            """
            获取调用统计信息

            不传 group_by 时返回单个汇总 dict；
            传 group_by=daily/model/user 时返回分组列表

            权限: ai_call_log:statistics
            """
            service = CallLogService(db)

            if group_by is None:
                statistics = await service.get_overall_summary(
                    tenant_id=tenant_id,
                    start_date=start_date,
                    end_date=end_date,
                )
            else:
                statistics = await service.get_statistics(
                    tenant_id=tenant_id,
                    start_date=start_date,
                    end_date=end_date,
                    group_by=group_by,
                )

            return success(data=statistics, message=_("common.success"))

        @router.get("/failed", summary="获取失败的调用日志")
        @action_read("action.ai_call_log.failed")
        async def list_failed_logs(
            request: Request,
            db: DbSession,
            admin: ActiveAdmin,
            tenant_id: Optional[int] = Query(None, description="租户 ID"),
            start_date: Optional[date] = Query(None, description="开始日期"),
            limit: int = Query(100, ge=1, le=1000, description="返回数量"),
        ):
            """
            获取失败的调用日志

            权限: ai_call_log:failed
            """
            service = CallLogService(db)
            logs = await service.get_failed_logs(
                tenant_id=tenant_id,
                start_date=start_date,
                limit=limit,
            )

            return success(data=logs, message=_("common.success"))

        @router.get("/{log_id}", summary="获取调用日志详情")
        @action_read("action.ai_call_log.detail")
        async def get_call_log_detail(
            request: Request,
            db: DbSession,
            log_id: int,
            admin: ActiveAdmin,
        ):
            """
            获取调用日志详情（含完整请求和响应体）

            权限: ai_call_log:detail
            """
            service = CallLogService(db)
            log = await service.get_by_id(log_id)

            if not log:
                raise NotFoundException(message=_("ai.error.call_log_not_found"))

            return success(data=log, message=_("common.success"))


# 导出路由器
router = AdminAICallLogController.get_router()

__all__ = ["router", "AdminAICallLogController"]
