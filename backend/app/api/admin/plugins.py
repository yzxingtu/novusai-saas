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
from app.api.admin.plugin_dependency_routes import register_plugin_dependency_routes
from app.core.base_controller import GlobalController
from app.core.deps import ActiveAdmin, DbSession
from app.core.i18n import _ as translate
from app.core.response import deleted, success
from app.enums.rbac import PermissionScope
from app.rbac.decorators import (
    MenuAIConfig,
    MenuConfig,
    action_delete,
    action_update,
    permission_resource,
)
from app.services.system.plugin_admin_workflow_service import (
    PluginAdminWorkflowService,
)
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
    workflow_service_class = PluginAdminWorkflowService

    def get_workflow_service(self, db: DbSession) -> PluginAdminWorkflowService:
        return self.workflow_service_class(db)

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
            await self.get_workflow_service(db).enable_plugin(
                plugin_id=plugin_id,
                admin_id=admin.id,
                menu_overrides=body.menu_overrides if body else None,
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
            await self.get_workflow_service(db).disable_plugin(
                plugin_id=plugin_id,
                admin_id=admin.id,
                force=force,
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
            await self.get_workflow_service(db).update_menu_config(
                plugin_id=plugin_id,
                menu_overrides=body.menu_overrides,
            )
            return success(data={"message": translate("plugin.menu_config_updated")})

        @self.router.post("/{plugin_id}/sync-manifest")
        @action_update("action.plugin.update")
        async def sync_manifest(
            plugin_id: int,
            db: DbSession,
            admin: ActiveAdmin,
        ):
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
            deleted_already_message = await self.get_workflow_service(db).uninstall_plugin(
                plugin_id=plugin_id,
                admin_id=admin.id,
                confirm_data_delete=confirm_data_delete,
                cleanup_dependencies=cleanup_dependencies,
            )
            if deleted_already_message:
                return deleted(message=deleted_already_message)
            return deleted()

        @self.router.post("/{plugin_id}/refresh-schedules")
        @action_update("action.plugin.repair")
        async def refresh_plugin_schedules(
            plugin_id: int,
            db: DbSession,
            admin: ActiveAdmin,
        ):
            result = await self.get_workflow_service(db).refresh_plugin_schedules(
                plugin_id=plugin_id,
                admin_id=admin.id,
            )
            return success(
                data=result,
                message=translate("plugin.schedule_refreshed"),
            )

        @self.router.post("/{plugin_id}/repair")
        @action_update("action.plugin.repair")
        async def repair_plugin(plugin_id: int, db: DbSession, admin: ActiveAdmin):
            await self.get_workflow_service(db).repair_plugin(
                plugin_id=plugin_id,
                admin_id=admin.id,
            )
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
            await self.get_workflow_service(db).force_cleanup_orphan(plugin_id=plugin_id)
            return deleted()

        @self.router.put("/{plugin_id}/config")
        @action_update("action.plugin.config")
        async def update_config(
            plugin_id: int,
            body: PluginConfigBody,
            db: DbSession = None,
            admin: ActiveAdmin = None,
        ):
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
            icon = await self.get_workflow_service(db).upload_icon(
                plugin_id=plugin_id,
                file=file,
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
            result = await self.get_workflow_service(db).activate_license(
                plugin_id=plugin_id,
                license_key=body.license_key,
            )
            return success(data=result)

        @self.router.post("/{plugin_id}/activate-trial")
        @action_update("action.plugin.activate_trial")
        async def activate_trial(
            plugin_id: int,
            db: DbSession = None,
            admin: ActiveAdmin = None,
        ):
            license_info = await self.get_workflow_service(db).activate_trial(
                plugin_id=plugin_id
            )
            return success(data=license_info)

        @self.router.delete("/{plugin_id}/license")
        @action_delete("action.plugin.revoke_license")
        async def revoke_license(
            plugin_id: int,
            db: DbSession = None,
            admin: ActiveAdmin = None,
        ):
            await self.get_workflow_service(db).revoke_license(plugin_id=plugin_id)
            return deleted()

        @self.router.delete("/{plugin_id}/backups/{backup_name}")
        @action_delete("action.plugin.uninstall")
        async def delete_backup(
            plugin_id: int,
            backup_name: str,
            db: DbSession,
            admin: ActiveAdmin,
        ):
            await self.get_workflow_service(db).delete_backup(
                plugin_id=plugin_id,
                backup_name=backup_name,
            )
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
