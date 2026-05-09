"""Test type: structural.

中文: 覆盖退役后的独立操作/动作日志 API 暴露合同。
EN: Covers the retired standalone operation/action log API exposure contract.
中文: 仅使用文件存在性和聚合路由检查，不启动数据库或网络依赖。
EN: Uses file existence and aggregate router inspection only, with no database
or network dependencies.
"""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

RETIRED_ROUTE_MODULES = (
    ROOT / "app" / "api" / "admin" / "operation_logs.py",
    ROOT / "app" / "api" / "tenant" / "operation_logs.py",
    ROOT / "app" / "api" / "tenant" / "ai_action_logs.py",
)

RETIRED_ROUTE_PREFIXES = (
    "/operation-logs",
    "/ai/action-logs",
)

RETIRED_IMPORT_TOKENS = (
    "AdminOperationLogController",
    "TenantOperationLogController",
    "TenantAIActionLogController",
    "operation_logs_router",
    "ai_action_logs_router",
)


def _route_paths(router) -> set[str]:
    return {str(getattr(route, "path", "")) for route in router.routes}


def test_retired_log_route_modules_are_removed() -> None:
    for module_path in RETIRED_ROUTE_MODULES:
        assert not module_path.exists()


def test_admin_and_tenant_aggregate_routers_do_not_mount_retired_log_paths() -> None:
    from app.api.admin import admin_router
    from app.api.tenant import tenant_router

    for router in (admin_router, tenant_router):
        route_paths = _route_paths(router)
        for prefix in RETIRED_ROUTE_PREFIXES:
            assert all(not path.startswith(prefix) for path in route_paths)


def test_admin_and_tenant_api_packages_do_not_import_retired_log_controllers() -> None:
    source_by_file = {
        "admin": (ROOT / "app" / "api" / "admin" / "__init__.py").read_text(
            encoding="utf-8"
        ),
        "tenant": (ROOT / "app" / "api" / "tenant" / "__init__.py").read_text(
            encoding="utf-8"
        ),
    }

    for source in source_by_file.values():
        for token in RETIRED_IMPORT_TOKENS:
            assert token not in source


def test_retained_log_evidence_services_stay_importable() -> None:
    from app.models.ai.action_log import AIActionLog
    from app.models.system.operation_log import OperationLog
    from app.services.ai.action_log_service import (
        AIActionLogService,
        write_ai_action_log,
    )
    from app.services.ai.conversation_timeline_service import (
        ConversationTimelineService,
    )
    from app.services.system.dashboard_service_parts import activity
    from app.services.system.operation_log_service import (
        OperationLogService,
        create_log_async,
    )
    from app.services.system.trace_lookup_service import TraceLookupService

    assert OperationLog.__tablename__ == "operation_logs"
    assert AIActionLog.__tablename__ == "ai_action_logs"
    assert OperationLogService is not None
    assert create_log_async is not None
    assert TraceLookupService is not None
    assert activity._operation_log_identity_ref is not None
    assert AIActionLogService is not None
    assert write_ai_action_log is not None
    assert ConversationTimelineService is not None
