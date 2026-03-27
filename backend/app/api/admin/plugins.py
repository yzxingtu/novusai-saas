"""
插件管理 Controller（管理端） / Plugin Management Controller (Admin)
"""

import re
import shutil
import tempfile
from pathlib import Path

from fastapi import File, Response, UploadFile
from pydantic import BaseModel as PydanticBaseModel
from pydantic import Field

from app.core.base_controller import GlobalController
from app.core.deps import ActiveAdmin, DbSession, QueryParams
from app.core.logging import LogManager
from app.core.response import (
    build_public_error_text,
    created,
    deleted,
    paginated,
    resolve_public_error_message,
    success,
)
from app.enums.rbac import PermissionScope
from app.rbac.decorators import (
    MenuConfig,
    action_create,
    action_delete,
    action_read,
    action_update,
    permission_resource,
)
from app.rbac.services import PermissionService
from app.services.system.plugin_service import PluginService

_SLUG_PATTERN = re.compile(r"^[a-z0-9][a-z0-9\-]*$")
logger = LogManager.get_logger("plugin.admin")


def _sanitize_slug(slug: str) -> None:
    """校验 marketplace slug 防止路径遍历，无效时抛 400 / Validate marketplace slug to prevent path traversal. Raises 400 on invalid."""
    if not slug or not _SLUG_PATTERN.match(slug) or len(slug) > 128:
        from app.exceptions.base import ValidationException
        raise ValidationException(
            message=f"Invalid marketplace slug: '{slug}'. Only lowercase letters, digits and hyphens allowed.",
        )


_MENU_CODE_PATTERN = re.compile(r"^[a-z0-9_]+$")
_SEMVER_PATTERN = re.compile(r"^\d+\.\d+\.\d+(?:-[\w.]+)?(?:\+[\w.]+)?$")


class PluginConfigBody(PydanticBaseModel):
    config: dict = Field(default_factory=dict, max_length=65536)


class PluginCapabilitiesBody(PydanticBaseModel):
    capabilities: list[str] = Field(default_factory=list)


class PluginAssignTenantsBody(PydanticBaseModel):
    tenant_ids: list[int] = Field(default_factory=list, max_length=500)


class PluginActivateLicenseBody(PydanticBaseModel):
    license_key: str = Field(default="", max_length=500)


class PluginRollbackBody(PydanticBaseModel):
    target_version: str = Field(default="", pattern=r"^\d+\.\d+\.\d+(?:-[\w.]+)?(?:\+[\w.]+)?$")


class MenuOverrideItem(PydanticBaseModel):
    """单条菜单覆盖：挂载到哪个父级 / Single menu override: which parent to mount under."""
    name: str = Field(..., max_length=100, description="Menu name from plugin.yaml")
    parent: str = Field(..., max_length=100, pattern=r"^[a-z0-9_-]+$", description="Admin parent menu code (e.g. system_mgmt)")
    tenant_parent: str | None = Field(None, max_length=100, pattern=r"^[a-z0-9_-]+$", description="Tenant parent menu code (when menu scope is both)")


class PluginMenuConfigBody(PydanticBaseModel):
    """管理员可配置的菜单位置覆盖 / Admin-configurable menu placement overrides."""
    menu_overrides: list[MenuOverrideItem] = Field(default_factory=list)


class PluginEnableBody(PydanticBaseModel):
    """启用接口的可选 body（含菜单配置）/ Optional body for enable endpoint with menu config."""
    menu_overrides: list[MenuOverrideItem] = Field(default_factory=list)


class PluginDependencyActionBody(PydanticBaseModel):
    """安装/卸载依赖开关 / Install/uninstall dependency switches."""
    python: bool = True
    force: bool = False


