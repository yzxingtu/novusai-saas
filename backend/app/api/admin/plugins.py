"""
插件管理 Controller（管理端） / Plugin Management Controller (Admin)
"""

import shutil
import tempfile
from pathlib import Path

from fastapi import File, Form, Response, UploadFile

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
)
from app.api.admin.plugin_admin_contracts import (
    build_menu_overrides_payload as _build_menu_overrides_payload,
)
from app.api.admin.plugin_admin_contracts import (
    resolve_plugin_audit_service as _resolve_plugin_audit_service,
)
from app.api.admin.plugin_dependency_routes import register_plugin_dependency_routes
from app.api.admin.plugin_install_preview import (
    assert_install_preview_token as _assert_install_preview_token,
)
from app.api.admin.plugin_install_preview import (
    assert_marketplace_package_identity as _assert_marketplace_package_identity,
)
from app.api.admin.plugin_install_preview import (
    create_install_preview_token as _create_install_preview_token,
)
from app.api.admin.plugin_install_preview import (
    decode_install_preview_token as _decode_install_preview_token,
)
from app.api.admin.plugin_install_preview import (
    extract_plugin_from_zip as _extract_plugin_from_zip,
)
from app.api.admin.plugin_install_preview import (
    sanitize_marketplace_slug as _sanitize_slug,
)
from app.api.admin.plugin_install_preview import (
    test_registry_connection as _test_registry_connection,
)
from app.core.base_controller import GlobalController
from app.core.deps import ActiveAdmin, DbSession, QueryParams
from app.core.i18n import _
from app.core.logging import LogManager
from app.core.response import (
    created,
    deleted,
    paginated,
    resolve_public_error_message,
    success,
)
from app.enums.rbac import PermissionScope
from app.rbac.decorators import (
    MenuAIConfig,
    MenuConfig,
    action_create,
    action_delete,
    action_read,
    action_update,
    permission_resource,
)
from app.services.system.plugin_cleanup_service import PluginCleanupService
from app.services.system.plugin_read_model_service import PluginReadModelService
from app.services.system.plugin_service import PluginService

