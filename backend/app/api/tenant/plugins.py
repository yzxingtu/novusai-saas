"""
企业端插件列表 API / Tenant Plugin List API

返回当前企业可用的已启用插件列表（根据 scope + tenant_assignments 过滤）。
Returns enabled plugin list available to current tenant (filtered by scope + tenant_assignments).
企业端不能管理插件（安装/卸载/启用/禁用），只能查看可用的插件。
Tenant cannot manage plugins (install/uninstall/enable/disable), only view available ones.
"""

from __future__ import annotations

from fastapi import APIRouter

from app.core.deps import ActiveTenantAdmin, DbSession
from app.core.logging import get_logger
from app.core.response import success
from app.rbac.decorators import auth_only

logger = get_logger(__name__)

router = APIRouter(prefix="/plugins", tags=["企业插件"])


@router.get("")
@auth_only
async def list_available_plugins(
    db: DbSession,
    tenant_admin: ActiveTenantAdmin,
):
    """
    获取当前企业可用的已启用插件列表 / Get enabled plugin list available to current tenant

    过滤规则（插件资源 scope = ResourceScopeEnum） / Filter rules (plugin resource scope):
    - all_tenants / global_shared → 所有企业可见 / visible to all tenants
    - selected_tenants / admin_and_selected_tenants → 仅 RTA 已分配当前企业的插件可见 / assigned via resource_tenant_assignments only
    - admin_only → 企业端不可见 / not visible on tenant side
    """
    from sqlalchemy import select

    from app.enums.plugin import PluginStatusEnum
    from app.models.system.plugin import Plugin
    from app.services.system.plugin_service import PluginService

    tenant_id = tenant_admin.tenant_id
    visible_names = await PluginService(db).get_tenant_visible_plugin_names(tenant_id)

    # 查询所有已启用的插件 / Query all enabled plugins
    result = await db.execute(
        select(Plugin).where(
            Plugin.status == PluginStatusEnum.ENABLED.value,
            Plugin.is_deleted.is_(False),
        )
    )
    all_enabled = list(result.scalars().all())

    visible_plugins = [
        plugin for plugin in all_enabled if plugin.name in visible_names
    ]

    items = []
    for p in visible_plugins:
        data = p.to_dict()
        # 脱敏配置 / Mask sensitive config
        manifest_data = data.get("manifest") or {}
        config_schema = manifest_data.get("config_schema")
        if config_schema and data.get("config"):
            from app.plugins.crypto import mask_plugin_config
            data["config"] = mask_plugin_config(data["config"], config_schema)
        items.append(data)

    return success(data={
        "items": items,
        "total": len(items),
        "page": 1,
        "page_size": len(items),
        "pages": 1,
    })


@router.get("/slots")
@auth_only
async def get_plugin_slots(
    db: DbSession,
    tenant_admin: ActiveTenantAdmin,
):
    """
    获取当前企业可见的已启用插件前端插槽数据。
    Get enabled plugin frontend slot data visible to current tenant.

    过滤规则 / Filter rules:
    - 资源 scope=admin_only 的插件插槽不返回 / admin_only plugin slots not returned
    - selected_tenants / admin_and_selected_tenants 的插件仅当 RTA 已分配当前企业时返回插槽 / assigned scopes need RTA row

    返回格式 / Return format:
    {
      "header_widgets": [...],
      "dashboard_widgets": [...],
      "settings_tabs": [...],
      "floating_panels": [...],
      "pages": [...],
      "notification_ui": [...]
    }
    """
    from app.plugins.registry import ExtensionRegistry
    from app.services.system.plugin_service import PluginService

    visible_names = await PluginService(db).get_tenant_visible_plugin_names(
        tenant_admin.tenant_id
    )

    registry = ExtensionRegistry.get_instance()
    grouped = registry.get_frontend_slots_grouped(scope="tenant")

    # 按可见插件名过滤各插槽 / Filter slots by visible plugin names
    filtered = {
        slot_key: [
            s for s in slots if s.get("plugin_name") in visible_names
        ]
        for slot_key, slots in grouped.items()
    }

    return success(data=filtered)
