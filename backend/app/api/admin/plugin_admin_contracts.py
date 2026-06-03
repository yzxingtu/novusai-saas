"""Admin plugin controller contracts and helper seams."""

from __future__ import annotations

from typing import TYPE_CHECKING

from pydantic import BaseModel as PydanticBaseModel
from pydantic import ConfigDict, Field

from app.core.deps import ActiveAdmin, DbSession, QueryParams
from app.core.i18n import _
from app.core.response import paginated, success
from app.exceptions import NotFoundException
from app.rbac.decorators import action_read
from app.services.system.plugin_read_model_service import PluginReadModelService
from app.services.system.plugin_runtime_audit_service import PluginRuntimeAuditService

if TYPE_CHECKING:
    from app.core.base_controller import GlobalController


def resolve_plugin_audit_service(db: DbSession) -> PluginRuntimeAuditService:
    return PluginRuntimeAuditService(db)


async def build_plugin_runtime_audit_payload(
    service: PluginRuntimeAuditService,
    *,
    plugin_id: int | None = None,
    tenant_id: int | None = None,
) -> dict:
    reports = await service.list_plugin_audit_reports(
        plugin_id=plugin_id,
        tenant_id=tenant_id,
        limit=1 if plugin_id is not None else 50,
    )
    if plugin_id is not None:
        if not reports:
            raise NotFoundException(
                message=_("plugin.error.not_found_by_id").format(plugin_id=plugin_id)
            )
        return reports[0].model_dump()
    return {
        "items": [report.model_dump() for report in reports],
        "total": len(reports),
    }


class PluginConfigBody(PydanticBaseModel):
    config: dict = Field(default_factory=dict, max_length=65536)


class PluginInstallConfirmBody(PydanticBaseModel):
    config: dict = Field(default_factory=dict, max_length=65536)
    preview_token: str = Field(default="", max_length=4096)


class PluginCapabilitiesBody(PydanticBaseModel):
    capabilities: list[str] = Field(default_factory=list)


class PluginAssignTenantsBody(PydanticBaseModel):
    tenant_ids: list[int] = Field(default_factory=list, max_length=500)


class PluginActivateLicenseBody(PydanticBaseModel):
    license_key: str = Field(default="", max_length=500)


class PluginRollbackBody(PydanticBaseModel):
    target_version: str = Field(
        default="",
        pattern=r"^\d+\.\d+\.\d+(?:-[\w.]+)?(?:\+[\w.]+)?$",
    )


class MenuOverrideItem(PydanticBaseModel):
    """Single menu override contract."""

    name: str = Field(..., max_length=100, description="Menu name from plugin.yaml")
    parent: str = Field(
        ...,
        max_length=100,
        pattern=r"^[a-z0-9_-]+$",
        description="Admin parent menu code (e.g. system_mgmt)",
    )
    tenant_parent: str | None = Field(
        None,
        max_length=100,
        pattern=r"^[a-z0-9_-]+$",
        description="Tenant parent menu code (when menu scope is both)",
    )


class PluginMenuConfigBody(PydanticBaseModel):
    """Admin-configurable menu placement overrides."""

    menu_overrides: list[MenuOverrideItem] = Field(default_factory=list)


class PluginEnableBody(PydanticBaseModel):
    """Optional enable-body contract with menu configuration."""

    menu_overrides: list[MenuOverrideItem] = Field(default_factory=list)


class PluginDependencyActionBody(PydanticBaseModel):
    """Install/uninstall dependency switches."""

    model_config = ConfigDict(extra="forbid")

    python: bool = True


def build_menu_overrides_payload(
    menu_overrides: list[MenuOverrideItem],
) -> dict[str, dict[str, str]]:
    payload: dict[str, dict[str, str]] = {}
    for item in menu_overrides:
        if item.tenant_parent:
            payload[item.name] = {
                "parent": item.parent,
                "tenant_parent": item.tenant_parent,
            }
        else:
            payload[item.name] = {"parent": item.parent}
    return payload


