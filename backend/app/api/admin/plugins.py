"""
插件管理 Controller（管理端）
"""

import re
import shutil
import tempfile
from pathlib import Path

from fastapi import File, UploadFile
from pydantic import BaseModel as PydanticBaseModel
from pydantic import Field

from app.core.base_controller import GlobalController
from app.core.deps import ActiveAdmin, DbSession, QueryParams
from app.core.logging import LogManager
from app.core.response import created, deleted, paginated, success
from app.enums.rbac import PermissionScope
from app.rbac.decorators import (
    MenuConfig,
    action_create,
    action_delete,
    action_read,
    action_update,
    permission_resource,
)
from app.services.system.plugin_service import PluginService

_SLUG_PATTERN = re.compile(r"^[a-z0-9][a-z0-9\-]*$")
logger = LogManager.get_logger("plugin.admin")


def _sanitize_slug(slug: str) -> None:
    """Validate marketplace slug to prevent path traversal. Raises 400 on invalid slug."""
    if not slug or not _SLUG_PATTERN.match(slug) or len(slug) > 128:
        from app.exceptions.base import ValidationException
        raise ValidationException(
            message=f"Invalid marketplace slug: '{slug}'. Only lowercase letters, digits and hyphens allowed.",
        )


class PluginConfigBody(PydanticBaseModel):
    config: dict = Field(default_factory=dict)


class PluginCapabilitiesBody(PydanticBaseModel):
    capabilities: list[str] = Field(default_factory=list)


class PluginAssignTenantsBody(PydanticBaseModel):
    tenant_ids: list[int] = Field(default_factory=list)


class PluginActivateLicenseBody(PydanticBaseModel):
    license_key: str = ""


class PluginBindAiFeatureBody(PydanticBaseModel):
    agent_id: int | None = None


class PluginRollbackBody(PydanticBaseModel):
    target_version: str = ""


class MenuOverrideItem(PydanticBaseModel):
    """Single menu override: which parent to mount under"""
    name: str = Field(..., description="Menu name from plugin.yaml")
    parent: str = Field(..., description="Admin parent menu code (e.g. system_mgmt)")
    tenant_parent: str | None = Field(None, description="Tenant parent menu code (for admin_and_all scope)")


class PluginMenuConfigBody(PydanticBaseModel):
    """Admin-configurable menu placement overrides"""
    menu_overrides: list[MenuOverrideItem] = Field(default_factory=list)


class PluginEnableBody(PydanticBaseModel):
    """Optional body for enable endpoint with menu config"""
    menu_overrides: list[MenuOverrideItem] = Field(default_factory=list)


class PluginDependencyActionBody(PydanticBaseModel):
    """Install/uninstall dependency switches"""
    python: bool = True
    npm: bool = True
    force: bool = False


