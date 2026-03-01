"""
租户端插件列表 API

返回当前租户可用的已启用插件列表（根据 scope + tenant_assignments 过滤）。
租户端不能管理插件（安装/卸载/启用/禁用），只能查看可用的插件。
"""

from __future__ import annotations

from fastapi import APIRouter

from app.core.deps import DbSession, ActiveTenantAdmin
from app.core.logging import get_logger
from app.core.response import success
from app.rbac.decorators import auth_only

logger = get_logger(__name__)

router = APIRouter(prefix="/plugins", tags=["租户插件"])


@router.get("")
@auth_only
async def list_available_plugins(
    db: DbSession,
    tenant_admin: ActiveTenantAdmin,
):
    """
    获取当前租户可用的已启用插件列表

    过滤规则（根据 scope）：
    - all_tenants → 所有租户可见
    - admin_and_all → 所有租户可见
    - assigned_tenants → 仅分配了当前租户的插件可见
    - admin_and_assigned → 仅分配了当前租户的插件可见
    - admin_only → 租户端不可见
    """
    from sqlalchemy import select

    from app.enums.plugin import PluginStatusEnum
    from app.models.system.plugin import Plugin
    from app.models.system.resource_tenant_assignment import ResourceTenantAssignment

    tenant_id = tenant_admin.tenant_id

    # 查询所有已启用的插件
    result = await db.execute(
        select(Plugin).where(
            Plugin.status == PluginStatusEnum.ENABLED.value,
            Plugin.is_deleted.is_(False),
        )
    )
    all_enabled = list(result.scalars().all())

    # 查询当前租户被分配的插件 ID
    assignment_result = await db.execute(
        select(ResourceTenantAssignment.resource_id).where(
            ResourceTenantAssignment.resource_type == "plugin",
            ResourceTenantAssignment.tenant_id == tenant_id,
            ResourceTenantAssignment.is_active.is_(True),
        )
    )
    assigned_plugin_ids = set(assignment_result.scalars().all())

    # 根据 scope 过滤
    TENANT_ALL_SCOPES = {"all_tenants", "admin_and_all"}
    TENANT_ASSIGNED_SCOPES = {"assigned_tenants", "admin_and_assigned"}

    visible_plugins = []
    for plugin in all_enabled:
        scope = plugin.scope
        if scope in TENANT_ALL_SCOPES:
            visible_plugins.append(plugin)
        elif scope in TENANT_ASSIGNED_SCOPES:
            if plugin.id in assigned_plugin_ids:
                visible_plugins.append(plugin)
        # admin_only → 不返回

    items = []
    for p in visible_plugins:
        data = p.to_dict()
        # 脱敏配置
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
    获取当前租户可见的已启用插件前端插槽数据。

    过滤规则：
    - admin_only scope 的插槽不返回
    - assigned_tenants / admin_and_assigned scope 的插槽仅当租户被分配时返回

    返回格式：
    {
      "header_widgets": [...],
      "dashboard_widgets": [...],
      "settings_tabs": [...],
      "floating_panels": [...],
      "standalone_pages": [...],
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

    # 按可见插件名过滤各插槽
    filtered = {
        slot_key: [
            s for s in slots if s.get("plugin_name") in visible_names
        ]
        for slot_key, slots in grouped.items()
    }

    return success(data=filtered)