def register_plugin_admin_read_routes(controller: GlobalController) -> None:
    """Register read-only admin plugin routes that delegate into services."""

    @controller.router.get("/slots")
    @action_read("action.plugin.list")
    async def get_plugin_slots(db: DbSession, admin: ActiveAdmin):
        return success(
            data=await PluginReadModelService(db).build_admin_visible_slots(admin)
        )

    @controller.router.get("/updates")
    @action_read("action.plugin.list")
    async def check_updates(db: DbSession, admin: ActiveAdmin):
        _ = admin
        from app.plugins.update_checker import check_updates as _check

        updates = await _check(db)
        return success(data=updates)

    @controller.router.get("/menu-parent-options")
    @action_read("action.plugin.list")
    async def get_menu_parent_options(db: DbSession, admin: ActiveAdmin):
        _ = admin
        return success(
            data=await PluginReadModelService(db).build_menu_parent_options()
        )

    @controller.router.get("/runtime/audit")
    @action_read("action.plugin.health")
    async def plugin_runtime_audit(
        db: DbSession,
        admin: ActiveAdmin,
        plugin_id: int | None = None,
        tenant_id: int | None = None,
    ):
        _ = admin
        service = resolve_plugin_audit_service(db)
        report = await build_plugin_runtime_audit_payload(
            service,
            plugin_id=plugin_id,
            tenant_id=tenant_id,
        )
        return success(data=report)

    @controller.router.get("")
    @action_read("action.plugin.list")
    async def list_plugins(db: DbSession, admin: ActiveAdmin, query: QueryParams):
        _ = admin
        result_items, total = await PluginReadModelService(db).build_admin_plugin_list(
            query
        )
        return paginated(
            items=result_items,
            total=total,
            page=query.page,
            page_size=query.size,
        )

    @controller.router.get("/{plugin_id}")
    @action_read("action.plugin.detail")
    async def get_plugin(
        plugin_id: int,
        db: DbSession,
        admin: ActiveAdmin,
        locale: str = "zh-CN",
    ):
        _ = admin
        return success(
            data=await PluginReadModelService(db).build_admin_plugin_detail(
                plugin_id,
                locale=locale,
            )
        )

    @controller.router.get("/{plugin_id}/versions")
    @action_read("action.plugin.versions")
    async def list_versions(plugin_id: int, db: DbSession, admin: ActiveAdmin):
        _ = admin
        return success(
            data=await PluginReadModelService(db).list_plugin_versions(plugin_id)
        )

    @controller.router.get("/{plugin_id}/tenants")
    @action_read("action.plugin.tenants")
    async def list_tenant_assignments(
        plugin_id: int,
        db: DbSession,
        admin: ActiveAdmin,
    ):
        _ = admin
        return success(
            data=await PluginReadModelService(db).list_tenant_assignment_items(
                plugin_id
            )
        )

    @controller.router.get("/{plugin_id}/license")
    @action_read("action.plugin.view_license")
    async def get_license_status(
        plugin_id: int,
        db: DbSession,
        admin: ActiveAdmin,
    ):
        _ = admin
        return success(
            data=await PluginReadModelService(db).get_plugin_license_status(plugin_id)
        )

    @controller.router.get("/{plugin_id}/ai-features")
    @action_read("action.plugin.ai_features")
    async def list_ai_features(plugin_id: int, db: DbSession, admin: ActiveAdmin):
        _ = admin
        return success(
            data=await PluginReadModelService(db).list_ai_feature_assignment_items(
                plugin_id
            )
        )

    @controller.router.get("/{plugin_id}/backups")
    @action_read("action.plugin.read")
    async def list_backups(plugin_id: int, db: DbSession, admin: ActiveAdmin):
        _ = admin
        return success(
            data=await PluginReadModelService(db).list_plugin_backups(plugin_id)
        )

    @controller.router.get("/{plugin_id}/health")
    @action_read("action.plugin.health")
    async def get_health(plugin_id: int, db: DbSession, admin: ActiveAdmin):
        _ = admin
        return success(
            data=await PluginReadModelService(db).get_plugin_health_status(plugin_id)
        )


__all__ = [
    "MenuOverrideItem",
    "PluginActivateLicenseBody",
    "PluginAssignTenantsBody",
    "PluginCapabilitiesBody",
    "PluginConfigBody",
    "PluginDependencyActionBody",
    "PluginEnableBody",
    "PluginInstallConfirmBody",
    "PluginMenuConfigBody",
    "PluginRollbackBody",
    "build_plugin_runtime_audit_payload",
    "build_menu_overrides_payload",
    "register_plugin_admin_read_routes",
    "resolve_plugin_audit_service",
]
