"""Plugin read models shared by admin, tenant, and config helpers."""

from __future__ import annotations

from collections.abc import Iterable
from typing import TYPE_CHECKING, Any

from sqlalchemy import select

from app.core.i18n import _
from app.enums.plugin import PluginStatusEnum
from app.enums.rbac import PermissionScope
from app.exceptions import BusinessException, NotFoundException
from app.models.auth.permission import Permission
from app.models.system.agent_assignment import SystemAgentAssignment
from app.models.system.plugin import Plugin
from app.plugins.dependencies import (
    build_plugin_dependency_states,
    normalize_plugin_dependencies,
)
from app.plugins.registry import ExtensionRegistry
from app.rbac.services import PermissionService

if TYPE_CHECKING:
    from app.services.system.plugin_service import PluginService


class PluginReadModelService:
    """Read-side helpers that keep plugin controllers thin."""

    def __init__(self, db):
        self._db = db
        self._plugin_service: PluginService | None = None

    def _get_plugin_service(self) -> PluginService:
        if self._plugin_service is None:
            from app.services.system.plugin_service import PluginService

            self._plugin_service = PluginService(self._db)
        return self._plugin_service

    async def _get_plugin_or_raise(self, plugin_id: int) -> Plugin:
        plugin = await self._get_plugin_service().get_by_id(plugin_id)
        if plugin is None:
            raise NotFoundException(
                message=_("plugin.error.not_found_by_id").format(
                    plugin_id=plugin_id,
                )
            )
        return plugin

    async def assert_name_available(self, plugin_name: str) -> None:
        """Raise if a plugin with the same name is already installed."""
        existing = await self._get_plugin_service().get_by_name(plugin_name)
        if existing is not None:
            raise BusinessException(
                message=_("plugin.error.already_installed").format(
                    plugin_name=plugin_name,
                )
            )

    async def build_menu_parent_options(self) -> dict[str, list[dict[str, Any]]]:
        """Build admin/tenant menu-parent trees for plugin menu mounting."""
        result = await self._db.execute(
            select(Permission)
            .where(
                Permission.type == "menu",
                Permission.is_enabled.is_(True),
                Permission.is_deleted.is_(False),
            )
            .order_by(Permission.sort_order)
        )
        all_menus = list(result.scalars().all())

        def _short_name(code: str) -> str:
            return code.rsplit(".", 1)[-1] if "." in code else code

        def _label(perm: Permission) -> str:
            name_key = perm.name or ""
            translated = PermissionService._translate_name(name_key)
            if translated and translated != name_key:
                return translated
            if "." in name_key:
                return name_key.split(".")[-1]
            return name_key

        def _has_menu_children(menus_subset: list[Permission], parent_id: int) -> bool:
            return any(
                menu.parent_id == parent_id and menu.type == "menu"
                for menu in menus_subset
            )

        def _build_tree(
            menus_subset: list[Permission],
            parent_id: int | None,
        ) -> list[dict[str, Any]]:
            nodes: list[dict[str, Any]] = []
            for menu in menus_subset:
                if menu.parent_id != parent_id:
                    continue
                children = _build_tree(menus_subset, menu.id)
                if not children and not _has_menu_children(menus_subset, menu.id):
                    continue
                node: dict[str, Any] = {
                    "value": _short_name(menu.code),
                    "label": _label(menu),
                    "icon": menu.icon,
                    "code": menu.code,
                }
                if children:
                    node["children"] = children
                nodes.append(node)
            return nodes

        admin_menus = [
            menu
            for menu in all_menus
            if menu.scope in (PermissionScope.ADMIN.value, PermissionScope.BOTH.value)
        ]
        tenant_menus = [
            menu
            for menu in all_menus
            if menu.scope in (PermissionScope.TENANT.value, PermissionScope.BOTH.value)
        ]

        return {
            "admin": _build_tree(admin_menus, None),
            "tenant": _build_tree(tenant_menus, None),
        }

    async def list_enabled_plugins_by_names(
        self,
        plugin_names: set[str],
    ) -> list[Plugin]:
        """Load enabled plugins by name, preserving stable name order."""
        if not plugin_names:
            return []

        requested_names = set(plugin_names)
        result = await self._db.execute(
            select(Plugin)
            .where(
                Plugin.name.in_(sorted(requested_names)),
                Plugin.status == PluginStatusEnum.ENABLED.value,
                Plugin.is_deleted.is_(False),
            )
            .order_by(Plugin.name)
        )
        plugins = [
            plugin
            for plugin in result.scalars().all()
            if getattr(plugin, "name", None) in requested_names
        ]
        plugins.sort(key=lambda item: getattr(item, "name", ""))
        return plugins

    async def list_tenant_visible_plugins(self, tenant_admin) -> list[Plugin]:
        """Load enabled plugins visible to both the tenant and current tenant admin."""
        from app.api.shared._plugin_slot_filter import (
            collect_plugin_names_from_grouped_slots,
            filter_grouped_plugin_slots_by_permission_codes,
        )

        visible_names = await self._get_plugin_service().get_tenant_visible_plugin_names(
            tenant_admin.tenant_id
        )
        permission_codes = await PermissionService(self._db).get_tenant_admin_permissions(
            tenant_admin
        )

        registry = ExtensionRegistry.get_instance()
        grouped = registry.get_frontend_slots_grouped(scope="tenant")
        grouped = {
            slot_key: [
                slot for slot in slots if slot.get("plugin_name") in visible_names
            ]
            for slot_key, slots in grouped.items()
        }
        grouped = filter_grouped_plugin_slots_by_permission_codes(
            grouped,
            permission_codes,
        )
        current_user_visible_names = collect_plugin_names_from_grouped_slots(grouped)
        return await self.list_enabled_plugins_by_names(
            visible_names & current_user_visible_names
        )

    async def build_admin_visible_slots(self, admin) -> dict[str, list[dict[str, Any]]]:
        """Build admin plugin slots filtered by runtime gate and permission codes."""
        from app.api.shared._plugin_slot_filter import (
            filter_grouped_plugin_slots_by_permission_codes,
        )
        from app.plugins.runtime_gate import evaluate_plugin_runtime_gate

        registry = ExtensionRegistry.get_instance()
        grouped = registry.get_frontend_slots_grouped(scope="admin")
        permission_codes = await PermissionService(self._db).get_admin_permissions(admin)

        plugin_names = {
            slot.get("plugin_name")
            for slots in grouped.values()
            for slot in slots
            if slot.get("plugin_name")
        }
        allowed_names: set[str] = set()
        for plugin_name in plugin_names:
            gate = await evaluate_plugin_runtime_gate(
                self._db,
                plugin_name,
                tenant_id=None,
                require_enabled=True,
                enforce_scope=False,
            )
            if gate.allowed:
                allowed_names.add(plugin_name)

        filtered = {
            slot_key: [
                slot for slot in slots if slot.get("plugin_name") in allowed_names
            ]
            for slot_key, slots in grouped.items()
        }
        return filter_grouped_plugin_slots_by_permission_codes(
            filtered,
            permission_codes,
        )

    async def build_tenant_visible_slots(
        self,
        tenant_admin,
    ) -> dict[str, list[dict[str, Any]]]:
        """Build tenant plugin slots filtered by tenant visibility and permission codes."""
        from app.api.shared._plugin_slot_filter import (
            filter_grouped_plugin_slots_by_permission_codes,
        )

        visible_names = await self._get_plugin_service().get_tenant_visible_plugin_names(
            tenant_admin.tenant_id
        )
        permission_codes = await PermissionService(self._db).get_tenant_admin_permissions(
            tenant_admin
        )

        registry = ExtensionRegistry.get_instance()
        grouped = registry.get_frontend_slots_grouped(scope="tenant")
        filtered = {
            slot_key: [
                slot for slot in slots if slot.get("plugin_name") in visible_names
            ]
            for slot_key, slots in grouped.items()
        }
        return filter_grouped_plugin_slots_by_permission_codes(
            filtered,
            permission_codes,
        )

    @staticmethod
    def _mask_sensitive_config(data: dict[str, Any]) -> dict[str, Any]:
        """Mask secret config fields based on plugin config schema."""
        from app.plugins.crypto import mask_plugin_config

        manifest_data = data.get("manifest") or {}
        config_schema = manifest_data.get("config_schema")
        if config_schema and data.get("config"):
            data["config"] = mask_plugin_config(data["config"], config_schema)
        return data

    async def build_admin_plugin_list(
        self,
        query,
    ) -> tuple[list[dict[str, Any]], int]:
        """Build admin plugin list payload with dependency + recovery states."""
        service = self._get_plugin_service()
        items, total = await service.query_list(query)
        result_items: list[dict[str, Any]] = []
        for item in items:
            data = self._mask_sensitive_config(item.to_dict())
            dependency_status = await service.get_dependency_status(item)
            data["dependency_status"] = dependency_status
            data["recovery_state"] = service.get_recovery_state(
                item,
                dependency_status=dependency_status,
            )
            result_items.append(data)
        return result_items, total

    async def build_admin_plugin_detail(
        self,
        plugin_id: int,
        *,
        locale: str,
    ) -> dict[str, Any]:
        """Build admin plugin detail payload with README and dependency status."""
        service = self._get_plugin_service()
        plugin = await self._get_plugin_or_raise(plugin_id)

        data = self._mask_sensitive_config(plugin.to_dict())
        dependency_status = await service.get_dependency_status(plugin)
        data["dependency_status"] = dependency_status
        data["recovery_state"] = service.get_recovery_state(
            plugin,
            dependency_status=dependency_status,
        )
        data["readme"] = await service.get_readme(plugin_id, locale=locale)
        return data

    async def list_tenant_visible_plugin_items(self, tenant_admin) -> list[dict[str, Any]]:
        """Build masked tenant-visible plugin list items."""
        plugins = await self.list_tenant_visible_plugins(tenant_admin)
        return [self._mask_sensitive_config(plugin.to_dict()) for plugin in plugins]

    async def list_ai_feature_assignments(
        self,
        plugin_name: str,
    ) -> list[SystemAgentAssignment]:
        """Load plugin AI feature assignments for the admin plugin detail page."""
        result = await self._db.execute(
            select(SystemAgentAssignment).where(
                SystemAgentAssignment.feature_code.like(f"plugin.{plugin_name}.%"),
                SystemAgentAssignment.is_deleted.is_(False),
            )
        )
        return list(result.scalars().all())

    async def list_ai_feature_assignment_items(
        self,
        plugin_id: int,
    ) -> list[dict[str, Any]]:
        """Build plugin AI feature assignment payloads by plugin id."""
        plugin = await self._get_plugin_or_raise(plugin_id)
        assignments = await self.list_ai_feature_assignments(plugin.name)
        return [assignment.to_dict() for assignment in assignments]

    async def get_known_storage_drivers(self) -> list[dict[str, Any]]:
        """Load declared plugin storage drivers for config pages."""
        result = await self._db.execute(
            select(Plugin).where(
                Plugin.is_deleted.is_(False),
            )
        )
        plugins = result.scalars().all()

        drivers: list[dict[str, Any]] = []
        for plugin in plugins:
            manifest = plugin.manifest or {}
            extensions = manifest.get("extensions", {})
            for storage_driver in extensions.get("storage_drivers", []):
                code = storage_driver.get("code", "")
                if not code:
                    continue
                display = storage_driver.get("display_name", {})
                if isinstance(display, dict):
                    display_str = display.get("zh-CN") or display.get("en") or code
                else:
                    display_str = str(display) if display else code
                drivers.append(
                    {
                        "name": code,
                        "display_name": display_str,
                        "plugin_name": plugin.name,
                        "plugin_status": plugin.status,
                    }
                )
        return drivers

    async def collect_dependency_states(
        self,
        manifest_or_data: object,
        *,
        require_enabled: bool,
    ) -> list[dict[str, object]]:
        """Collect normalized plugin dependency runtime states."""
        requirements = normalize_plugin_dependencies(manifest_or_data)
        if not requirements:
            return []

        plugin_names = sorted({item.plugin for item in requirements})
        result = await self._db.execute(
            select(Plugin.name, Plugin.version, Plugin.status).where(
                Plugin.name.in_(plugin_names),
                Plugin.is_deleted.is_(False),
            )
        )
        plugin_rows = {
            row[0]: {
                "name": row[0],
                "status": row[2],
                "version": row[1],
            }
            for row in result.all()
        }
        return [
            state.to_dict()
            for state in build_plugin_dependency_states(
                requirements,
                plugin_rows,
                require_enabled=require_enabled,
            )
        ]

    async def list_dependents(
        self,
        plugin_name: str,
        *,
        statuses: Iterable[str] | None = None,
    ) -> list[dict[str, object]]:
        """List plugins that depend on the specified plugin."""
        filters = [
            Plugin.name != plugin_name,
            Plugin.is_deleted.is_(False),
        ]
        normalized_statuses = sorted({str(status) for status in statuses or []})
        if normalized_statuses:
            filters.append(Plugin.status.in_(normalized_statuses))

        result = await self._db.execute(
            select(
                Plugin.id,
                Plugin.name,
                Plugin.version,
                Plugin.status,
                Plugin.manifest,
            ).where(*filters)
        )
        dependents: list[dict[str, object]] = []
        for plugin_id, name, version, status, manifest_data in result.all():
            try:
                requirements = normalize_plugin_dependencies(manifest_data)
            except Exception:
                continue

            for requirement in requirements:
                if requirement.plugin != plugin_name:
                    continue
                dependents.append(
                    {
                        "plugin_id": plugin_id,
                        "plugin": name,
                        "version": version,
                        "status": status,
                        "required_version": requirement.version,
                        "source": requirement.source,
                    }
                )
        return dependents

    async def list_dependents_by_plugin_id(
        self,
        plugin_id: int,
        *,
        statuses: Iterable[str] | None = None,
    ) -> list[dict[str, object]]:
        """Resolve plugin name by id and list its dependents."""
        result = await self._db.execute(
            select(Plugin.name).where(
                Plugin.id == plugin_id,
                Plugin.is_deleted.is_(False),
            )
        )
        plugin_name = result.scalar_one_or_none()
        if not plugin_name:
            return []
        return await self.list_dependents(plugin_name, statuses=statuses)

    async def list_dependencies_by_plugin_id(
        self,
        plugin_id: int,
        *,
        require_enabled: bool,
    ) -> list[dict[str, object]]:
        """Resolve plugin by id and collect dependency states."""
        result = await self._db.execute(
            select(Plugin.manifest).where(
                Plugin.id == plugin_id,
                Plugin.is_deleted.is_(False),
            )
        )
        manifest_data = result.scalar_one_or_none()
        if not manifest_data or not isinstance(manifest_data, dict):
            return []
        return await self.collect_dependency_states(
            manifest_data,
            require_enabled=require_enabled,
        )

    async def list_plugin_versions(self, plugin_id: int) -> list[dict[str, Any]]:
        """List plugin versions for admin version management."""
        await self._get_plugin_or_raise(plugin_id)

        from app.plugins.version_manager import VersionManager

        manager = VersionManager(self._db)
        return await manager.list_versions(plugin_id)

    async def list_tenant_assignment_items(
        self,
        plugin_id: int,
    ) -> list[dict[str, Any]]:
        """List tenant assignments for the plugin."""
        plugin = await self._get_plugin_or_raise(plugin_id)
        assignments = await self._get_plugin_service().repo.get_tenant_assignments(
            plugin.id
        )
        return [assignment.to_dict() for assignment in assignments]

    async def get_plugin_license_status(self, plugin_id: int) -> dict[str, Any]:
        """Load plugin license status payload for admin surfaces."""
        await self._get_plugin_or_raise(plugin_id)

        from app.plugins.license import get_license_status_by_id

        return await get_license_status_by_id(plugin_id, self._db)

    async def list_plugin_backups(self, plugin_id: int) -> list[dict[str, Any]]:
        """List backup snapshots for the plugin."""
        import asyncio as _asyncio

        from app.plugins.backup import list_backups as _list

        plugin = await self._get_plugin_or_raise(plugin_id)
        return await _asyncio.to_thread(_list, plugin.name)

    async def get_plugin_health_status(self, plugin_id: int) -> dict[str, Any]:
        """Load runtime health status for the plugin."""
        from app.plugins.health import PluginHealthMonitor

        plugin = await self._get_plugin_or_raise(plugin_id)
        monitor = PluginHealthMonitor(self._db)
        return await monitor.get_health_status(plugin.name)

__all__ = ["PluginReadModelService"]