@permission_resource(
    resource="plugin",
    name="menu.admin.plugin",
    scope=PermissionScope.ADMIN_ONLY,
    menu=MenuConfig(
        icon="lucide:puzzle",
        path="/plugins",
        component="admin/plugins/index",
        parent="system_maintenance",
        sort_order=60,
    ),
)
class AdminPluginController(GlobalController):
    prefix = "/plugins"
    tags = ["插件管理"]
    service_class = PluginService

    def _register_routes(self):

        # ── 依赖查询 ──

        @self.router.get("/{plugin_id}/dependents")
        @action_read("action.plugin.read")
        async def get_plugin_dependents(plugin_id: int, db: DbSession, admin: ActiveAdmin):
            """获取依赖此插件的插件列表"""
            from app.plugins.lifecycle import PluginLifecycle

            lifecycle = PluginLifecycle(db)
            dependents = await lifecycle.get_dependents(plugin_id)
            return success(data=dependents)

        @self.router.get("/{plugin_id}/dependencies")
        @action_read("action.plugin.read")
        async def get_plugin_dependencies(plugin_id: int, db: DbSession, admin: ActiveAdmin):
            """获取此插件的依赖插件列表"""
            from app.plugins.lifecycle import PluginLifecycle

            lifecycle = PluginLifecycle(db)
            dependencies = await lifecycle.get_dependencies(plugin_id)
            return success(data=dependencies)

        @self.router.post("/{plugin_id}/dependencies/install")
        @action_update("action.plugin.update")
        async def install_plugin_dependencies(
            plugin_id: int,
            db: DbSession,
            admin: ActiveAdmin,
            body: PluginDependencyActionBody | None = None,
        ):
            """显式安装插件依赖（不改变插件状态）"""
            service = self.get_service(db)
            payload = body or PluginDependencyActionBody()
            result = await service.install_plugin_dependencies(
                plugin_id,
                install_python=payload.python,
                install_npm=payload.npm,
            )
            return success(data=result)

        @self.router.post("/{plugin_id}/dependencies/uninstall")
        @action_update("action.plugin.update")
        async def uninstall_plugin_dependencies(
            plugin_id: int,
            db: DbSession,
            admin: ActiveAdmin,
            body: PluginDependencyActionBody | None = None,
        ):
            """显式卸载插件依赖（不卸载插件本体）"""
            from app.exceptions.base import ValidationException

            service = self.get_service(db)
            payload = body or PluginDependencyActionBody()
            if payload.force:
                raise ValidationException(
                    message=(
                        "Force dependency uninstall is disabled for safety. "
                        "Disable plugin first."
                    ),
                )
            result = await service.uninstall_plugin_dependencies(
                plugin_id,
                uninstall_python=payload.python,
                uninstall_npm=payload.npm,
                force=False,
            )
            return success(data=result)

        # ── 前端插槽查询 ──

        @self.router.get("/slots")
        @action_read("action.plugin.list")
        async def get_plugin_slots(db: DbSession, admin: ActiveAdmin):
            """
            获取所有已启用插件的前端插槽数据（admin 端）。

            返回格式：
            {
              "header_widgets": [...],
              "dashboard_widgets": [...],
              "settings_tabs": [...],
              "floating_panels": [...],
              "standalone_pages": [...],
              "notification_ui": [...]
            }

            前端 pluginSlotsStore 启动时调用此接口，驱动各插槽渲染。
            """
            from app.plugins.loader import PluginLoader
            from app.plugins.registry import ExtensionRegistry

            registry = ExtensionRegistry.get_instance()
            grouped = registry.get_frontend_slots_grouped(scope="admin")

            plugin_names = {
                slot.get("plugin_name")
                for slots in grouped.values()
                for slot in slots
                if slot.get("plugin_name")
            }

            loader = PluginLoader()
            plugin_styles: dict[str, list[str]] = {}
            for plugin_name in plugin_names:
                styles: list[str] = []
                try:
                    manifest = loader.load_manifest(plugin_name)
                    frontend = (
                        manifest.extensions.frontend
                        if manifest.extensions
                        else None
                    )
                    if frontend and frontend.admin:
                        styles = list(frontend.admin.styles or [])
                except Exception:
                    styles = []
                plugin_styles[plugin_name] = styles

            return success(
                data={
                    **grouped,
                    "plugin_styles": plugin_styles,
                }
            )

        # ── 更新检查 ──

        @self.router.get("/updates")
        @action_read("action.plugin.list")
        async def check_updates(db: DbSession, admin: ActiveAdmin):
            """检查已安装插件的可用更新"""
            from app.plugins.update_checker import check_updates as _check

            updates = await _check(db)
            return success(data=updates)

        # ── 插件市场 ──

        @self.router.post("/marketplace/test-connection")
        @action_read("action.plugin.list")
        async def marketplace_test_connection(
            db: DbSession,
            admin: ActiveAdmin,
            source_url: str = "",
        ):
            """测试市场镜像源连通性"""
            import time as _time

            import httpx as _httpx

            if not source_url:
                from app.plugins.marketplace import _DEFAULT_GITHUB_URL
                source_url = _DEFAULT_GITHUB_URL

            url = f"{source_url.rstrip('/')}/registry.json"
            try:
                start = _time.perf_counter()
                async with _httpx.AsyncClient(timeout=5.0) as client:
                    resp = await client.head(url)
                latency_ms = int((_time.perf_counter() - start) * 1000)
                return success(data={
                    "ok": resp.status_code < 400,
                    "status_code": resp.status_code,
                    "latency_ms": latency_ms,
                })
            except Exception as exc:
                return success(data={
                    "ok": False,
                    "error": str(exc),
                    "latency_ms": -1,
                })

        @self.router.get("/marketplace")
        @action_read("action.plugin.list")
        async def marketplace_list(
            db: DbSession,
            admin: ActiveAdmin,
            category: str = "",
            sort: str = "-downloads",
            search: str = "",
            page_number: int = 1,
            page_size: int = 20,
        ):
            """插件市场列表（搜索/分类/排序/分页）"""
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

            return paginated(items=page_items, total=total, page=page_number, page_size=page_size)

        @self.router.get("/marketplace/{slug}")
        @action_read("action.plugin.list")
        async def marketplace_detail(slug: str, db: DbSession, admin: ActiveAdmin):
            """插件市场详情"""
            from app.plugins.marketplace import MarketplaceClient

            client = MarketplaceClient(db)
            detail = await client.fetch_plugin_detail(slug)
            if not detail:
                from app.plugins.exceptions import PluginNotFoundError
                raise PluginNotFoundError(message=f"Plugin '{slug}' not found in marketplace")

            readme = await client.fetch_readme(slug)
            detail["readme"] = readme

            # 兼容性检查
            compat = detail.get("compatibility", {})
            detail["compatibility_ok"] = True
            if compat.get("platform_version"):
                # 简单字符串比较（后续可改为 semver）
                detail["platform_version_required"] = compat["platform_version"]

            return success(data=detail)

        @self.router.post("/marketplace/{slug}/install")
        @action_create("action.plugin.install")
        async def marketplace_preview_install(
            slug: str, db: DbSession = None, admin: ActiveAdmin = None,
        ):
            """市场安装预览（下载+解压+生成预览，不执行安装）"""
            from app.plugins.marketplace import MarketplaceClient

            client = MarketplaceClient(db)
            detail = await client.fetch_plugin_detail(slug)
            if not detail:
                from app.plugins.exceptions import PluginNotFoundError
                raise PluginNotFoundError(message=f"Plugin '{slug}' not found in marketplace")

            version = detail.get("version", "1.0.0")
            zip_path = await client.download_plugin(slug, version)

            # 解压并生成预览
            from app.plugins.loader import PluginLoader
            from app.plugins.package_security import extract_plugin_zip_safely
            from app.plugins.preview import generate_preview

            _sanitize_slug(slug)
            try:
                extract_dir = zip_path.parent / "extracted"
                plugin_dir = extract_plugin_zip_safely(zip_path, extract_dir)
                loader = PluginLoader(plugins_dir=plugin_dir.parent)
                preview = await generate_preview(plugin_dir, loader)
                return success(data=preview.model_dump())
            finally:
                shutil.rmtree(zip_path.parent, ignore_errors=True)

        @self.router.post("/marketplace/{slug}/confirm-install")
        @action_create("action.plugin.install")
        async def marketplace_confirm_install(
            slug: str,
            body: PluginConfigBody,
            db: DbSession = None,
            admin: ActiveAdmin = None,
        ):
            """确认从市场安装（下载+安装，设置 install_source=marketplace）"""
            from app.enums.plugin import PluginInstallSourceEnum
            from app.plugins.marketplace import MarketplaceClient

            client = MarketplaceClient(db)
            detail = await client.fetch_plugin_detail(slug)
            if not detail:
                from app.plugins.exceptions import PluginNotFoundError
                raise PluginNotFoundError(message=f"Plugin '{slug}' not found in marketplace")

            version = detail.get("version", "1.0.0")
            zip_path = await client.download_plugin(slug, version)

            from app.plugins.loader import PluginLoader
            from app.plugins.package_security import extract_plugin_zip_safely

            _sanitize_slug(slug)
            try:
                extract_dir = zip_path.parent / "extracted"
                plugin_dir = extract_plugin_zip_safely(zip_path, extract_dir)

                loader = PluginLoader()
                manifest = loader.load_manifest_from_path(plugin_dir)
                logger.info(
                    "Marketplace confirm install: slug=%s plugin=%s",
                    slug,
                    manifest.name,
                )
                service = self.get_service(db)
                # 直接从 staging 目录安装，生命周期层负责复制与回滚，避免预拷贝造成脏目录残留
                plugin = await service.install_from_path(plugin_dir, body.config)

                # 更新 install_source 和 marketplace_slug
                plugin.install_source = PluginInstallSourceEnum.MARKETPLACE.value
                plugin.marketplace_slug = slug
                await db.flush()

                return created(data=plugin.to_dict())
            finally:
                shutil.rmtree(zip_path.parent, ignore_errors=True)

        @self.router.get("/menu-parent-options")
        @action_read("action.plugin.list")
        async def get_menu_parent_options(db: DbSession, admin: ActiveAdmin):
            """
            获取可用的父级菜单树，供插件菜单挂载位置选择。

            同时返回 admin 和 tenant 两侧的菜单树（多级嵌套），
            前端可按插件菜单的 scope 显示对应分组。
            """
            from sqlalchemy import select

            from app.core.i18n import translate
            from app.models.auth.permission import Permission

            # 加载所有启用的菜单权限（admin + tenant）
            result = await db.execute(
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
                """'menu:admin.system_mgmt' → 'system_mgmt'"""
                return code.rsplit(".", 1)[-1] if "." in code else code

            def _label(perm: Permission) -> str:
                name_key = perm.name or ""
                if "." in name_key:
                    t = translate(name_key)
                    return t if t != name_key else name_key.split(".")[-1]
                return name_key

            # 计算哪些 id 是父节点（有子菜单的目录型节点）
            def _has_menu_children(menus_subset: list, parent_id: int) -> bool:
                return any(m.parent_id == parent_id and m.type == "menu" for m in menus_subset)

            def _build_tree(menus_subset: list, parent_id: int | None) -> list:
                nodes = []
                for m in menus_subset:
                    if m.parent_id == parent_id:
                        children = _build_tree(menus_subset, m.id)
                        # 只保留目录型节点（有子菜单），叶子页面不作为父级候选
                        if not children and not _has_menu_children(menus_subset, m.id):
                            continue
                        node = {
                            "value": _short_name(m.code),
                            "label": _label(m),
                            "icon": m.icon,
                            "code": m.code,
                        }
                        if children:
                            node["children"] = children
                        nodes.append(node)
                return nodes

            # admin 侧：admin_only + admin_and_all
            admin_menus = [m for m in all_menus if m.scope in ("admin_only", "admin_and_all")]
            # tenant 侧：all_tenants + admin_and_all
            tenant_menus = [m for m in all_menus if m.scope in ("all_tenants", "admin_and_all")]

            return success(data={
                "admin": _build_tree(admin_menus, None),
                "tenant": _build_tree(tenant_menus, None),
            })

        @self.router.get("")
        @action_read("action.plugin.list")
        async def list_plugins(db: DbSession, admin: ActiveAdmin, query: QueryParams):
            service = self.get_service(db)
            items, total = await service.query_list(query)

            # 脱敏配置
            from app.plugins.crypto import mask_plugin_config

            result_items = []
            for item in items:
                data = item.to_dict()
                manifest_data = data.get("manifest") or {}
                config_schema = manifest_data.get("config_schema")
                if config_schema and data.get("config"):
                    data["config"] = mask_plugin_config(data["config"], config_schema)
                data["dependency_status"] = service.get_dependency_status(item)
                result_items.append(data)

            return paginated(
                items=result_items, total=total,
                page=query.page, page_size=query.size,
            )

        @self.router.get("/{plugin_id}")
        @action_read("action.plugin.detail")
        async def get_plugin(
            plugin_id: int,
            db: DbSession,
            admin: ActiveAdmin,
            locale: str = "zh-CN",
        ):
            service = self.get_service(db)
            plugin = await service.get_by_id(plugin_id)

            data = plugin.to_dict()

            # 脱敏配置
            from app.plugins.crypto import mask_plugin_config

            manifest_data = data.get("manifest") or {}
            config_schema = manifest_data.get("config_schema")
            if config_schema and data.get("config"):
                data["config"] = mask_plugin_config(data["config"], config_schema)

            data["dependency_status"] = service.get_dependency_status(plugin)

            # 加载 README（按 locale 优先级）
            readme = await service.get_readme(plugin_id, locale=locale)
            data["readme"] = readme

            return success(data=data)

        def _extract_plugin_from_zip(file_content: bytes, filename: str) -> tuple[Path, Path]:
            """
            解压 ZIP 到系统临时目录，返回 (staging_dir, plugin_dir)。
            使用系统临时目录，不在项目内，避免触发 --reload。
            调用方负责清理 staging_dir。
            """
            from app.plugins.package_security import (
                ensure_package_size_limit,
                extract_plugin_zip_safely,
            )

            staging_dir = Path(tempfile.mkdtemp(prefix="novusai_plugin_"))
            safe_filename = Path(filename).name if filename else "plugin.zip"

            ensure_package_size_limit(len(file_content))

            zip_path = staging_dir / safe_filename
            with open(zip_path, "wb") as f:
                f.write(file_content)

            try:
                extract_dir = staging_dir / "extracted"
                plugin_dir = extract_plugin_zip_safely(zip_path, extract_dir)
            except Exception:
                shutil.rmtree(staging_dir, ignore_errors=True)
                raise

            return staging_dir, plugin_dir

        @self.router.post("/preview")
        @action_create("action.plugin.preview")
        async def preview_install(
            file: UploadFile = File(...),
            db: DbSession = None,
            admin: ActiveAdmin = None,
        ):
            """上传 ZIP 分析，返回安装预览（不安装）"""
            from app.plugins.preview import generate_preview

            content = await file.read()
            staging_dir, plugin_dir = _extract_plugin_from_zip(content, file.filename or "plugin.zip")

            try:
                from app.plugins.loader import PluginLoader

                loader = PluginLoader(plugins_dir=plugin_dir.parent)
                preview = await generate_preview(plugin_dir, loader)
                return success(data=preview.model_dump())
            finally:
                shutil.rmtree(staging_dir, ignore_errors=True)

        @self.router.post("/upload")
        @action_create("action.plugin.install")
        async def install_plugin(
            file: UploadFile = File(...),
            db: DbSession = None,
            admin: ActiveAdmin = None,
        ):
            """
            上传 ZIP 并安装插件

            lifecycle.install() 内部负责把文件从 staging_dir 复制到 plugins/{name}/，
            此端点只需解压 + 调用安装逻辑 + 清理临时目录。
            """
            from sqlalchemy import select

            from app.models.system.plugin import Plugin as PluginModel

            content = await file.read()
            staging_dir, plugin_dir = _extract_plugin_from_zip(content, file.filename or "plugin.zip")

            try:
                import yaml

                with open(plugin_dir / "plugin.yaml", encoding="utf-8") as yf:
                    manifest_data = yaml.safe_load(yf)
                plugin_name = manifest_data.get("name", plugin_dir.name)

                # 检查是否已安装（DB 有记录则提示走升级流程）
                existing = await db.execute(
                    select(PluginModel.id).where(
                        PluginModel.name == plugin_name,
                        PluginModel.is_deleted.is_(False),
                    )
                )
                if existing.scalar_one_or_none():
                    from app.exceptions.base import BusinessException
                    raise BusinessException(
                        message=f"Plugin '{plugin_name}' is already installed. "
                                "Please uninstall it first or use the upgrade endpoint.",
                    )

                # lifecycle.install() 内部会把 plugin_dir → plugins/{name}/ 完成文件复制
                service = self.get_service(db)
                plugin = await service.install_from_path(plugin_dir, operator_id=admin.id)
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
            """启用插件（自动安装 pip/npm 依赖，通过 Socket.IO 推送进度）"""
            service = self.get_service(db)

            # 保存管理员配置的菜单挂载位置
            if body and body.menu_overrides:
                plugin = await service.get_by_id(plugin_id)
                config = dict(plugin.config or {})
                config["menu_overrides"] = {
                    item.name: (
                        {"parent": item.parent, "tenant_parent": item.tenant_parent}
                        if item.tenant_parent
                        else {"parent": item.parent}
                    )
                    for item in body.menu_overrides
                }
                plugin.config = config
                await db.flush()

            await service.enable_plugin(plugin_id, operator_id=admin.id)
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
            await service.disable_plugin(plugin_id, force=force, operator_id=admin.id)
            return success(data={"message": "Plugin disabled"})

        @self.router.put("/{plugin_id}/menu-config")
        @action_update("action.plugin.update")
        async def update_menu_config(
            plugin_id: int,
            body: PluginMenuConfigBody,
            db: DbSession,
            admin: ActiveAdmin,
        ):
            """更新插件菜单挂载位置（已启用插件可动态调整）"""
            from app.enums.plugin import PluginStatusEnum
            from app.exceptions.base import BusinessException
            from app.plugins._extension_registrar import (
                get_failed_extensions,
                register_all_extensions,
            )
            from app.plugins.loader import PluginLoader
            from app.plugins.registry import ExtensionRegistry
            from app.rbac.sync import PermissionSyncService

            service = self.get_service(db)
            plugin = await service.get_by_id(plugin_id)

            # 保存新的菜单覆盖配置
            config = dict(plugin.config or {})
            config["menu_overrides"] = {
                item.name: (
                    {"parent": item.parent, "tenant_parent": item.tenant_parent}
                    if item.tenant_parent
                    else {"parent": item.parent}
                )
                for item in body.menu_overrides
            }
            plugin.config = config
            await db.flush()

            # 如果插件已启用，重新注册扩展点 + 同步权限到 DB
            if plugin.status == PluginStatusEnum.ENABLED.value:
                registry = ExtensionRegistry.get_instance()
                registry.unregister_all(plugin.name)

                loader = PluginLoader()
                manifest = loader.load_manifest(plugin.name)
                menu_overrides = config.get("menu_overrides")
                register_all_extensions(registry, manifest, plugin.name, menu_overrides=menu_overrides)

                failed = get_failed_extensions(plugin.name)
                if failed:
                    # fail-close：任一扩展加载失败，撤销本次注册，避免菜单配置“半成功”
                    registry.unregister_all(plugin.name)
                    failed_summary = "; ".join(
                        f"{item['type']}:{item['entry_point']}" for item in failed[:5]
                    )
                    raise BusinessException(
                        message=(
                            f"Menu config update failed: {len(failed)} extension(s) failed to load. "
                            f"{failed_summary}"
                        ),
                    )

                # 仅同步当前插件权限，避免全量 sync 的事务副作用
                sync_service = PermissionSyncService(db)
                await sync_service.sync_plugin_permissions(plugin.name)

            return success(data={"message": "Menu config updated"})

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
            await service.uninstall_plugin(
                plugin_id,
                confirm_data_delete,
                cleanup_dependencies=cleanup_dependencies,
                operator_id=admin.id,
            )
            return deleted()

        @self.router.post("/{plugin_id}/repair")
        @action_update("action.plugin.repair")
        async def repair_plugin(plugin_id: int, db: DbSession, admin: ActiveAdmin):
            """修复插件：重置错误计数并尝试重新恢复（安装依赖 + 注册扩展点）"""
            from app.enums.plugin import PluginStatusEnum
            from app.exceptions.base import BusinessException
            from app.plugins._extension_registrar import (
                get_failed_extensions,
                register_all_extensions,
            )
            from app.plugins.lifecycle import PluginLifecycle, _plugin_lock
            from app.plugins.loader import PluginLoader
            from app.plugins.progress import PluginProgressEmitter
            from app.plugins.registry import ExtensionRegistry

            plugin = await self.get_service(db).get_by_id(plugin_id)

            # 只对 error 或 enabled 状态的插件执行修复
            if plugin.status not in (PluginStatusEnum.ERROR.value, PluginStatusEnum.ENABLED.value):
                raise BusinessException(message="Plugin is not in error or enabled state — repair not needed")

            loader = PluginLoader()
            lifecycle = PluginLifecycle(db)
            registry = ExtensionRegistry.get_instance()
            emitter = PluginProgressEmitter(admin.id, plugin.name, "enable")

            async with _plugin_lock(plugin_id):
                try:
                    manifest = loader.load_manifest(plugin.name)

                    # 安装 Python 依赖
                    if manifest.dependencies.python:
                        await emitter.emit_step("pip", "running", f"Checking {len(manifest.dependencies.python)} Python package(s)...")
                        pip_installed = await lifecycle._install_python_deps(plugin.name, manifest.dependencies.python)
                        if pip_installed:
                            await emitter.emit_step("pip", "success", f"Installed {len(pip_installed)} package(s)")
                        else:
                            await emitter.emit_step("pip", "success", "Python dependencies already satisfied")
                    else:
                        await emitter.emit_step("pip", "success", "No Python dependencies")

                    # 安装前端 npm 依赖
                    frontend_ext = manifest.extensions.frontend if manifest.extensions else None
                    npm_deps = frontend_ext.npm_dependencies if frontend_ext else []
                    if npm_deps:
                        await emitter.emit_step("npm", "running", f"Checking {len(npm_deps)} npm package(s)...")
                        npm_installed = await lifecycle._install_npm_deps(plugin.name, npm_deps)
                        if npm_installed > 0:
                            await emitter.emit_step("npm", "success", f"Installed {npm_installed} npm package(s)")
                        else:
                            await emitter.emit_step("npm", "success", "npm already satisfied (skipped)")
                    else:
                        await emitter.emit_step("npm", "success", "No npm dependencies")

                    # 确保 DB 表存在（DB 重建后表可能丢失）
                    from app.plugins.loader import PLUGINS_DIR as _PLUGINS_DIR
                    migrations_dir = _PLUGINS_DIR / plugin.name / "backend" / "migrations" / "versions"
                    if migrations_dir.is_dir():
                        await emitter.emit_step("alembic", "running", "Ensuring database tables...")
                        try:
                            await lifecycle.run_alembic_upgrade(plugin.name)
                            await emitter.emit_step("alembic", "success", "Database tables verified")
                        except Exception as _alembic_exc:
                            await emitter.emit_step("alembic", "warning", f"DB migration warning: {_alembic_exc}")

                    # 注册扩展点
                    await emitter.emit_step("extensions", "running", "Registering extensions...")
                    menu_overrides = (plugin.config or {}).get("menu_overrides")
                    register_all_extensions(registry, manifest, plugin.name, menu_overrides=menu_overrides)

                    # fail-close：扩展加载失败则中止修复
                    failed = get_failed_extensions(plugin.name)
                    if failed:
                        failed_summary = "; ".join(f"{f['type']}:{f['entry_point']}" for f in failed[:5])
                        plugin.status = PluginStatusEnum.ERROR.value
                        plugin.error_message = f"Repair failed: extension load failed: {failed_summary}"
                        plugin.error_count = (plugin.error_count or 0) + 1
                        await db.flush()
                        await emitter.emit_error(f"{len(failed)} extension(s) failed to load")
                        raise BusinessException(message=f"Repair failed: {len(failed)} extension(s) failed")

                    await emitter.emit_step("extensions", "success", f"Registered {registry.get_registered_count(plugin.name)} extension(s)")

                    # 恢复成功：重置错误，恢复 enabled 状态
                    plugin.status = PluginStatusEnum.ENABLED.value
                    plugin.error_count = 0
                    plugin.error_message = None
                    await db.flush()

                    # 将 permission_registry 内存菜单写入 DB（首次修复时 DB 可能无记录，flush 不 commit）
                    try:
                        from app.rbac.sync import PermissionSyncService
                        perm_sync = PermissionSyncService(db)
                        await perm_sync.sync_plugin_permissions(plugin.name)
                    except Exception as _perm_exc:
                        logger.warning("Repair: permission sync failed for %s: %s", plugin.name, _perm_exc)

                    # 同步启用权限（error 状态下权限可能被禁用）
                    await lifecycle._set_plugin_permissions_enabled(plugin.name, True)

                    await emitter.emit_done(f"Plugin {plugin.name} repaired successfully")
                    return success(data={"message": "Plugin repaired and restored"})

                except BusinessException:
                    raise
                except Exception as exc:
                    plugin.status = PluginStatusEnum.ERROR.value
                    plugin.error_count = (plugin.error_count or 0) + 1
                    plugin.error_message = f"Repair failed: {exc}"
                    await db.flush()
                    await emitter.emit_error(f"Repair failed: {exc}")
                    raise BusinessException(message=f"Repair failed: {exc}") from exc

        @self.router.delete("/{plugin_id}/force-cleanup")
        @action_delete("action.plugin.uninstall")
        async def force_cleanup_orphan(plugin_id: int, db: DbSession, admin: ActiveAdmin):
            """强制清理孤立插件记录（磁盘文件已缺失的 error 状态插件）"""
            from sqlalchemy import delete

            from app.models.system.plugin import Plugin as PluginModel
            from app.models.system.plugin_license import PluginLicense
            from app.models.system.plugin_version import PluginVersion
            from app.models.system.resource_tenant_assignment import (
                ResourceTenantAssignment,
            )
            from app.plugins.loader import PLUGINS_DIR

            plugin = await self.get_service(db).get_by_id(plugin_id)
            plugin_dir = PLUGINS_DIR / plugin.name
            if plugin_dir.exists():
                from app.exceptions.base import BusinessException
                raise BusinessException(
                    message="Plugin files exist on disk. Use normal uninstall instead of force cleanup.",
                )

            await db.execute(delete(PluginVersion).where(PluginVersion.plugin_id == plugin_id))
            await db.execute(
                delete(ResourceTenantAssignment).where(
                    ResourceTenantAssignment.resource_type == "plugin",
                    ResourceTenantAssignment.resource_id == plugin_id,
                )
            )
            await db.execute(delete(PluginLicense).where(PluginLicense.plugin_id == plugin_id))
            await db.execute(delete(PluginModel).where(PluginModel.id == plugin_id))

            # 清理 alembic_version 中的孤立版本戳
            # 由于插件文件已不存在，无法扫描实际 revision ID，退回前缀模糊匹配
            # 注意：LIKE 中 _ 是通配符，需转义 (escape='\\')
            from sqlalchemy import text
            _raw_prefix = plugin.name.replace("-", "_") + "_"
            await db.execute(
                text("DELETE FROM alembic_version WHERE version_num LIKE :prefix"),
                {"prefix": f"{_raw_prefix}%"},
            )

            await db.flush()
            return deleted()

        # ── 配置 ──

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
                    message=f"Unknown capabilities: {unknown}. "
                    f"Valid: {sorted(_VALID_CAPABILITIES)}",
                )
            service = self.get_service(db)
            await service.update_capabilities(plugin_id, body.capabilities)
            return success(data={"message": "Capabilities updated"})

        # ── 图标上传 ──

        @self.router.post("/{plugin_id}/icon")
        @action_update("action.plugin.icon")
        async def upload_icon(
            plugin_id: int,
            file: UploadFile = File(...),
            db: DbSession = None,
            admin: ActiveAdmin = None,
        ):
            """上传插件图标（PNG/SVG/JPG）"""
            from app.plugins.loader import PLUGINS_DIR

            service = self.get_service(db)
            plugin = await service.get_by_id(plugin_id)

            # 验证文件类型
            allowed = {".png", ".svg", ".jpg", ".jpeg", ".webp"}
            suffix = Path(file.filename).suffix.lower() if file.filename else ".png"
            if suffix not in allowed:
                from app.exceptions.base import ValidationException
                raise ValidationException(message="Only PNG/SVG/JPG/WebP images are allowed")

            # 验证文件大小（最大 2MB）
            _ICON_MAX_SIZE = 2 * 1024 * 1024
            content = await file.read()
            if len(content) > _ICON_MAX_SIZE:
                from app.exceptions.base import ValidationException
                raise ValidationException(
                    message=f"Icon file too large ({len(content)} bytes). Maximum size is 2MB.",
                )

            # 保存文件
            icon_filename = f"icon{suffix}"
            icon_path = PLUGINS_DIR / plugin.name / icon_filename
            with open(icon_path, "wb") as f:
                f.write(content)

            # 更新 icon 字段为插件静态资源路径
            plugin.icon = f"/plugin-assets/{plugin.name}/{icon_filename}"
            await db.flush()

            return success(data={"icon": plugin.icon})

        # ── 版本 ──

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
                safe_filename = Path(file.filename).name if file.filename else "plugin.zip"
                tmp_path = Path(tmp_dir) / safe_filename
                with open(tmp_path, "wb") as f:
                    content = await file.read()
                    ensure_package_size_limit(len(content))
                    f.write(content)

                extract_dir = Path(tmp_dir) / "extracted"
                plugin_dir = extract_plugin_zip_safely(tmp_path, extract_dir)

                manager = VersionManager(db)
                await manager.upgrade(plugin_id, plugin_dir)
                return success(data={"message": "Plugin upgraded"})

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
            return success(data={"message": f"Rolled back to {body.target_version}"})

        # ── 租户分配 ──

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
            plugin_id: int, tenant_id: int,
            db: DbSession = None, admin: ActiveAdmin = None,
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
                raise BusinessException(message=result.get("message", "Activation failed"))
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

            await create_trial_license(plugin_id, trial_days=14, db=db)
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

        # ── AI 功能绑定 ──

        @self.router.get("/{plugin_id}/ai-features")
        @action_read("action.plugin.ai_features")
        async def list_ai_features(plugin_id: int, db: DbSession, admin: ActiveAdmin):
            """获取插件 AI 功能列表及其 Agent 绑定"""
            from sqlalchemy import select

            from app.models.system.agent_assignment import SystemAgentAssignment

            plugin = await self.get_service(db).get(plugin_id)
            result = await db.execute(
                select(SystemAgentAssignment).where(
                    SystemAgentAssignment.feature_code.like(f"plugin.{plugin.name}.%"),
                    SystemAgentAssignment.is_deleted.is_(False),
                )
            )
            assignments = result.scalars().all()
            return success(data=[a.to_dict() for a in assignments])

        @self.router.put("/{plugin_id}/ai-features/{assignment_id}")
        @action_update("action.plugin.bind_ai")
        async def bind_ai_feature(
            plugin_id: int,
            assignment_id: int,
            body: PluginBindAiFeatureBody,
            db: DbSession = None,
            admin: ActiveAdmin = None,
        ):
            """为插件 AI 功能绑定 Agent"""
            from sqlalchemy import select, update

            from app.models.system.agent_assignment import SystemAgentAssignment
            from app.models.system.plugin import Plugin as PluginModel

            plugin_name_result = await db.execute(
                select(PluginModel.name).where(
                    PluginModel.id == plugin_id,
                    PluginModel.is_deleted.is_(False),
                )
            )
            plugin_name = plugin_name_result.scalar_one_or_none()
            if not plugin_name:
                from app.exceptions.base import NotFoundException
                raise NotFoundException(message="Plugin not found")

            result = await db.execute(
                update(SystemAgentAssignment).where(
                    SystemAgentAssignment.id == assignment_id,
                    SystemAgentAssignment.feature_code.like(f"plugin.{plugin_name}.%"),
                    SystemAgentAssignment.is_deleted.is_(False),
                ).values(agent_id=body.agent_id)
            )
            if result.rowcount == 0:
                from app.exceptions.base import NotFoundException
                raise NotFoundException(message="AI feature assignment not found for this plugin")
            await db.flush()
            return success(data={"message": "AI feature binding updated"})

        # ── 备份 ──

        @self.router.get("/{plugin_id}/backups")
        @action_read("action.plugin.read")
        async def list_backups(plugin_id: int, db: DbSession, admin: ActiveAdmin):
            """列出插件的所有备份记录"""
            from app.plugins.backup import list_backups as _list

            plugin = await self.get_service(db).get_by_id(plugin_id)
            backups = _list(plugin.name)
            return success(data=backups)

        @self.router.delete("/{plugin_id}/backups/{backup_name}")
        @action_delete("action.plugin.uninstall")
        async def delete_backup(plugin_id: int, backup_name: str, db: DbSession, admin: ActiveAdmin):
            """删除指定备份（仅允许删除该插件的备份）"""
            import re as _re

            from app.exceptions.base import NotFoundException, ValidationException
            from app.plugins.backup import BACKUPS_DIR

            # 安全校验：backup_name 只允许 [版本]_[时间戳] 格式，防路径穿越
            if not _re.match(r'^[a-zA-Z0-9._-]+$', backup_name) or '..' in backup_name:
                raise ValidationException(message="Invalid backup name")

            plugin = await self.get_service(db).get_by_id(plugin_id)
            backup_path = BACKUPS_DIR / plugin.name / backup_name
            if not backup_path.is_dir():
                raise NotFoundException(message="Backup not found")

            import shutil as _shutil
            _shutil.rmtree(backup_path)

            # 若该插件已无备份，清理空目录
            plugin_backup_dir = BACKUPS_DIR / plugin.name
            if plugin_backup_dir.is_dir() and not any(plugin_backup_dir.iterdir()):
                plugin_backup_dir.rmdir()

            return deleted()

        # ── 健康 ──

        @self.router.get("/{plugin_id}/health")
        @action_read("action.plugin.health")
        async def get_health(plugin_id: int, db: DbSession, admin: ActiveAdmin):
            from app.plugins.health import PluginHealthMonitor

            plugin = await self.get_service(db).get(plugin_id)
            monitor = PluginHealthMonitor(db)
            status = await monitor.get_health_status(plugin.name)
            return success(data=status)


admin_plugin_controller = AdminPluginController()
router = admin_plugin_controller.router
