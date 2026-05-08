"""
AI 供应商健康状态 API (Admin) / AI Provider Health API (Admin)

提供供应商健康检查状态查询接口
Provides provider health check status query endpoints.
"""

import importlib
from typing import Any

from fastapi import Body, Query, Request
from sqlalchemy import select

from app.ai.failover import FailoverService
from app.core.base_controller import GlobalController
from app.core.deps import ActiveAdmin, DbSession
from app.core.i18n import _
from app.core.response import success
from app.enums.rbac import PermissionScope
from app.exceptions import ServiceUnavailableException
from app.models.ai.provider import AIProvider
from app.rbac.decorators import (
    MenuConfig,
    action_create,
    action_read,
    permission_resource,
)
from app.schemas.ai.runtime_diagnostics import RuntimeSmokeRequest


def _is_missing_module(exc: ModuleNotFoundError, module_path: str) -> bool:
    return bool(exc.name) and (
        exc.name == module_path or exc.name.startswith(f"{module_path}.")
    )


def _resolve_runtime_diagnostics_service(db: DbSession) -> Any:
    candidates = [
        ("app.services.ai.runtime_diagnostics_service", "AIRuntimeDiagnosticsService"),
        ("app.services.ai.runtime_diagnostics", "AIRuntimeDiagnosticsService"),
        ("app.services.ai.runtime_service", "AIRuntimeDiagnosticsService"),
    ]
    for module_path, class_name in candidates:
        try:
            module = importlib.import_module(module_path)
        except ModuleNotFoundError as exc:
            if _is_missing_module(exc, module_path):
                continue
            raise
        service_cls = getattr(module, class_name, None)
        if service_cls is not None:
            return service_cls(db)
    raise ServiceUnavailableException(
        message=_("ai.runtime.error.diagnostics_service_unavailable")
    )


@permission_resource(
    resource="ai_health",
    name="menu.admin.ai_health",
    scope=PermissionScope.ADMIN,
    parent_resource="ai_infra",
    menu=MenuConfig(
        icon="lucide:heart-pulse",
        path="/ai/monitor/health",
        component="ai/health/index",
        parent="ai_infra",
        sort_order=40,
    ),
)
class AdminAIHealthController(GlobalController):
    """
    AI 供应商健康状态控制器 / AI Provider Health Status Controller

    提供供应商健康检查状态查询 / Provides provider health check status queries
    """

    prefix = "/ai/health"
    tags = [_("menu.tags.admin_ai_health")]

    def _register_routes(self) -> None:
        """注册路由 / Register routes"""
        router = self.router

        @router.get("", summary="获取所有供应商健康状态")
        @action_read("action.ai_health.list")
        async def get_all_health(
            request: Request,
            db: DbSession,
            admin: ActiveAdmin,
        ):
            """
            获取所有供应商当前健康状态（从 Redis 读取） / Get all provider current health status (from Redis)

            权限 / Permission: ai_health:list
            """
            statuses = await FailoverService.get_all_provider_health()

            # Enrich with provider icon / 补充供应商图标
            pid_set = {s.get("provider_id") for s in statuses if s.get("provider_id")}
            icon_map: dict[int, str | None] = {}
            if pid_set:
                rows = (
                    await db.execute(
                        select(AIProvider.id, AIProvider.icon).where(
                            AIProvider.id.in_(pid_set)
                        )
                    )
                ).all()
                icon_map = {r.id: r.icon for r in rows}
            for s in statuses:
                s["provider_icon"] = icon_map.get(s.get("provider_id"))

            return success(data=statuses, message=_("common.success"))

        @router.get("/{provider_id}/history", summary="获取供应商健康检查历史")
        @action_read("action.ai_health.history")
        async def get_health_history(
            request: Request,
            db: DbSession,
            provider_id: int,
            admin: ActiveAdmin,
            limit: int = Query(
                60,
                ge=1,
                le=288,
                description="返回历史采样条数，默认 60 条",
            ),
        ):
            """
            获取供应商最近 24h 健康检查记录 / Get provider last 24h health check history

            权限 / Permission: ai_health:history
            """
            history = await FailoverService.get_provider_health_history(
                provider_id=provider_id,
                limit=limit,
            )
            return success(data=history, message=_("common.success"))

        @router.get("/runtime/capabilities", summary="获取 AI runtime 能力清单")
        @action_read("action.ai_health.list")
        async def get_runtime_capabilities(
            request: Request,
            db: DbSession,
            admin: ActiveAdmin,
            tenant_id: int | None = Query(None, description="企业 ID"),
            agent_id: int | None = Query(None, description="智能体 ID"),
            agent_code: str | None = Query(None, description="智能体代码"),
        ):
            _request = request
            _admin = admin
            service = _resolve_runtime_diagnostics_service(db)
            data = await service.get_capabilities(
                scope="admin",
                tenant_id=tenant_id,
                agent_id=agent_id,
                agent_code=agent_code,
            )
            return success(data=data, message=_("common.success"))

        @router.get("/runtime/doctor", summary="运行 AI runtime Doctor 预检")
        @action_read("action.ai_health.list")
        async def run_runtime_doctor(
            request: Request,
            db: DbSession,
            admin: ActiveAdmin,
            tenant_id: int | None = Query(None, description="企业 ID"),
            agent_id: int | None = Query(None, description="智能体 ID"),
            agent_code: str | None = Query(None, description="智能体代码"),
        ):
            _request = request
            _admin = admin
            service = _resolve_runtime_diagnostics_service(db)
            report = await service.run_doctor(
                scope="admin",
                tenant_id=tenant_id,
                agent_id=agent_id,
                agent_code=agent_code,
            )
            return success(data=report, message=_("common.success"))

        @router.post("/runtime/smoke", summary="运行 Agent Capability Smoke")
        @action_create("action.ai_health.list")
        async def run_runtime_smoke(
            request: Request,
            db: DbSession,
            admin: ActiveAdmin,
            body: RuntimeSmokeRequest = Body(default_factory=RuntimeSmokeRequest),
        ):
            _request = request
            _admin = admin
            service = _resolve_runtime_diagnostics_service(db)
            report = await service.run_smoke(
                scope="admin",
                tenant_id=body.tenant_id,
                agent_id=body.agent_id,
                agent_code=body.agent_code,
            )
            return success(data=report, message=_("common.success"))


# 导出路由器 / Export router
router = AdminAIHealthController.get_router()

__all__ = ["router", "AdminAIHealthController"]
