"""
Admin plugin write-side workflow service. / 管理端插件写侧工作流服务。

Owns controller-local orchestration so admin plugin routes stay transport-only.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from app.core.i18n import _
from app.exceptions.base import BusinessException
from app.plugins.lifecycle import PluginLifecycle
from app.services.system.plugin_cleanup_service import PluginCleanupService
from app.services.system.plugin_service import PluginService

if TYPE_CHECKING:
    from fastapi import UploadFile


class PluginAdminWorkflowService:
    """Own admin-side plugin write workflows outside the controller."""

    def __init__(self, db) -> None:
        self._db = db
        self._plugin_service = PluginService(db)
        self._cleanup_service = PluginCleanupService(db)
        self._lifecycle = PluginLifecycle(db)

    @staticmethod
    def _build_menu_overrides_payload(
        menu_overrides: list[Any] | None,
    ) -> dict[str, dict[str, str]]:
        payload: dict[str, dict[str, str]] = {}
        for item in menu_overrides or []:
            if hasattr(item, "model_dump"):
                data = item.model_dump(exclude_none=True)
            elif isinstance(item, dict):
                data = {key: value for key, value in item.items() if value is not None}
            else:
                data = {
                    "name": item.name,
                    "parent": item.parent,
                }
                tenant_parent = (
                    item.tenant_parent if hasattr(item, "tenant_parent") else None
                )
                if tenant_parent is not None:
                    data["tenant_parent"] = tenant_parent

            payload[str(data["name"])] = {
                "parent": str(data["parent"]),
            }
            tenant_parent = data.get("tenant_parent")
            if tenant_parent:
                payload[str(data["name"])]["tenant_parent"] = str(tenant_parent)
        return payload

    @staticmethod
    def _resolve_plugin_display_name(plugin: Any, plugin_id: int) -> str:
        if plugin is None:
            return f"plugin#{plugin_id}"
        display_name = plugin.display_name if hasattr(plugin, "display_name") else None
        if display_name:
            return display_name
        return plugin.name if hasattr(plugin, "name") else f"plugin#{plugin_id}"

    async def enable_plugin(
        self,
        *,
        plugin_id: int,
        admin_id: int,
        menu_overrides: list[Any] | None = None,
    ) -> None:
        if menu_overrides:
            await self._lifecycle.update_menu_overrides(
                plugin_id,
                menu_overrides=self._build_menu_overrides_payload(menu_overrides),
                refresh_runtime=False,
            )

        await self._plugin_service.enable_plugin(plugin_id, operator_id=admin_id)
        plugin = await self._plugin_service.get_by_id(plugin_id)

        from app.services.common.notification_service import notify

        await notify(
            self._db,
            "biz.plugin_enabled",
            [("admin", admin_id)],
            data={"plugin_name": self._resolve_plugin_display_name(plugin, plugin_id)},
        )

    async def disable_plugin(
        self,
        *,
        plugin_id: int,
        admin_id: int,
        force: bool = False,
    ) -> None:
        plugin = await self._plugin_service.get_by_id(plugin_id)
        plugin_display = self._resolve_plugin_display_name(plugin, plugin_id)
        await self._plugin_service.disable_plugin(
            plugin_id,
            force=force,
            operator_id=admin_id,
        )

        from app.services.common.notification_service import notify

        await notify(
            self._db,
            "biz.plugin_disabled",
            [("admin", admin_id)],
            data={"plugin_name": plugin_display},
        )

    async def update_menu_config(
        self,
        *,
        plugin_id: int,
        menu_overrides: list[Any] | None,
    ) -> None:
        await self._lifecycle.update_menu_overrides(
            plugin_id,
            menu_overrides=self._build_menu_overrides_payload(menu_overrides),
            refresh_runtime=True,
        )

    async def uninstall_plugin(
        self,
        *,
        plugin_id: int,
        admin_id: int,
        confirm_data_delete: bool = False,
        cleanup_dependencies: bool = False,
    ) -> str | None:
        plugin = await self._plugin_service.get_by_id(plugin_id)
        if plugin is None:
            return _("plugin.deleted_already").format(plugin_id=plugin_id)

        plugin_display = self._resolve_plugin_display_name(plugin, plugin_id)
        plugin_version = getattr(plugin, "version", None) or "1.0.0"
        await self._plugin_service.uninstall_plugin(
            plugin_id,
            confirm_data_delete,
            cleanup_dependencies=cleanup_dependencies,
            operator_id=admin_id,
        )

        from app.services.common.notification_service import notify

        await notify(
            self._db,
            "biz.plugin_uninstalled",
            [("admin", admin_id)],
            data={"plugin_name": plugin_display, "version": plugin_version},
        )
        return None

    async def refresh_plugin_schedules(
        self,
        *,
        plugin_id: int,
        admin_id: int,
    ) -> dict[str, Any]:
        result = await self._plugin_service.refresh_plugin_schedules(
            plugin_id,
            operator_id=admin_id,
        )
        await self._db.commit()
        return result

    async def repair_plugin(self, *, plugin_id: int, admin_id: int) -> None:
        await self._lifecycle.repair(plugin_id, operator_id=admin_id)

    async def force_cleanup_orphan(self, *, plugin_id: int) -> None:
        await self._cleanup_service.force_cleanup_orphan(plugin_id)
        await self._db.flush()

    async def upload_icon(self, *, plugin_id: int, file: UploadFile) -> str:
        return await self._cleanup_service.save_plugin_icon(
            plugin_id,
            filename=file.filename,
            content=await file.read(),
        )

    async def activate_license(
        self, *, plugin_id: int, license_key: str
    ) -> dict[str, Any]:
        from app.plugins.license import activate_license as do_activate

        result = await do_activate(plugin_id, license_key, self._db)
        if not result.get("success"):
            raise BusinessException(
                message=result.get("message", _("plugin.error.activation_failed"))
            )
        return result

    async def activate_trial(self, *, plugin_id: int) -> dict[str, Any] | None:
        from app.plugins.license import create_trial_license, get_license_status_by_id

        license_info = await create_trial_license(plugin_id, db=self._db)
        if license_info:
            return license_info
        return await get_license_status_by_id(plugin_id, self._db)

    async def revoke_license(self, *, plugin_id: int) -> None:
        from app.plugins.license import revoke_license as do_revoke

        await do_revoke(plugin_id, self._db)

    async def delete_backup(self, *, plugin_id: int, backup_name: str) -> None:
        await self._cleanup_service.delete_backup(plugin_id, backup_name)


__all__ = ["PluginAdminWorkflowService"]