logger = LogManager.get_logger("plugin.admin")
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
        register_plugin_dependency_routes(
            self,
            dependency_action_body=PluginDependencyActionBody,
        )

        # ── 前端插槽查询 / Frontend Slot Query ──

        @self.router.get("/slots")
        @action_read("action.plugin.list")
        async def get_plugin_slots(db: DbSession, admin: ActiveAdmin):
            """
            获取所有已启用插件的前端插槽数据（admin 端）。
            Get all enabled plugins' frontend slot data (admin side).

            返回格式 / Response format:
            {
              "header_widgets": [...],
              "dashboard_widgets": [...],
              "settings_tabs": [...],
              "floating_panels": [...],
              "pages": [...],
              "notification_ui": [...]
            }

            前端 pluginSlotsStore 启动时调用此接口，驱动各插槽渲染。
            Frontend pluginSlotsStore calls this endpoint on startup to drive slot rendering.
            """
            return success(
                data=await PluginReadModelService(db).build_admin_visible_slots(admin)
            )

        # ── 更新检查 / Update Check ──

        @self.router.get("/updates")
        @action_read("action.plugin.list")
        async def check_updates(db: DbSession, admin: ActiveAdmin):
            """检查已安装插件的可用更新 / Check available updates for installed plugins"""
            from app.plugins.update_checker import check_updates as _check

            updates = await _check(db)
            return success(data=updates)

        # ── 插件市场 / Plugin Marketplace ──

        @self.router.post("/marketplace/test-connection")
        @action_read("action.plugin.list")
        async def marketplace_test_connection(
            db: DbSession,
            admin: ActiveAdmin,
            source_url: str = "",
        ):
            """测试市场镜像源连通性 / Test marketplace mirror source connectivity"""
            _ = db, admin
            from app.plugins.marketplace import _DEFAULT_GITHUB_URL

            return success(
                data=await _test_registry_connection(
                    source_url=source_url,
                    default_url=_DEFAULT_GITHUB_URL,
                    log_label="Marketplace",
                )
            )

        @self.router.post("/skill-registry/test-connection")
        @action_read("action.plugin.list")
        async def skill_registry_test_connection(
            db: DbSession,
            admin: ActiveAdmin,
            source_url: str = "",
        ):
            """测试技能市场镜像源连通性 / Test skill registry mirror source connectivity"""
            _ = db, admin
            from app.services.ai.skill_registry_service import (
                _DEFAULT_GITHUB_URL as _SKILL_DEFAULT_GITHUB_URL,
            )

            return success(
                data=await _test_registry_connection(
                    source_url=source_url,
                    default_url=_SKILL_DEFAULT_GITHUB_URL,
                    log_label="Skill registry",
                )
            )

        @self.router.get("/marketplace")
        @action_read("action.plugin.list")
        async def marketplace_list(
            db: DbSession,
            admin: ActiveAdmin,
            response: Response,
            category: str = "",
            sort: str = "-downloads",
            search: str = "",
            page_number: int = 1,
            page_size: int = 20,
        ):
            """插件市场列表（搜索/分类/排序/分页） / Plugin marketplace list (search/category/sort/pagination)"""
            page_size = max(1, min(page_size, 100))
            page_number = max(1, page_number)

            from app.plugins.marketplace import MarketplaceClient

            client = MarketplaceClient(db)
            result = await client.list_plugins(
                search=search,
                category=category,
                sort=sort,
                page_number=page_number,
                page_size=page_size,
            )
            page_items = result["items"]
            total = result["total"]

            response.headers["Cache-Control"] = "private, max-age=60"
            return paginated(
                items=page_items, total=total, page=page_number, page_size=page_size
            )

        @self.router.get("/marketplace/{slug}")
        @action_read("action.plugin.list")
        async def marketplace_detail(
            slug: str, db: DbSession, admin: ActiveAdmin, response: Response
        ):
            """插件市场详情 / Plugin marketplace detail"""
            from app.plugins.marketplace import MarketplaceClient

            client = MarketplaceClient(db)
            detail = await client.fetch_plugin_detail(slug)
            if not detail:
                from app.plugins.exceptions import PluginNotFoundError

                raise PluginNotFoundError(
                    message=_("plugin.error.marketplace_not_found").format(
                        slug=slug,
                    )
                )

            readme = await client.fetch_readme(slug)
            detail["readme"] = readme

            compat = detail.get("compatibility", {})
            detail["compatibility_ok"] = True
            if compat.get("platform_version"):
                detail["platform_version_required"] = compat["platform_version"]

            response.headers["Cache-Control"] = "private, max-age=120"
            return success(data=detail)

        @self.router.post("/marketplace/{slug}/install")
        @action_create("action.plugin.install")
        async def marketplace_preview_install(
            slug: str,
            db: DbSession = None,
            admin: ActiveAdmin = None,
        ):
            """市场安装预览（下载+解压+生成预览，不执行安装） / Marketplace install preview (download+extract+generate preview, no actual install)"""
            _sanitize_slug(slug)

            from app.plugins.marketplace import MarketplaceClient

            client = MarketplaceClient(db)
            detail = await client.fetch_plugin_detail(slug)
            if not detail:
                from app.plugins.exceptions import PluginNotFoundError

                raise PluginNotFoundError(
                    message=_("plugin.error.marketplace_not_found").format(
                        slug=slug,
                    )
                )

            version = detail.get("version", "1.0.0")
            zip_path = await client.download_plugin(slug, version)

            from app.plugins.loader import PluginLoader
            from app.plugins.package_security import extract_plugin_zip_safely
            from app.plugins.preview import generate_preview

            try:
                extract_dir = zip_path.parent / "extracted"
                plugin_dir = extract_plugin_zip_safely(zip_path, extract_dir)
                loader = PluginLoader(plugins_dir=plugin_dir.parent)
                manifest = loader.load_manifest_from_path(plugin_dir)
                _assert_marketplace_package_identity(
                    slug=slug,
                    detail=detail,
                    manifest=manifest,
                )
                preview = await generate_preview(plugin_dir, loader, db=db)
                preview.preview_token = _create_install_preview_token(
                    source="marketplace",
                    plugin_name=manifest.name,
                    version=manifest.version,
                    admin_id=getattr(admin, "id", None),
                    marketplace_slug=slug,
                )
                return success(data=preview.model_dump())
            finally:
                shutil.rmtree(zip_path.parent, ignore_errors=True)

        @self.router.post("/marketplace/{slug}/confirm-install")
        @action_create("action.plugin.install")
        async def marketplace_confirm_install(
            slug: str,
            body: PluginInstallConfirmBody,
            db: DbSession = None,
            admin: ActiveAdmin = None,
        ):
            """确认从市场安装（下载+安装，设置 install_source=marketplace） / Confirm marketplace install (download+install, set install_source=marketplace)"""
            _sanitize_slug(slug)
            preview_payload = _decode_install_preview_token(body.preview_token)
            _assert_install_preview_token(
                preview_payload,
                source="marketplace",
                marketplace_slug=slug,
                admin_id=getattr(admin, "id", None),
            )

            from app.enums.plugin import PluginInstallSourceEnum
            from app.plugins.marketplace import MarketplaceClient

            client = MarketplaceClient(db)
            detail = await client.fetch_plugin_detail(slug)
            if not detail:
                from app.plugins.exceptions import PluginNotFoundError

                raise PluginNotFoundError(
                    message=_("plugin.error.marketplace_not_found").format(
                        slug=slug,
                    )
                )

            version = detail.get("version", "1.0.0")
            _assert_install_preview_token(
                preview_payload,
                source="marketplace",
                version=str(version),
                admin_id=getattr(admin, "id", None),
                marketplace_slug=slug,
            )
            zip_path = await client.download_plugin(slug, version)

            from app.plugins.loader import PluginLoader
            from app.plugins.package_security import extract_plugin_zip_safely

            try:
                extract_dir = zip_path.parent / "extracted"
                plugin_dir = extract_plugin_zip_safely(zip_path, extract_dir)

                loader = PluginLoader()
                manifest = loader.load_manifest_from_path(plugin_dir)
                _assert_marketplace_package_identity(
                    slug=slug,
                    detail=detail,
                    manifest=manifest,
                )
                _assert_install_preview_token(
                    preview_payload,
                    source="marketplace",
                    plugin_name=manifest.name,
                    version=manifest.version,
                    admin_id=getattr(admin, "id", None),
                    marketplace_slug=slug,
                )
                logger.info(
                    "Marketplace confirm install: slug={} plugin={}",
                    slug,
                    manifest.name,
                )
                service = self.get_service(db)
                # 直接从 staging 目录安装，生命周期层负责复制与回滚，避免预拷贝造成脏目录残留
                # Install directly from staging dir, lifecycle layer handles copy & rollback to avoid dirty dir residue
                plugin = await service.install_from_path(plugin_dir, body.config)

                # 更新 install_source 和 marketplace_slug / Update install_source and marketplace_slug
                plugin.install_source = PluginInstallSourceEnum.MARKETPLACE.value
                plugin.marketplace_slug = slug
                await db.flush()

                from app.services.common.notification_service import notify

                await notify(
                    db,
                    "biz.plugin_installed",
                    [("admin", admin.id)],
                    data={
                        "plugin_name": plugin.display_name or plugin.name,
                        "version": plugin.version or "1.0.0",
                    },
                )

                return created(data=plugin.to_dict())
            finally:
                shutil.rmtree(zip_path.parent, ignore_errors=True)

        @self.router.get("/menu-parent-options")
        @action_read("action.plugin.list")
        async def get_menu_parent_options(db: DbSession, admin: ActiveAdmin):
            """
            获取可用的父级菜单树，供插件菜单挂载位置选择 / Get available parent menu tree for plugin menu mount.

            同时返回 admin 和 tenant 两侧的菜单树（多级嵌套），
            前端可按插件菜单的 scope 显示对应分组。
            Returns menu trees for both admin and tenant sides (multi-level nested),
            frontend can display corresponding groups based on plugin menu scope.
            """
            return success(
                data=await PluginReadModelService(db).build_menu_parent_options()
            )

        @self.router.get("")
        @action_read("action.plugin.list")
        async def list_plugins(db: DbSession, admin: ActiveAdmin, query: QueryParams):
            _admin = admin
            result_items, total = await PluginReadModelService(
                db
            ).build_admin_plugin_list(query)

            return paginated(
                items=result_items,
                total=total,
                page=query.page,
                page_size=query.size,
            )

        @self.router.get("/{plugin_id}")
        @action_read("action.plugin.detail")
        async def get_plugin(
            plugin_id: int,
            db: DbSession,
            admin: ActiveAdmin,
            locale: str = "zh-CN",
        ):
            _admin = admin
            return success(
                data=await PluginReadModelService(db).build_admin_plugin_detail(
                    plugin_id,
                    locale=locale,
                )
            )

        @self.router.post("/preview")
        @action_create("action.plugin.preview")
        async def preview_install(
            file: UploadFile = File(...),
            db: DbSession = None,
            admin: ActiveAdmin = None,
        ):
            """上传 ZIP 分析，返回安装预览（不安装） / Upload ZIP for analysis, return install preview (no installation)"""
            from app.plugins.preview import generate_preview

            content = await file.read()
            staging_dir, plugin_dir = _extract_plugin_from_zip(
                content, file.filename or "plugin.zip"
            )

            try:
                from app.plugins.loader import PluginLoader

                loader = PluginLoader(plugins_dir=plugin_dir.parent)
                preview = await generate_preview(plugin_dir, loader, db=db)
                manifest = loader.load_manifest_from_path(plugin_dir)
                preview.preview_token = _create_install_preview_token(
                    source="upload",
                    plugin_name=manifest.name,
                    version=manifest.version,
                    admin_id=getattr(admin, "id", None),
                )
                return success(data=preview.model_dump())
            finally:
                shutil.rmtree(staging_dir, ignore_errors=True)

        @self.router.post("/upload")
        @action_create("action.plugin.install")
        async def install_plugin(
            file: UploadFile = File(...),
            preview_token: str = Form(""),
            db: DbSession = None,
            admin: ActiveAdmin = None,
        ):
            """
            上传 ZIP 并安装插件 / Upload ZIP and install plugin

            lifecycle.install() 内部负责把文件从 staging_dir 复制到 plugins/{name}/，
            this endpoint only needs to extract + call install logic + clean up temp directory.
            此端点只需解压 + 调用安装逻辑 + 清理临时目录。
            """
            preview_payload = _decode_install_preview_token(preview_token)
            _assert_install_preview_token(
                preview_payload,
                source="upload",
                admin_id=getattr(admin, "id", None),
            )

            content = await file.read()
            staging_dir, plugin_dir = _extract_plugin_from_zip(
                content, file.filename or "plugin.zip"
            )

            try:
                import yaml

                with open(plugin_dir / "plugin.yaml", encoding="utf-8") as yf:
                    manifest_data = yaml.safe_load(yf)
                plugin_name = manifest_data.get("name", plugin_dir.name)
                plugin_version = str(manifest_data.get("version", ""))
                _assert_install_preview_token(
                    preview_payload,
                    source="upload",
                    plugin_name=str(plugin_name),
                    version=plugin_version,
                    admin_id=getattr(admin, "id", None),
                )

                # 检查是否已安装（DB 有记录则提示走升级流程） / Check if already installed (prompt upgrade if DB record exists)
                await PluginReadModelService(db).assert_name_available(
                    str(plugin_name)
                )

                # lifecycle.install() 内部会把 plugin_dir -> plugins/{name}/ 完成文件复制 / lifecycle.install() copies plugin_dir -> plugins/{name}/ internally
                service = self.get_service(db)
                plugin = await service.install_from_path(
                    plugin_dir, operator_id=admin.id
                )

                from app.services.common.notification_service import notify

                await notify(
                    db,
                    "biz.plugin_installed",
                    [("admin", admin.id)],
                    data={
                        "plugin_name": plugin.display_name or plugin.name,
                        "version": plugin.version or "1.0.0",
                    },
                )

                return created(data=plugin.to_dict())
            finally:
                shutil.rmtree(staging_dir, ignore_errors=True)

        @self.router.post("/{plugin_id}/enable")
        @action_update("action.plugin.enable")
        async def enable_plugin(
            plugin_id: int,
            db: DbSession,
            admin: ActiveAdmin,
            body: PluginEnableBody | None = None,
        ):
            """启用插件（校验插件依赖并按需安装 Python 依赖，通过 Socket.IO 推送进度） / Enable plugin (validate plugin deps and install Python deps when needed, push progress via Socket.IO)"""
            service = self.get_service(db)

            # 保存管理员配置的菜单挂载位置 / Save admin-configured menu mount positions
            if body and body.menu_overrides:
                plugin = await service.get_by_id(plugin_id)
                config = dict(plugin.config or {})
                config["menu_overrides"] = _build_menu_overrides_payload(
                    body.menu_overrides
                )
                plugin.config = config
                await db.flush()

            await service.enable_plugin(plugin_id, operator_id=admin.id)

            plugin = await service.get_by_id(plugin_id)
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
            """更新插件菜单挂载位置（已启用插件可动态调整） / Update plugin menu mount point (enabled plugins can be dynamically adjusted)"""
            from app.enums.plugin import PluginStatusEnum
            from app.exceptions.base import BusinessException
            from app.plugins._extension_registrar import (
                register_navigation_extensions,
            )
            from app.plugins.loader import PluginLoader
            from app.plugins.registry import ExtensionRegistry
            from app.rbac.sync import PermissionSyncService

            service = self.get_service(db)
            plugin = await service.get_by_id(plugin_id)

            # 保存新的菜单覆盖配置 / Save new menu override config
            config = dict(plugin.config or {})
            config["menu_overrides"] = _build_menu_overrides_payload(
                body.menu_overrides
            )
            plugin.config = config
            await db.flush()

            # 如果插件已启用，重新注册扩展点 + 同步权限到 DB / If plugin is enabled, re-register extensions + sync permissions to DB
            if plugin.status == PluginStatusEnum.ENABLED.value:
                registry = ExtensionRegistry.get_instance()
                registry.unregister_by_type(plugin.name, "menu")

                loader = PluginLoader()
                manifest = loader.load_manifest(plugin.name)
                menu_overrides = config.get("menu_overrides")
                try:
                    register_navigation_extensions(
                        registry,
                        manifest,
                        plugin.name,
                        menu_overrides=menu_overrides,
                    )
                except Exception as exc:
                    registry.unregister_by_type(plugin.name, "menu")
                    raise BusinessException(
                        message=resolve_public_error_message(
                            exc,
                            fallback_message=_(
                                "plugin.error.menu_config_update_failed"
                            ),
                        ),
                    ) from exc

                # 仅同步当前插件权限，避免全量 sync 的事务副作用 / Only sync current plugin permissions to avoid side effects of full sync
                sync_service = PermissionSyncService(db)
                await sync_service.sync_plugin_permissions(plugin.name)

            return success(data={"message": _("plugin.menu_config_updated")})

        @self.router.post("/{plugin_id}/sync-manifest")
        @action_update("action.plugin.update")
        async def sync_manifest(
            plugin_id: int,
            db: DbSession,
            admin: ActiveAdmin,
        ):
            """显式同步磁盘 manifest 到数据库；版本变化必须走 upgrade。 / Explicitly sync disk manifest to DB; version drift must use upgrade."""
            service = self.get_service(db)
            await service.sync_manifest(plugin_id)
            return success(data={"message": _("plugin.manifest_synced")})

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
                    message=_("plugin.deleted_already").format(plugin_id=plugin_id)
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
            """手动刷新插件调度状态 / Manually refresh plugin scheduler state."""
            service = self.get_service(db)
            result = await service.refresh_plugin_schedules(
                plugin_id,
                operator_id=admin.id,
            )
            await db.commit()
            return success(
                data=result,
                message=_("plugin.schedule_refreshed"),
            )

        @self.router.post("/{plugin_id}/repair")
        @action_update("action.plugin.repair")
        async def repair_plugin(plugin_id: int, db: DbSession, admin: ActiveAdmin):
            """修复插件：控制器仅协调请求，运行时恢复编排下沉到 lifecycle。 / Repair plugin with lifecycle-owned runtime orchestration."""
            from app.plugins.lifecycle import PluginLifecycle

            lifecycle = PluginLifecycle(db)
            await lifecycle.repair(plugin_id, operator_id=admin.id)
            return success(data={"message": _("plugin.repaired_and_restored")})

        @self.router.delete("/{plugin_id}/force-cleanup")
        @action_delete("action.plugin.uninstall")
        async def force_cleanup_orphan(
            plugin_id: int, db: DbSession, admin: ActiveAdmin
        ):
            """强制清理孤立插件记录（磁盘文件已缺失的 error 状态插件） / Force cleanup orphaned plugin records (error-state plugins with missing disk files)"""
            await PluginCleanupService(db).force_cleanup_orphan(plugin_id)
            await db.flush()
            return deleted()

        # ── 配置 / Configuration ──

        @self.router.put("/{plugin_id}/config")
        @action_update("action.plugin.config")
        async def update_config(
            plugin_id: int,
            body: PluginConfigBody,
            db: DbSession = None,
            admin: ActiveAdmin = None,
        ):
            service = self.get_service(db)
            await service.update_plugin_config(plugin_id, body.config)
            return success(data={"message": "Config updated"})

        @self.router.put("/{plugin_id}/capabilities")
        @action_update("action.plugin.capabilities")
        async def update_capabilities(
            plugin_id: int,
            body: PluginCapabilitiesBody,
            db: DbSession = None,
            admin: ActiveAdmin = None,
        ):
            from app.exceptions.base import ValidationException
            from app.plugins.manifest import _VALID_CAPABILITIES

            unknown = [c for c in body.capabilities if c not in _VALID_CAPABILITIES]
            if unknown:
                raise ValidationException(
                    message=_("plugin.error.unknown_capabilities").format(
                        capabilities=", ".join(unknown),
                    ),
                )
            service = self.get_service(db)
            await service.update_capabilities(plugin_id, body.capabilities)
            return success(data={"message": _("plugin.capabilities_updated")})

        # ── 图标上传 / Icon Upload ──

        @self.router.post("/{plugin_id}/icon")
        @action_update("action.plugin.icon")
        async def upload_icon(
            plugin_id: int,
            file: UploadFile = File(...),
            db: DbSession = None,
            admin: ActiveAdmin = None,
        ):
            """上传插件图标（PNG/SVG/JPG） / Upload plugin icon (PNG/SVG/JPG)"""
            from app.plugins.loader import PLUGINS_DIR

            service = self.get_service(db)
            plugin = await service.get_by_id(plugin_id)

            # 验证文件类型 / Validate file type
            allowed = {".png", ".svg", ".jpg", ".jpeg", ".webp"}
            suffix = Path(file.filename).suffix.lower() if file.filename else ".png"
            if suffix not in allowed:
                from app.exceptions.base import ValidationException

                raise ValidationException(message=_("plugin.error.invalid_icon_type"))

            # 验证文件大小（最大 2MB） / Validate file size (max 2MB)
            _ICON_MAX_SIZE = 2 * 1024 * 1024
            content = await file.read()
            if len(content) > _ICON_MAX_SIZE:
                from app.exceptions.base import ValidationException

                raise ValidationException(
                    message=_("plugin.error.icon_too_large").format(size=len(content)),
                )

            # 保存文件 / Save file
            icon_filename = f"icon{suffix}"
            icon_path = PLUGINS_DIR / plugin.name / icon_filename
            with open(icon_path, "wb") as f:
                f.write(content)

            # 更新 icon 字段为插件根目录内的相对图标文件 / Store canonical plugin-root relative icon path
            plugin.icon = icon_filename
            await db.flush()

            return success(data={"icon": plugin.icon})

        # ── 版本 / Version ──

        @self.router.get("/{plugin_id}/versions")
        @action_read("action.plugin.versions")
        async def list_versions(plugin_id: int, db: DbSession, admin: ActiveAdmin):
            from app.plugins.version_manager import VersionManager

            manager = VersionManager(db)
            versions = await manager.list_versions(plugin_id)
            return success(data=versions)

        @self.router.post("/{plugin_id}/upgrade")
        @action_update("action.plugin.upgrade")
        async def upgrade_plugin(
            plugin_id: int,
            file: UploadFile = File(...),
            db: DbSession = None,
            admin: ActiveAdmin = None,
        ):
            from app.plugins.package_security import (
                ensure_package_size_limit,
                extract_plugin_zip_safely,
            )
            from app.plugins.version_manager import VersionManager

            with tempfile.TemporaryDirectory() as tmp_dir:
                safe_filename = (
                    Path(file.filename).name if file.filename else "plugin.zip"
                )
                tmp_path = Path(tmp_dir) / safe_filename
                with open(tmp_path, "wb") as f:
                    content = await file.read()
                    ensure_package_size_limit(len(content))
                    f.write(content)

                extract_dir = Path(tmp_dir) / "extracted"
                plugin_dir = extract_plugin_zip_safely(tmp_path, extract_dir)

                manager = VersionManager(db)
                await manager.upgrade(plugin_id, plugin_dir)
                return success(data={"message": _("plugin.upgraded")})

        @self.router.post("/{plugin_id}/rollback")
        @action_update("action.plugin.rollback")
        async def rollback_plugin(
            plugin_id: int,
            body: PluginRollbackBody,
            db: DbSession = None,
            admin: ActiveAdmin = None,
        ):
            from app.plugins.version_manager import VersionManager

            manager = VersionManager(db)
            await manager.rollback(plugin_id, body.target_version)
            return success(
                data={
                    "message": _("plugin.rolled_back_to").format(
                        version=body.target_version,
                    )
                }
            )

        # ── 企业分配 / Tenant Assignment ──

        @self.router.get("/{plugin_id}/tenants")
        @action_read("action.plugin.tenants")
        async def list_tenant_assignments(
            plugin_id: int, db: DbSession, admin: ActiveAdmin
        ):
            repo = self.get_service(db).repo
            assignments = await repo.get_tenant_assignments(plugin_id)
            return success(data=[a.to_dict() for a in assignments])

        @self.router.post("/{plugin_id}/tenants")
        @action_update("action.plugin.assign_tenants")
        async def assign_tenants(
            plugin_id: int,
            body: PluginAssignTenantsBody,
            db: DbSession = None,
            admin: ActiveAdmin = None,
        ):
            service = self.get_service(db)
            count = await service.assign_tenants(plugin_id, body.tenant_ids)
            return success(data={"assigned": count})

        @self.router.delete("/{plugin_id}/tenants/{tenant_id}")
        @action_update("action.plugin.unassign_tenant")
        async def unassign_tenant(
            plugin_id: int,
            tenant_id: int,
            db: DbSession = None,
            admin: ActiveAdmin = None,
        ):
            service = self.get_service(db)
            await service.unassign_tenant(plugin_id, tenant_id)
            return deleted()

        # ── License ──

        @self.router.get("/{plugin_id}/license")
        @action_read("action.plugin.view_license")
        async def get_license_status(
            plugin_id: int,
            db: DbSession = None,
            admin: ActiveAdmin = None,
        ):
            from app.plugins.license import get_license_status_by_id

            license_info = await get_license_status_by_id(plugin_id, db)
            return success(data=license_info)

        @self.router.post("/{plugin_id}/activate-license")
        @action_update("action.plugin.activate_license")
        async def activate_license(
            plugin_id: int,
            body: PluginActivateLicenseBody,
            db: DbSession = None,
            admin: ActiveAdmin = None,
        ):
            from app.plugins.license import activate_license as do_activate

            result = await do_activate(plugin_id, body.license_key, db)
            if not result.get("success"):
                from app.exceptions.base import BusinessException

                raise BusinessException(
                    message=result.get("message", _("plugin.error.activation_failed"))
                )
            return success(data=result)

        @self.router.post("/{plugin_id}/activate-trial")
        @action_update("action.plugin.activate_trial")
        async def activate_trial(
            plugin_id: int,
            db: DbSession = None,
            admin: ActiveAdmin = None,
        ):
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
            from app.plugins.license import revoke_license as do_revoke

            await do_revoke(plugin_id, db)
            return deleted()

        # ── AI 功能绑定 / AI Feature Binding ──

        @self.router.get("/{plugin_id}/ai-features")
        @action_read("action.plugin.ai_features")
        async def list_ai_features(plugin_id: int, db: DbSession, admin: ActiveAdmin):
            """获取插件 AI 功能列表及其 Agent 绑定 / Get plugin AI feature list and their Agent bindings"""
            plugin = await self.get_service(db).get_by_id(plugin_id)
            if not plugin:
                from app.exceptions.base import NotFoundException

                raise NotFoundException(
                    message=_("plugin.error.not_found_by_id").format(
                        plugin_id=plugin_id,
                    )
                )
            assignments = await PluginReadModelService(db).list_ai_feature_assignments(
                plugin.name
            )
            return success(data=[a.to_dict() for a in assignments])

        # 插件 AI 功能绑定仅能通过「AI 功能分配」/admin/ai/agent-assignments 修改，不在此提供 PUT，避免双入口。
        # Plugin AI bindings are edited only via AI Feature Assignment; no PUT here to keep a single entry point.

        # ── 备份 / Backup ──

        @self.router.get("/{plugin_id}/backups")
        @action_read("action.plugin.read")
        async def list_backups(plugin_id: int, db: DbSession, admin: ActiveAdmin):
            """列出插件的所有备份记录 / List all backup records for the plugin"""
            import asyncio as _asyncio

            from app.exceptions.base import NotFoundException
            from app.plugins.backup import list_backups as _list

            plugin = await self.get_service(db).get_by_id(plugin_id)
            if not plugin:
                raise NotFoundException(
                    message=_("plugin.error.not_found_by_id").format(
                        plugin_id=plugin_id,
                    )
                )
            backups = await _asyncio.to_thread(_list, plugin.name)
            return success(data=backups)

        @self.router.delete("/{plugin_id}/backups/{backup_name}")
        @action_delete("action.plugin.uninstall")
        async def delete_backup(
            plugin_id: int, backup_name: str, db: DbSession, admin: ActiveAdmin
        ):
            """删除指定备份（仅允许删除该插件的备份） / Delete specified backup (only backups for this plugin are allowed)"""
            import re as _re

            from app.exceptions.base import NotFoundException, ValidationException
            from app.plugins.backup import BACKUPS_DIR

            # 安全校验：backup_name 只允许 [版本]_[时间戳] 格式，防路径穿越 / Security check: backup_name only allows [version]_[timestamp] format, prevents path traversal
            if not _re.match(r"^[a-zA-Z0-9._-]+$", backup_name) or ".." in backup_name:
                raise ValidationException(message=_("plugin.error.invalid_backup_name"))

            plugin = await self.get_service(db).get_by_id(plugin_id)
            if not plugin:
                raise NotFoundException(
                    message=_("plugin.error.not_found_by_id").format(
                        plugin_id=plugin_id,
                    )
                )
            backup_path = BACKUPS_DIR / plugin.name / backup_name
            if not backup_path.is_dir():
                raise NotFoundException(message=_("plugin.error.backup_not_found"))

            import shutil as _shutil

            _shutil.rmtree(backup_path)

            # 若该插件已无备份，清理空目录 / If plugin has no backups, clean up empty directory
            plugin_backup_dir = BACKUPS_DIR / plugin.name
            if plugin_backup_dir.is_dir() and not any(plugin_backup_dir.iterdir()):
                plugin_backup_dir.rmdir()

            return deleted()

        # ── 健康 / Health ──

        @self.router.get("/runtime/audit")
        @action_read("action.plugin.health")
        async def plugin_runtime_audit(
            db: DbSession,
            admin: ActiveAdmin,
            plugin_id: int | None = None,
            tenant_id: int | None = None,
        ):
            _admin = admin
            service = _resolve_plugin_audit_service(db)
            report = await service.build_audit_report(
                scope="admin",
                plugin_id=plugin_id,
                tenant_id=tenant_id,
            )
            return success(data=report)

        @self.router.get("/{plugin_id}/health")
        @action_read("action.plugin.health")
        async def get_health(plugin_id: int, db: DbSession, admin: ActiveAdmin):
            from app.plugins.health import PluginHealthMonitor

            plugin = await self.get_service(db).get_by_id(plugin_id)
            if not plugin:
                from app.exceptions.base import NotFoundException

                raise NotFoundException(
                    message=_("plugin.error.not_found_by_id").format(
                        plugin_id=plugin_id,
                    )
                )
            monitor = PluginHealthMonitor(db)
            status = await monitor.get_health_status(plugin.name)
            return success(data=status)


admin_plugin_controller = AdminPluginController()
router = admin_plugin_controller.router
