"""
Admin long-term memory debug API / 管理端长期记忆调试 API
"""

from fastapi import Request

from app.core.base_controller import GlobalController
from app.core.deps import ActiveAdmin, DbSession, QueryParams
from app.core.i18n import _
from app.core.response import paginated, success
from app.enums.rbac import PermissionScope
from app.exceptions import NotFoundException
from app.rbac.decorators import MenuConfig, action_read, permission_resource
from app.services.ai.long_term_memory_debug_service import (
    AdminMemoryRecordDebugService,
    AdminProfileSnapshotDebugService,
)


@permission_resource(
    resource="ai_long_term_memory_debug",
    name="menu.admin.ai_long_term_memory_debug",
    scope=PermissionScope.ADMIN,
    parent_resource="ai_call_log",
    menu=MenuConfig(
        icon="lucide:brain-circuit",
        path="/ai/debug/memory",
        component="ai/debug-memory/index",
        parent="ai_ops",
        sort_order=99,
        hidden=True,
    ),
)
class AdminLongTermMemoryDebugController(GlobalController):
    prefix = "/ai/long-term-memory"
    tags = [_("menu.tags.admin_ai_call_log")]

    def _register_routes(self) -> None:
        router = self.router

        @router.get("/records", summary="获取长期记忆记录列表")
        @action_read("action.ai_long_term_memory_debug.list")
        async def list_memory_records(
            request: Request,
            db: DbSession,
            spec: QueryParams,
            admin: ActiveAdmin,
        ):
            _ = request, admin
            service = AdminMemoryRecordDebugService(db)
            items, total = await service.query_list(spec=spec)
            return paginated(
                items=await service.serialize_records(items),
                total=total,
                page=spec.page,
                page_size=spec.size,
            )

        @router.get("/records/{record_id}", summary="获取长期记忆记录详情")
        @action_read("action.ai_long_term_memory_debug.detail")
        async def get_memory_record_detail(
            request: Request,
            db: DbSession,
            record_id: int,
            admin: ActiveAdmin,
        ):
            _ = request, admin
            service = AdminMemoryRecordDebugService(db)
            item = await service.get_by_id(record_id)
            if not item:
                raise NotFoundException(message="Memory record not found")
            return success(data=await service.serialize_record(item))

        @router.get("/profiles", summary="获取画像快照列表")
        @action_read("action.ai_long_term_memory_debug.list")
        async def list_profile_snapshots(
            request: Request,
            db: DbSession,
            spec: QueryParams,
            admin: ActiveAdmin,
        ):
            _ = request, admin
            service = AdminProfileSnapshotDebugService(db)
            items, total = await service.query_list(spec=spec)
            return paginated(
                items=await service.serialize_snapshots(items),
                total=total,
                page=spec.page,
                page_size=spec.size,
            )

        @router.get("/profiles/{snapshot_id}", summary="获取画像快照详情")
        @action_read("action.ai_long_term_memory_debug.detail")
        async def get_profile_snapshot_detail(
            request: Request,
            db: DbSession,
            snapshot_id: int,
            admin: ActiveAdmin,
        ):
            _ = request, admin
            service = AdminProfileSnapshotDebugService(db)
            item = await service.get_by_id(snapshot_id)
            if not item:
                raise NotFoundException(message="Profile snapshot not found")
            return success(data=await service.serialize_snapshot(item))


router = AdminLongTermMemoryDebugController.get_router()


__all__ = ["AdminLongTermMemoryDebugController", "router"]
