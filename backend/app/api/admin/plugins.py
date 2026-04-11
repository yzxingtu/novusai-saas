"""
插件管理 Controller（管理端） / Plugin Management Controller (Admin)
"""

from __future__ import annotations

from fastapi import File, UploadFile

from app.api.admin import plugin_install_preview as _install_preview_helpers
from app.api.admin.plugin_admin_contracts import (
    MenuOverrideItem as _MenuOverrideItem,
)
from app.api.admin.plugin_admin_contracts import (
    PluginActivateLicenseBody,
    PluginAssignTenantsBody,
    PluginCapabilitiesBody,
    PluginConfigBody,
    PluginDependencyActionBody,
    PluginEnableBody,
    PluginInstallConfirmBody,
    PluginMenuConfigBody,
    PluginRollbackBody,
    register_plugin_admin_read_routes,
)
from app.api.admin.plugin_admin_contracts import (
    build_menu_overrides_payload as _build_menu_overrides_payload,
)
from app.api.admin.plugin_dependency_routes import register_plugin_dependency_routes
from app.core.base_controller import GlobalController
from app.core.deps import ActiveAdmin, DbSession
from app.core.i18n import _ as translate
from app.core.response import deleted, success
from app.enums.rbac import PermissionScope
from app.plugins.lifecycle import PluginLifecycle
from app.rbac.decorators import (
    MenuAIConfig,
    MenuConfig,
    action_delete,
    action_update,
    permission_resource,
)
from app.services.system.plugin_cleanup_service import PluginCleanupService
from app.services.system.plugin_service import PluginService

_assert_install_preview_token = _install_preview_helpers.assert_install_preview_token
_assert_marketplace_package_identity = (
    _install_preview_helpers.assert_marketplace_package_identity
)
_create_install_preview_token = _install_preview_helpers.create_install_preview_token
_decode_install_preview_token = _install_preview_helpers.decode_install_preview_token
_extract_plugin_from_zip = _install_preview_helpers.extract_plugin_from_zip
_sanitize_slug = _install_preview_helpers.sanitize_marketplace_slug
_test_registry_connection = _install_preview_helpers.test_registry_connection

MenuOverrideItem = _MenuOverrideItem