@permission_resource(
    resource="plugin",
    name="menu.admin.plugin",
    scope=PermissionScope.ADMIN,
    parent_resource="system_maintenance",
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
    tags = ["Plugin Management"]
    service_class = PluginService

    def _register_routes(self):

        # ── 依赖查询 / Dependency Query ──

        @self.router.get("/{plugin_id}/dependents")
        @action_read("action.plugin.read")
        async def get_plugin_dependents(plugin_id: int, db: DbSession, admin: ActiveAdmin):
            """获取依赖此插件的插件列表 / Get plugins that depend on this plugin"""
            from app.plugins.lifecycle import PluginLifecycle

            lifecycle = PluginLifecycle(db)
            dependents = await lifecycle.get_dependents(plugin_id)
            return success(data=dependents)

        @self.router.get("/{plugin_id}/dependencies")
        @action_read("action.plugin.read")
        async def get_plugin_dependencies(plugin_id: int, db: DbSession, admin: ActiveAdmin):
            """获取此插件的依赖插件列表 / Get this plugin's dependency list"""
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
            """显式安装插件依赖（不改变插件状态） / Explicitly install plugin dependencies (without changing plugin status)"""
            service = self.get_service(db)
            payload = body or PluginDependencyActionBody()
            result = await service.install_plugin_dependencies(
                plugin_id,
                install_python=payload.python,
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
            """显式卸载插件依赖（不卸载插件本体） / Explicitly uninstall plugin dependencies (without uninstalling the plugin itself)"""
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
                force=False,
            )
            return success(data=result)

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
            from app.api.shared._plugin_slot_filter import (
                filter_grouped_plugin_slots_by_permission_codes,
            )
            from app.plugins.registry import ExtensionRegistry
            from app.plugins.runtime_gate import evaluate_plugin_runtime_gate

            registry = ExtensionRegistry.get_instance()
            grouped = registry.get_frontend_slots_grouped(scope="admin")
            permission_codes = await PermissionService(db).get_admin_permissions(
                admin
            )

            plugin_names = {
                slot.get("plugin_name")
                for slots in grouped.values()
                for slot in slots
                if slot.get("plugin_name")
            }
            allowed_names: set[str] = set()
            for plugin_name in plugin_names:
                gate = await evaluate_plugin_runtime_gate(
                    db,
                    plugin_name,
                    tenant_id=None,
                    require_enabled=True,
                    enforce_scope=False,
                )
                if gate.allowed:
                    allowed_names.add(plugin_name)

            grouped = {
                slot_key: [
                    slot for slot in slots
                    if slot.get("plugin_name") in allowed_names
                ]
                for slot_key, slots in grouped.items()
            }
            grouped = filter_grouped_plugin_slots_by_permission_codes(
                grouped,
                permission_codes,
            )

            return success(data=grouped)

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
            import ipaddress
            import time as _time
            from urllib.parse import urlparse

            import httpx as _httpx

            if not source_url:
                from app.plugins.marketplace import _DEFAULT_GITHUB_URL
                source_url = _DEFAULT_GITHUB_URL

            _ALLOWED_SCHEMES = {"http", "https"}
            _ALLOWED_HOSTS = {
                "github.com", "raw.githubusercontent.com",
                "gitee.com", "raw.gitee.com",
                "api.github.com", "objects.githubusercontent.com",
            }

            parsed = urlparse(source_url)
            if parsed.scheme not in _ALLOWED_SCHEMES:
                from app.exceptions.base import ValidationException
                raise ValidationException(message="Only http/https URLs are allowed")

            hostname = (parsed.hostname or "").lower()
            try:
                ip = ipaddress.ip_address(hostname)
                if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved:
                    from app.exceptions.base import ValidationException
                    raise ValidationException(message="Private/reserved IP addresses are not allowed")
            except ValueError as exc:
                if hostname not in _ALLOWED_HOSTS:
                    from app.exceptions.base import ValidationException
                    raise ValidationException(
                        message=f"Host '{hostname}' is not in the allowed list. "
                                f"Allowed: {', '.join(sorted(_ALLOWED_HOSTS))}",
                    ) from exc

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
                logger.warning("Marketplace connection test failed for {}: {}", source_url, exc)
                return success(data={
                    "ok": False,
                    "error": "Connection failed. Please check the URL and try again.",
                    "latency_ms": -1,
                })

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
            return paginated(items=page_items, total=total, page=page_number, page_size=page_size)

        @self.router.get("/marketplace/{slug}")
        @action_read("action.plugin.list")
        async def marketplace_detail(slug: str, db: DbSession, admin: ActiveAdmin, response: Response):
            """插件市场详情 / Plugin marketplace detail"""
            from app.plugins.marketplace import MarketplaceClient

            client = MarketplaceClient(db)
            detail = await client.fetch_plugin_detail(slug)
            if not detail:
                from app.plugins.exceptions import PluginNotFoundError
                raise PluginNotFoundError(message=f"Plugin '{slug}' not found in marketplace")

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
            slug: str, db: DbSession = None, admin: ActiveAdmin = None,
        ):
            """市场安装预览（下载+解压+生成预览，不执行安装） / Marketplace install preview (download+extract+generate preview, no actual install)"""
            _sanitize_slug(slug)

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
            from app.plugins.preview import generate_preview
            try:
                extract_dir = zip_path.parent / "extracted"
                plugin_dir = extract_plugin_zip_safely(zip_path, extract_dir)
                loader = PluginLoader(plugins_dir=plugin_dir.parent)
                preview = await generate_preview(plugin_dir, loader, db=db)
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
            """确认从市场安装（下载+安装，设置 install_source=marketplace） / Confirm marketplace install (download+install, set install_source=marketplace)"""
            _sanitize_slug(slug)

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
            try:
                extract_dir = zip_path.parent / "extracted"
                plugin_dir = extract_plugin_zip_safely(zip_path, extract_dir)

                loader = PluginLoader()
                manifest = loader.load_manifest_from_path(plugin_dir)
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
                    db, "biz.plugin_installed",
                    [("admin", admin.id)],
                    data={"plugin_name": plugin.display_name or plugin.name, "version": plugin.version or "1.0.0"},
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
            from sqlalchemy import select

            from app.models.auth.permission import Permission
            from app.rbac.services.permission_service import PermissionService

            # 加载所有启用的菜单权限（admin + tenant） / Load all enabled menu permissions (admin + tenant)
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
                """将 menu:admin.xxx 转为最后一段（如 system_mgmt）/ 'menu:admin.system_mgmt' -> 'system_mgmt'."""
                return code.rsplit(".", 1)[-1] if "." in code else code

            def _label(perm: Permission) -> str:
                name_key = perm.name or ""
                translated = PermissionService._translate_name(name_key)
                if translated and translated != name_key:
                    return translated
                if "." in name_key:
                    return name_key.split(".")[-1]
                return name_key

            # 计算哪些 id 是父节点（有子菜单的目录型节点） / Determine which ids are parent nodes (directory nodes with child menus)
            def _has_menu_children(menus_subset: list, parent_id: int) -> bool:
                return any(m.parent_id == parent_id and m.type == "menu" for m in menus_subset)

            def _build_tree(menus_subset: list, parent_id: int | None) -> list:
                nodes = []
                for m in menus_subset:
                    if m.parent_id == parent_id:
                        children = _build_tree(menus_subset, m.id)
                        # 只保留目录型节点（有子菜单），叶子页面不作为父级候选 / Only keep directory nodes (with child menus), leaf pages are not parent candidates
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

            admin_menus = [
                m for m in all_menus
                if m.scope in (PermissionScope.ADMIN.value, PermissionScope.BOTH.value)
            ]
            tenant_menus = [
                m for m in all_menus
                if m.scope in (PermissionScope.TENANT.value, PermissionScope.BOTH.value)
            ]

            return success(data={
                "admin": _build_tree(admin_menus, None),
                "tenant": _build_tree(tenant_menus, None),
            })

        @self.router.get("")
        @action_read("action.plugin.list")
        async def list_plugins(db: DbSession, admin: ActiveAdmin, query: QueryParams):
            service = self.get_service(db)
            items, total = await service.query_list(query)

            # 脱敏配置 / Mask sensitive config
            from app.plugins.crypto import mask_plugin_config

            result_items = []
            for item in items:
                data = item.to_dict()
                manifest_data = data.get("manifest") or {}
                config_schema = manifest_data.get("config_schema")
                if config_schema and data.get("config"):
                    data["config"] = mask_plugin_config(data["config"], config_schema)
                data["dependency_status"] = await service.get_dependency_status(item)
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
            if plugin is None:
                from app.exceptions import NotFoundException
                raise NotFoundException(message=f"Plugin #{plugin_id} not found")

            data = plugin.to_dict()

            # 脱敏配置 / Mask sensitive config
            from app.plugins.crypto import mask_plugin_config

            manifest_data = data.get("manifest") or {}
            config_schema = manifest_data.get("config_schema")
            if config_schema and data.get("config"):
                data["config"] = mask_plugin_config(data["config"], config_schema)

            data["dependency_status"] = await service.get_dependency_status(plugin)

            # 加载 README（按 locale 优先级） / Load README (by locale priority)
            readme = await service.get_readme(plugin_id, locale=locale)
            data["readme"] = readme

            return success(data=data)

        def _extract_plugin_from_zip(file_content: bytes, filename: str) -> tuple[Path, Path]:
            """
            解压 ZIP 到系统临时目录，返回 (staging_dir, plugin_dir) / Extract ZIP to temp dir, return (staging_dir, plugin_dir).

            使用系统临时目录，不在项目内，避免触发 --reload。
            Uses system temp directory, not within project, to avoid triggering --reload.
            调用方负责清理 staging_dir。
            Caller is responsible for cleaning up staging_dir.
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
            """上传 ZIP 分析，返回安装预览（不安装） / Upload ZIP for analysis, return install preview (no installation)"""
            from app.plugins.preview import generate_preview

            content = await file.read()
            staging_dir, plugin_dir = _extract_plugin_from_zip(content, file.filename or "plugin.zip")

            try:
                from app.plugins.loader import PluginLoader

                loader = PluginLoader(plugins_dir=plugin_dir.parent)
                preview = await generate_preview(plugin_dir, loader, db=db)
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
            上传 ZIP 并安装插件 / Upload ZIP and install plugin

            lifecycle.install() 内部负责把文件从 staging_dir 复制到 plugins/{name}/，
            this endpoint only needs to extract + call install logic + clean up temp directory.
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

                # 检查是否已安装（DB 有记录则提示走升级流程） / Check if already installed (prompt upgrade if DB record exists)
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

                # lifecycle.install() 内部会把 plugin_dir -> plugins/{name}/ 完成文件复制 / lifecycle.install() copies plugin_dir -> plugins/{name}/ internally
                service = self.get_service(db)
                plugin = await service.install_from_path(plugin_dir, operator_id=admin.id)

                from app.services.common.notification_service import notify
                await notify(
                    db, "biz.plugin_installed",
                    [("admin", admin.id)],
                    data={"plugin_name": plugin.display_name or plugin.name, "version": plugin.version or "1.0.0"},
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

            plugin = await service.get_by_id(plugin_id)
            from app.services.common.notification_service import notify
            await notify(
                db, "biz.plugin_enabled",
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
                db, "biz.plugin_disabled",
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
                            fallback_message="Menu config update failed",
                        ),
                    ) from exc

                # 仅同步当前插件权限，避免全量 sync 的事务副作用 / Only sync current plugin permissions to avoid side effects of full sync
                sync_service = PermissionSyncService(db)
                await sync_service.sync_plugin_permissions(plugin.name)

            return success(data={"message": "Menu config updated"})

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
            return success(data={"message": "Manifest synced"})

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
                return deleted(message=f"Plugin #{plugin_id} already removed")
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
                db, "biz.plugin_uninstalled",
                [("admin", admin.id)],
                data={"plugin_name": plugin_display, "version": plugin_version},
            )

            return deleted()

        @self.router.post("/{plugin_id}/repair")
        @action_update("action.plugin.repair")
        async def repair_plugin(plugin_id: int, db: DbSession, admin: ActiveAdmin):
            """修复插件：重置错误计数并尝试重新恢复（安装 Python 依赖 + 注册扩展点） / Repair plugin: reset error count and attempt recovery (install Python deps + register extensions)"""
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

            # 只对 error 或 enabled 状态的插件执行修复 / Only repair plugins in error or enabled state
            if plugin.status not in (PluginStatusEnum.ERROR.value, PluginStatusEnum.ENABLED.value):
                raise BusinessException(message="Plugin is not in error or enabled state — repair not needed")

            loader = PluginLoader()
            lifecycle = PluginLifecycle(db)
            registry = ExtensionRegistry.get_instance()
            emitter = PluginProgressEmitter(admin.id, plugin.name, "enable")

            async with _plugin_lock(plugin_id):
                async def _fail_close_plugin_runtime() -> None:
                    try:
                        registry.unregister_all(plugin.name)
                    except Exception as cleanup_exc:
                        logger.warning(
                            "Repair: failed to unregister runtime extensions for {}: {}",
                            plugin.name,
                            cleanup_exc,
                        )
                    try:
                        await lifecycle._set_plugin_permissions_enabled(plugin.name, False)
                    except Exception as perm_exc:
                        logger.warning(
                            "Repair: failed to disable permissions for {}: {}",
                            plugin.name,
                            perm_exc,
                        )

                try:
                    manifest = loader.load_manifest(plugin.name)
                    from app.plugins.frontend_contract import (
                        validate_runtime_frontend_contract,
                    )
                    validate_runtime_frontend_contract(loader.plugins_dir / plugin.name, manifest)
                    await lifecycle._assert_plugin_runtime_enable_guards(
                        plugin,
                        manifest,
                        action="repair",
                    )

                    # 安装 Python 依赖 / Install Python dependencies
                    if manifest.dependencies.python:
                        await emitter.emit_step("pip", "running", f"Checking {len(manifest.dependencies.python)} Python package(s)...")
                        pip_installed = await lifecycle._install_python_deps(plugin.name, manifest.dependencies.python)
                        if pip_installed:
                            await emitter.emit_step("pip", "success", f"Installed {len(pip_installed)} package(s)")
                        else:
                            await emitter.emit_step("pip", "success", "Python dependencies already satisfied")
                    else:
                        await emitter.emit_step("pip", "success", "No Python dependencies")

                    # 确保 DB 表存在（DB 重建后表可能丢失） / Ensure DB tables exist (tables may be lost after DB rebuild)
                    from app.plugins.loader import PLUGINS_DIR as _PLUGINS_DIR
                    migrations_dir = _PLUGINS_DIR / plugin.name / "backend" / "migrations" / "versions"
                    if migrations_dir.is_dir():
                        await emitter.emit_step("alembic", "running", "Ensuring database tables...")
                        try:
                            await lifecycle.run_alembic_upgrade(plugin.name)
                            await emitter.emit_step("alembic", "success", "Database tables verified")
                        except Exception as alembic_exc:
                            await emitter.emit_step(
                                "alembic",
                                "error",
                                build_public_error_text(
                                    message="DB migration failed",
                                    exc=alembic_exc,
                                ),
                            )
                            raise

                    # 注册扩展点 / Register extension points
                    await emitter.emit_step("extensions", "running", "Registering extensions...")
                    menu_overrides = (plugin.config or {}).get("menu_overrides")
                    register_all_extensions(registry, manifest, plugin.name, menu_overrides=menu_overrides)

                    # fail-close：扩展加载失败则中止修复 / fail-close: abort repair if extension loading fails
                    failed = get_failed_extensions(plugin.name)
                    if failed:
                        failed_summary = "; ".join(f"{f['type']}:{f['entry_point']}" for f in failed[:5])
                        plugin.status = PluginStatusEnum.ERROR.value
                        plugin.error_message = f"Repair failed: extension load failed: {failed_summary}"
                        plugin.error_count = (plugin.error_count or 0) + 1
                        await _fail_close_plugin_runtime()
                        await db.flush()
                        await emitter.emit_error(f"{len(failed)} extension(s) failed to load")
                        raise BusinessException(message=f"Repair failed: {len(failed)} extension(s) failed")

                    await emitter.emit_step("extensions", "success", f"Registered {registry.get_registered_count(plugin.name)} extension(s)")

                    ext = manifest.extensions
                    if ext.skills:
                        await lifecycle._ensure_plugin_skill_records(
                            plugin.name,
                            manifest,
                            ext.skills,
                            active=True,
                        )
                    if manifest.ai_requirements and manifest.ai_requirements.features:
                        await lifecycle._ensure_plugin_ai_features(
                            plugin.name,
                            manifest.ai_requirements.features,
                        )
                    if ext.notifications:
                        await lifecycle._sync_plugin_notification_templates(
                            plugin.name,
                            ext.notifications,
                        )
                    if ext.tasks:
                        await lifecycle._sync_plugin_task_definitions(
                            plugin.name,
                            ext.tasks,
                        )

                    await lifecycle._restore_plugin_permissions(
                        plugin.name,
                        auto_grant_plans=True,
                    )

                    # 恢复成功：重置错误，恢复 enabled 状态 / Recovery successful: reset errors, restore enabled state
                    plugin.status = PluginStatusEnum.ENABLED.value
                    plugin.error_count = 0
                    plugin.error_message = None
                    await db.flush()

                    await emitter.emit_done(f"Plugin {plugin.name} repaired successfully")
                    return success(data={"message": "Plugin repaired and restored"})

                except BusinessException:
                    raise
                except Exception as exc:
                    plugin.status = PluginStatusEnum.ERROR.value
                    plugin.error_count = (plugin.error_count or 0) + 1
                    plugin.error_message = resolve_public_error_message(
                        exc,
                        fallback_message="Repair failed",
                    )
                    await _fail_close_plugin_runtime()
                    await db.flush()
                    await emitter.emit_error(
                        build_public_error_text(
                            message="Repair failed",
                            exc=exc,
                        )
                    )
                    raise BusinessException(
                        message=resolve_public_error_message(
                            exc,
                            fallback_message="Repair failed",
                        )
                    ) from exc

        @self.router.delete("/{plugin_id}/force-cleanup")
        @action_delete("action.plugin.uninstall")
        async def force_cleanup_orphan(plugin_id: int, db: DbSession, admin: ActiveAdmin):
            """强制清理孤立插件记录（磁盘文件已缺失的 error 状态插件） / Force cleanup orphaned plugin records (error-state plugins with missing disk files)"""
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

            # 清理 alembic_version 中的孤立版本戳 / Clean up orphaned version stamps in alembic_version
            # 由于插件文件已不存在，无法扫描实际 revision ID，退回前缀模糊匹配 / Since plugin files no longer exist, fall back to prefix fuzzy matching
            # 注意：LIKE 中 _ 是通配符，需转义 (escape='\\') / Note: _ is a wildcard in LIKE, needs escaping
            from sqlalchemy import text
            _raw_prefix = plugin.name.replace("-", "_") + "_"
            await db.execute(
                text("DELETE FROM alembic_version WHERE version_num LIKE :prefix"),
                {"prefix": f"{_raw_prefix}%"},
            )

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
                    message=f"Unknown capabilities: {unknown}. "
                    f"Valid: {sorted(_VALID_CAPABILITIES)}",
                )
            service = self.get_service(db)
            await service.update_capabilities(plugin_id, body.capabilities)
            return success(data={"message": "Capabilities updated"})

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
                raise ValidationException(message="Only PNG/SVG/JPG/WebP images are allowed")

            # 验证文件大小（最大 2MB） / Validate file size (max 2MB)
            _ICON_MAX_SIZE = 2 * 1024 * 1024
            content = await file.read()
            if len(content) > _ICON_MAX_SIZE:
                from app.exceptions.base import ValidationException
                raise ValidationException(
                    message=f"Icon file too large ({len(content)} bytes). Maximum size is 2MB.",
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
            from sqlalchemy import select

            from app.models.system.agent_assignment import SystemAgentAssignment

            plugin = await self.get_service(db).get_by_id(plugin_id)
            if not plugin:
                from app.exceptions.base import NotFoundException
                raise NotFoundException(message=f"Plugin #{plugin_id} not found")
            result = await db.execute(
                select(SystemAgentAssignment).where(
                    SystemAgentAssignment.feature_code.like(f"plugin.{plugin.name}.%"),
                    SystemAgentAssignment.is_deleted.is_(False),
                )
            )
            assignments = result.scalars().all()
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
                raise NotFoundException(message=f"Plugin #{plugin_id} not found")
            backups = await _asyncio.to_thread(_list, plugin.name)
            return success(data=backups)

        @self.router.delete("/{plugin_id}/backups/{backup_name}")
        @action_delete("action.plugin.uninstall")
        async def delete_backup(plugin_id: int, backup_name: str, db: DbSession, admin: ActiveAdmin):
            """删除指定备份（仅允许删除该插件的备份） / Delete specified backup (only backups for this plugin are allowed)"""
            import re as _re

            from app.exceptions.base import NotFoundException, ValidationException
            from app.plugins.backup import BACKUPS_DIR

            # 安全校验：backup_name 只允许 [版本]_[时间戳] 格式，防路径穿越 / Security check: backup_name only allows [version]_[timestamp] format, prevents path traversal
            if not _re.match(r'^[a-zA-Z0-9._-]+$', backup_name) or '..' in backup_name:
                raise ValidationException(message="Invalid backup name")

            plugin = await self.get_service(db).get_by_id(plugin_id)
            if not plugin:
                raise NotFoundException(message=f"Plugin #{plugin_id} not found")
            backup_path = BACKUPS_DIR / plugin.name / backup_name
            if not backup_path.is_dir():
                raise NotFoundException(message="Backup not found")

            import shutil as _shutil
            _shutil.rmtree(backup_path)

            # 若该插件已无备份，清理空目录 / If plugin has no backups, clean up empty directory
            plugin_backup_dir = BACKUPS_DIR / plugin.name
            if plugin_backup_dir.is_dir() and not any(plugin_backup_dir.iterdir()):
                plugin_backup_dir.rmdir()

            return deleted()

        # ── 健康 / Health ──

        @self.router.get("/{plugin_id}/health")
        @action_read("action.plugin.health")
        async def get_health(plugin_id: int, db: DbSession, admin: ActiveAdmin):
            from app.plugins.health import PluginHealthMonitor

            plugin = await self.get_service(db).get_by_id(plugin_id)
            if not plugin:
                from app.exceptions.base import NotFoundException
                raise NotFoundException(message=f"Plugin #{plugin_id} not found")
            monitor = PluginHealthMonitor(db)
            status = await monitor.get_health_status(plugin.name)
            return success(data=status)


admin_plugin_controller = AdminPluginController()
router = admin_plugin_controller.router
