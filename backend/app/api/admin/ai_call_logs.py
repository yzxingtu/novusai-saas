"""
AI 调用日志管理 API (Admin) / AI Call Log API (Admin)

提供平台端 AI 调用日志查询和分析接口（平台管理员专用）
Provides platform AI call log query and analysis endpoints (platform admin only).
"""

from datetime import date

from fastapi import Query, Request

from app.core.base_controller import GlobalController
from app.core.base_schema import PageResponse
from app.core.deps import ActiveAdmin, DbSession, QueryParams
from app.core.i18n import _
from app.core.response import success
from app.enums.rbac import PermissionScope
from app.exceptions import NotFoundException
from app.rbac.decorators import (
    MenuConfig,
    action_read,
    permission_resource,
)
from app.repositories.ai import AICallLogRepository
from app.services.ai import CallLogService


@permission_resource(
    resource="ai_call_log",
    name="menu.admin.ai_call_log",
    scope=PermissionScope.ADMIN,
    parent_resource="ai_quota_mgmt",
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
    AI 调用日志控制器 / AI Call Log Controller

    提供调用日志查询和统计分析接口 / Provides call log query and statistics analysis endpoints
    """

    prefix = "/ai/call-logs"
    tags = [_("menu.tags.admin_ai_call_log")]

    def _register_routes(self) -> None:
        """注册路由 / Register routes"""
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
            查询 AI 调用日志列表 / Query AI call log list

            支持 JSON:API 风格筛选 / Supports JSON:API style filtering:
            - filter[tenant_id]: 企业 ID / Tenant ID
            - filter[model_id]: 模型 ID / Model ID
            - filter[status]: 调用状态 / Call status
            - filter[created_at][gte]: 创建时间 >= / Created at >=
            - filter[created_at][lte]: 创建时间 <= / Created at <=

            权限 / Permission: ai_call_log:list
            """
            service = CallLogService(db)
            items, total = await service.repo.query_list_with_names(
                spec,
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

        @router.get("/statistics", summary="获取调用统计信息")
        @action_read("action.ai_call_log.statistics")
        async def get_statistics(
            request: Request,
            db: DbSession,
            admin: ActiveAdmin,
            tenant_id: int | None = Query(None, description="企业 ID"),
            start_date: date | None = Query(None, description="开始日期"),
            end_date: date | None = Query(None, description="结束日期"),
            group_by: str | None = Query(None, description="分组维度: daily/model/user，缺省返回汇总"),
        ):
            """
            获取调用统计信息 / Get call statistics

            不传 group_by 时返回单个汇总 dict / Without group_by returns single summary dict;
            传 group_by=daily/model/user 时返回分组列表 / With group_by=daily/model/user returns grouped list

            权限 / Permission: ai_call_log:statistics
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
            tenant_id: int | None = Query(None, description="企业 ID"),
            start_date: date | None = Query(None, description="开始日期"),
            limit: int = Query(100, ge=1, le=1000, description="返回数量"),
        ):
            """
            获取失败的调用日志 / Get failed call logs

            权限 / Permission: ai_call_log:failed
            """
            service = CallLogService(db)
            logs = await service.get_failed_logs(
                tenant_id=tenant_id,
                start_date=start_date,
                limit=limit,
            )

            return success(data=logs, message=_("common.success"))

        @router.get("/export", summary="导出 AI 调用日志 CSV")
        @action_read("action.ai_call_log.list")
        async def export_call_logs(
            request: Request,
            db: DbSession,
            spec: QueryParams,
            admin: ActiveAdmin,
        ):
            """
            导出 AI 调用日志为 CSV（最多 10000 条） / Export AI call logs as CSV (max 10000 records)

            支持与列表相同的筛选参数 / Supports same filtering parameters as list

            权限 / Permission: ai_call_log:list
            """
            from app.core.csv_export import MAX_EXPORT_ROWS, csv_streaming_response

            spec.size = MAX_EXPORT_ROWS
            spec.page = 1
            service = CallLogService(db)
            items, _ = await service.query_list(spec)

            rows = []
            for item in items:
                row = item.to_dict() if hasattr(item, 'to_dict') else item
                if isinstance(row, dict):
                    rows.append(row)
                else:
                    rows.append({
                        "id": getattr(item, "id", ""),
                        "tenant_id": getattr(item, "tenant_id", ""),
                        "model_id": getattr(item, "model_id", ""),
                        "status": getattr(item, "status", ""),
                        "total_tokens": getattr(item, "total_tokens", ""),
                        "cost": getattr(item, "cost", ""),
                        "latency_ms": getattr(item, "latency_ms", ""),
                        "created_at": getattr(item, "created_at", "").isoformat() if hasattr(getattr(item, "created_at", ""), "isoformat") else str(getattr(item, "created_at", "")),
                    })

            columns = [
                {"field": "id", "header": "ID"},
                {"field": "tenant_id", "header": _("ai.callLog.tenantId")},
                {"field": "model_id", "header": _("ai.callLog.modelId")},
                {"field": "status", "header": _("ai.callLog.status")},
                {"field": "total_tokens", "header": _("ai.callLog.totalTokens")},
                {"field": "cost", "header": _("ai.callLog.cost")},
                {"field": "latency_ms", "header": _("ai.callLog.latency")},
                {"field": "created_at", "header": _("common.createdAt")},
            ]

            return csv_streaming_response(rows, columns, "ai_call_logs.csv")

        @router.get("/{log_id}", summary="获取调用日志详情")
        @action_read("action.ai_call_log.detail")
        async def get_call_log_detail(
            request: Request,
            db: DbSession,
            log_id: int,
            admin: ActiveAdmin,
        ):
            """
            获取调用日志详情（含完整请求和响应体） / Get call log details (with full request and response body)

            权限 / Permission: ai_call_log:detail
            """
            service = CallLogService(db)
            log = await service.get_by_id(log_id)

            if not log:
                raise NotFoundException(message=_("ai.error.call_log_not_found"))

            repo = AICallLogRepository(db)
            payload = (
                await repo.enrich_logs_to_dicts(
                    [log],
                    include_tenant_names=True,
                    include_caller_names=True,
                    include_payload=True,
                )
            )[0]
            return success(data=payload, message=_("common.success"))


# 导出路由器 / Export router
router = AdminAICallLogController.get_router()

__all__ = ["router", "AdminAICallLogController"]