@permission_resource(
    resource="plugin",
    name="menu.admin.plugin",
    scope=PermissionScope.ADMIN,
    parent_resource="system_maintenance",
    menu=MenuConfig(
        ai=MenuAIConfig(
            description="Install, enable, disable, configure, and manage system plugins",
            keywords=[
                "插件",
                "扩展",
                "plugin",
                "plugins",
                "extension",
                "extensions",
                "addon",
            ],
            capabilities=[
                "install_plugin",
                "configure_plugin",
                "enable_plugin",
                "view_plugins",
            ],
            category="plugin",
        ),
        icon="lucide:puzzle",
        path="/plugins",
        component="admin/plugins/index",
        parent="system_maintenance",
        sort_order=60,
    ),
)
class AdminPluginController(GlobalController):
    prefix = "/plugins"
    tags = ["Plugin Management"]
    service_class = PluginService

    def _register_routes(self):
        register_plugin_admin_read_routes(self)
        register_plugin_install_preview_routes(self)
        register_plugin_dependency_routes(
            self,
            dependency_action_body=PluginDependencyActionBody,
        )

        @self.router.post("/{plugin_id}/enable")
        @action_update("action.plugin.enable")
        async def enable_plugin(
            plugin_id: int,
            db: DbSession,
            admin: ActiveAdmin,
            body: PluginEnableBody | None = None,
        ):
            lifecycle = PluginLifecycle(db)
            if body and body.menu_overrides:
                await lifecycle.update_menu_overrides(
                    plugin_id,
                    menu_overrides=_build_menu_overrides_payload(body.menu_overrides),
                    refresh_runtime=False,
                )

            await self.get_service(db).enable_plugin(plugin_id, operator_id=admin.id)

            plugin = await self.get_service(db).get_by_id(plugin_id)
            from app.services.common.notification_service import notify

            await notify(
                db,
                "biz.plugin_enabled",
                [("admin", admin.id)],
                data={"plugin_name": plugin.display_name or plugin.name},
            )
            return success(data={"message": "Plugin enabled"})

        @self.router.post("/{plugin_id}/disable")
        @action_update("action.plugin.disable")
        async def disable_plugin(
            plugin_id: int,
            db: DbSession,
            admin: ActiveAdmin,
            force: bool = False,
        ):
            service = self.get_service(db)
            plugin = await service.get_by_id(plugin_id)
            plugin_display = plugin.display_name or plugin.name

            await service.disable_plugin(plugin_id, force=force, operator_id=admin.id)

            from app.services.common.notification_service import notify

            await notify(
                db,
                "biz.plugin_disabled",
                [("admin", admin.id)],
                data={"plugin_name": plugin_display},
            )
            return success(data={"message": "Plugin disabled"})

        @self.router.put("/{plugin_id}/menu-config")
        @action_update("action.plugin.update")
        async def update_menu_config(
            plugin_id: int,
            body: PluginMenuConfigBody,
            db: DbSession,
            admin: ActiveAdmin,
        ):
            _admin = admin
            await PluginLifecycle(db).update_menu_overrides(
                plugin_id,
                menu_overrides=_build_menu_overrides_payload(body.menu_overrides),
                refresh_runtime=True,
            )
            return success(data={"message": translate("plugin.menu_config_updated")})

        @self.router.post("/{plugin_id}/sync-manifest")
        @action_update("action.plugin.update")
        async def sync_manifest(
            plugin_id: int,
            db: DbSession,
            admin: ActiveAdmin,
        ):
            _admin = admin
            await self.get_service(db).sync_manifest(plugin_id)
            return success(data={"message": translate("plugin.manifest_synced")})

        @self.router.delete("/{plugin_id}")
        @action_delete("action.plugin.uninstall")
        async def uninstall_plugin(
            plugin_id: int,
            db: DbSession,
            admin: ActiveAdmin,
            confirm_data_delete: bool = False,
            cleanup_dependencies: bool = False,
        ):
            service = self.get_service(db)
            plugin = await service.get_by_id(plugin_id)
            if plugin is None:
                return deleted(
                    message=translate("plugin.deleted_already").format(
                        plugin_id=plugin_id
                    )
                )

            plugin_display = plugin.display_name or plugin.name
            plugin_version = plugin.version or "1.0.0"
            await service.uninstall_plugin(
                plugin_id,
                confirm_data_delete,
                cleanup_dependencies=cleanup_dependencies,
                operator_id=admin.id,
            )

            from app.services.common.notification_service import notify

            await notify(
                db,
                "biz.plugin_uninstalled",
                [("admin", admin.id)],
                data={"plugin_name": plugin_display, "version": plugin_version},
            )
            return deleted()

        @self.router.post("/{plugin_id}/refresh-schedules")
        @action_update("action.plugin.repair")
        async def refresh_plugin_schedules(
            plugin_id: int,
            db: DbSession,
            admin: ActiveAdmin,
        ):
            result = await self.get_service(db).refresh_plugin_schedules(
                plugin_id,
                operator_id=admin.id,
            )
            await db.commit()
            return success(
                data=result,
                message=translate("plugin.schedule_refreshed"),
            )

        @self.router.post("/{plugin_id}/repair")
        @action_update("action.plugin.repair")
        async def repair_plugin(plugin_id: int, db: DbSession, admin: ActiveAdmin):
            await PluginLifecycle(db).repair(plugin_id, operator_id=admin.id)
            return success(
                data={"message": translate("plugin.repaired_and_restored")}
            )

        @self.router.delete("/{plugin_id}/force-cleanup")
        @action_delete("action.plugin.uninstall")
        async def force_cleanup_orphan(
            plugin_id: int,
            db: DbSession,
            admin: ActiveAdmin,
        ):
            _admin = admin
            await PluginCleanupService(db).force_cleanup_orphan(plugin_id)
            await db.flush()
            return deleted()

        @self.router.put("/{plugin_id}/config")
        @action_update("action.plugin.config")
        async def update_config(
            plugin_id: int,
            body: PluginConfigBody,
            db: DbSession = None,
            admin: ActiveAdmin = None,
        ):
            _admin = admin
            await self.get_service(db).update_plugin_config(plugin_id, body.config)
            return success(data={"message": "Config updated"})

        @self.router.put("/{plugin_id}/capabilities")
        @action_update("action.plugin.capabilities")
        async def update_capabilities(
            plugin_id: int,
            body: PluginCapabilitiesBody,
            db: DbSession = None,
            admin: ActiveAdmin = None,
        ):
            _admin = admin
            await self.get_service(db).update_capabilities(plugin_id, body.capabilities)
            return success(
                data={"message": translate("plugin.capabilities_updated")}
            )

        @self.router.post("/{plugin_id}/icon")
        @action_update("action.plugin.icon")
        async def upload_icon(
            plugin_id: int,
            file: UploadFile = File(...),
            db: DbSession = None,
            admin: ActiveAdmin = None,
        ):
            _admin = admin
            icon = await PluginCleanupService(db).save_plugin_icon(
                plugin_id,
                filename=file.filename,
                content=await file.read(),
            )
            return success(data={"icon": icon})

        @self.router.post("/{plugin_id}/upgrade")
        @action_update("action.plugin.upgrade")
        async def upgrade_plugin(
            plugin_id: int,
            file: UploadFile = File(...),
            db: DbSession = None,
            admin: ActiveAdmin = None,
        ):
            _admin = admin
            await self.get_service(db).upgrade_plugin(plugin_id, file)
            return success(data={"message": translate("plugin.upgraded")})

        @self.router.post("/{plugin_id}/rollback")
        @action_update("action.plugin.rollback")
        async def rollback_plugin(
            plugin_id: int,
            body: PluginRollbackBody,
            db: DbSession = None,
            admin: ActiveAdmin = None,
        ):
            _admin = admin
            await self.get_service(db).rollback_plugin(
                plugin_id,
                body.target_version,
            )
            return success(
                data={
                    "message": translate("plugin.rolled_back_to").format(
                        version=body.target_version,
                    )
                }
            )

        @self.router.post("/{plugin_id}/tenants")
        @action_update("action.plugin.assign_tenants")
        async def assign_tenants(
            plugin_id: int,
            body: PluginAssignTenantsBody,
            db: DbSession = None,
            admin: ActiveAdmin = None,
        ):
            _admin = admin
            count = await self.get_service(db).assign_tenants(plugin_id, body.tenant_ids)
            return success(data={"assigned": count})

        @self.router.delete("/{plugin_id}/tenants/{tenant_id}")
        @action_update("action.plugin.unassign_tenant")
        async def unassign_tenant(
            plugin_id: int,
            tenant_id: int,
            db: DbSession = None,
            admin: ActiveAdmin = None,
        ):
            _admin = admin
            await self.get_service(db).unassign_tenant(plugin_id, tenant_id)
            return deleted()

        @self.router.post("/{plugin_id}/activate-license")
        @action_update("action.plugin.activate_license")
        async def activate_license(
            plugin_id: int,
            body: PluginActivateLicenseBody,
            db: DbSession = None,
            admin: ActiveAdmin = None,
        ):
            _admin = admin
            from app.plugins.license import activate_license as do_activate

            result = await do_activate(plugin_id, body.license_key, db)
            if not result.get("success"):
                from app.exceptions.base import BusinessException

                raise BusinessException(
                    message=result.get(
                        "message",
                        translate("plugin.error.activation_failed"),
                    )
                )
            return success(data=result)

        @self.router.post("/{plugin_id}/activate-trial")
        @action_update("action.plugin.activate_trial")
        async def activate_trial(
            plugin_id: int,
            db: DbSession = None,
            admin: ActiveAdmin = None,
        ):
            _admin = admin
            from app.plugins.license import (
                create_trial_license,
                get_license_status_by_id,
            )

            license_info = await create_trial_license(plugin_id, db=db)
            if not license_info:
                license_info = await get_license_status_by_id(plugin_id, db)
            return success(data=license_info)

        @self.router.delete("/{plugin_id}/license")
        @action_delete("action.plugin.revoke_license")
        async def revoke_license(
            plugin_id: int,
            db: DbSession = None,
            admin: ActiveAdmin = None,
        ):
            _admin = admin
            from app.plugins.license import revoke_license as do_revoke

            await do_revoke(plugin_id, db)
            return deleted()

        @self.router.delete("/{plugin_id}/backups/{backup_name}")
        @action_delete("action.plugin.uninstall")
        async def delete_backup(
            plugin_id: int,
            backup_name: str,
            db: DbSession,
            admin: ActiveAdmin,
        ):
            _admin = admin
            await PluginCleanupService(db).delete_backup(plugin_id, backup_name)
            return deleted()


def register_plugin_install_preview_routes(controller: GlobalController) -> None:
    _install_preview_helpers.register_plugin_install_preview_routes(controller)


admin_plugin_controller = AdminPluginController()
router = admin_plugin_controller.router


__all__ = [
    "AdminPluginController",
    "MenuOverrideItem",
    "PluginInstallConfirmBody",
    "_assert_install_preview_token",
    "_assert_marketplace_package_identity",
    "_create_install_preview_token",
    "_decode_install_preview_token",
    "_extract_plugin_from_zip",
    "_sanitize_slug",
    "_test_registry_connection",
    "admin_plugin_controller",
    "router",
]
