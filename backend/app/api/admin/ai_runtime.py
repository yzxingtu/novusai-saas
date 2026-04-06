"""
Unified AI runtime diagnostics API (Admin) / 统一 AI runtime 诊断 API（管理端）。
"""

from __future__ import annotations

from fastapi import Body, Query

from app.core.base_controller import GlobalController
from app.core.deps import ActiveAdmin, DbSession
from app.core.i18n import _
from app.core.response import success
from app.enums.rbac import PermissionScope
from app.rbac.decorators import action_create, action_read, permission_resource
from app.schemas.ai.runtime_diagnostics import RuntimeSmokeRequest
from app.schemas.ai.skill_registry import StarterPackSyncRequest
from app.services.ai.runtime_diagnostics_service import AIRuntimeDiagnosticsService


@permission_resource(
    resource="ai_runtime",
    name="menu.admin.ai_health",
    scope=PermissionScope.ADMIN,
    parent_resource="ai_infra",
)
class AdminAIRuntimeController(GlobalController):
    """Unified admin endpoints consumed by runtime diagnostics UI."""

    prefix = "/ai/runtime"
    tags = [_("menu.tags.admin_ai_health")]

    def _register_routes(self) -> None:
        router = self.router

        @router.get("/capabilities", summary="获取 AI runtime 能力清单")
        @action_read("action.ai_health.list")
        async def get_runtime_capabilities(
            db: DbSession,
            admin: ActiveAdmin,
            tenant_id: int | None = Query(None, description="企业 ID"),
            agent_id: int | None = Query(None, description="智能体 ID"),
            agent_code: str | None = Query(None, description="智能体代码"),
        ):
            del admin
            data = await AIRuntimeDiagnosticsService(db).get_capabilities(
                scope="admin",
                tenant_id=tenant_id,
                agent_id=agent_id,
                agent_code=agent_code,
            )
            return success(data=data, message=_("common.success"))

        @router.get("/doctor", summary="运行 AI runtime Doctor 预检")
        @action_read("action.ai_health.list")
        async def run_runtime_doctor(
            db: DbSession,
            admin: ActiveAdmin,
            tenant_id: int | None = Query(None, description="企业 ID"),
            agent_id: int | None = Query(None, description="智能体 ID"),
            agent_code: str | None = Query(None, description="智能体代码"),
        ):
            del admin
            data = await AIRuntimeDiagnosticsService(db).run_doctor(
                scope="admin",
                tenant_id=tenant_id,
                agent_id=agent_id,
                agent_code=agent_code,
            )
            return success(data=data, message=_("common.success"))

        @router.post("/smoke", summary="运行 Agent Capability Smoke")
        @action_create("action.ai_health.list")
        async def run_runtime_smoke(
            db: DbSession,
            admin: ActiveAdmin,
            body: RuntimeSmokeRequest = Body(default_factory=RuntimeSmokeRequest),
        ):
            del admin
            data = await AIRuntimeDiagnosticsService(db).run_smoke(
                scope="admin",
                tenant_id=body.tenant_id,
                agent_id=body.agent_id,
                agent_code=body.agent_code,
            )
            return success(data=data, message=_("common.success"))

        @router.get("/root-cause", summary="获取调用失败根因诊断")
        @action_read("action.ai_health.list")
        async def get_runtime_root_cause(
            db: DbSession,
            admin: ActiveAdmin,
            trace_id: str | None = Query(None, description="trace_id"),
            call_log_id: int | None = Query(None, description="调用日志 ID"),
            conversation_id: int | None = Query(None, description="对话 ID"),
            turn: int | None = Query(None, ge=1, description="对话轮次"),
        ):
            del admin
            data = await AIRuntimeDiagnosticsService(db).build_root_cause(
                scope="admin",
                trace_id=trace_id,
                call_log_id=call_log_id,
                conversation_id=conversation_id,
                turn=turn,
            )
            return success(data=data, message=_("common.success"))

        @router.post("/starter-pack/sync", summary="同步/安装官方 starter packs")
        @action_create("action.ai_health.list")
        async def sync_official_starter_pack(
            db: DbSession,
            admin: ActiveAdmin,
            body: StarterPackSyncRequest = Body(default_factory=StarterPackSyncRequest),
        ):
            del admin
            data = await AIRuntimeDiagnosticsService(db).sync_official_starter_pack(
                pack_keys=body.pack_keys,
                install_missing=body.install_missing,
                upgrade_existing=body.upgrade_existing,
                dry_run=body.dry_run,
            )
            return success(data=data, message=_("common.success"))


router = AdminAIRuntimeController.get_router()


__all__ = ["AdminAIRuntimeController", "router"]
