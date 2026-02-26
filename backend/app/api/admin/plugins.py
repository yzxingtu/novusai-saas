"""
插件管理 Controller（管理端）
"""

import re
import shutil
import tempfile
from pathlib import Path

from fastapi import File, UploadFile
from pydantic import BaseModel as PydanticBaseModel, Field

from app.core.base_controller import GlobalController
from app.core.deps import DbSession, ActiveAdmin, QueryParams
from app.core.response import success, created, deleted, paginated
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


class PluginRollbackBody(PydanticBaseModel):
    target_version: str = ""


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
            from app.plugins.loader import PLUGINS_DIR, PluginLoader
            from app.plugins.package_security import extract_plugin_zip_safely
            from app.plugins.preview import generate_preview

            _sanitize_slug(slug)
            temp_dir = PLUGINS_DIR / f"_market_{slug}"
            try:
                extract_dir = zip_path.parent / "extracted"
                plugin_dir = extract_plugin_zip_safely(zip_path, extract_dir)

                if temp_dir.exists():
                    shutil.rmtree(temp_dir)
                shutil.copytree(plugin_dir, temp_dir)

                loader = PluginLoader()
                preview = await generate_preview(temp_dir, loader)
                return success(data=preview.model_dump())
            finally:
                shutil.rmtree(temp_dir, ignore_errors=True)
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

            from app.plugins.loader import PLUGINS_DIR, PluginLoader
            from app.plugins.package_security import extract_plugin_zip_safely

            _sanitize_slug(slug)
            try:
                extract_dir = zip_path.parent / "extracted"
                plugin_dir = extract_plugin_zip_safely(zip_path, extract_dir)

                loader = PluginLoader()
                manifest = loader.load_manifest_from_path(plugin_dir)
                target_dir = PLUGINS_DIR / manifest.name
                if not target_dir.exists():
                    shutil.copytree(plugin_dir, target_dir)

                service = self.get_service(db)
                plugin = await service.install_from_path(target_dir, body.config)

                # 更新 install_source 和 marketplace_slug
                plugin.install_source = PluginInstallSourceEnum.MARKETPLACE.value
                plugin.marketplace_slug = slug
                await db.flush()

                return created(data=plugin.to_dict())
            finally:
                shutil.rmtree(zip_path.parent, ignore_errors=True)

        @self.router.get("/frontend-config")
        @action_read("action.plugin.list")
        async def get_frontend_config(db: DbSession, admin: ActiveAdmin):
            """获取所有已启用插件的前端配置（菜单/路由/Widget/翻译）"""
            from sqlalchemy import select
            from app.enums.plugin import PluginStatusEnum
            from app.models.system.plugin import Plugin as PluginModel

            result = await db.execute(
                select(PluginModel.name, PluginModel.manifest, PluginModel.icon).where(
                    PluginModel.status == PluginStatusEnum.ENABLED.value,
                    PluginModel.is_deleted.is_(False),
                )
            )
            rows = result.all()

            configs = []
            for name, manifest_data, icon in rows:
                if not manifest_data:
                    continue
                extensions = manifest_data.get("extensions", {})
                frontend = extensions.get("frontend", {})
                # 仅返回有前端扩展声明的插件
                has_frontend = (
                    frontend.get("menus")
                    or frontend.get("header_widgets")
                    or frontend.get("floating_panels")
                    or frontend.get("dashboard_widgets")
                    or frontend.get("standalone_pages")
                    or frontend.get("settings_tabs")
                )
                if not has_frontend:
                    continue
                configs.append({
                    "name": name,
                    "icon": icon,
                    "frontend": frontend,
                    "locales": manifest_data.get("resources", {}).get("readme", {}),
                })
            return success(data=configs)

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
                result_items.append(data)

            return paginated(
                items=result_items, total=total,
                page=query.page, page_size=query.size,
            )

        @self.router.get("/{plugin_id}")
        @action_read("action.plugin.detail")
        async def get_plugin(plugin_id: int, db: DbSession, admin: ActiveAdmin):
            service = self.get_service(db)
            plugin = await service.get_by_id(plugin_id)

            data = plugin.to_dict()

            # 脱敏配置
            from app.plugins.crypto import mask_plugin_config

            manifest_data = data.get("manifest") or {}
            config_schema = manifest_data.get("config_schema")
            if config_schema and data.get("config"):
                data["config"] = mask_plugin_config(data["config"], config_schema)

            # 加载 README
            readme = await service.get_readme(plugin_id)
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
            上传 ZIP 并安装插件（两阶段提交）

            阶段 1：在系统临时目录中完成 DB 事务（不触发 Uvicorn --reload）
            阶段 2：DB 提交成功后，move 到 plugins/ 目录（此时 reload 不影响已提交的事务）
            """
            from sqlalchemy import select

            from app.models.system.plugin import Plugin as PluginModel
            from app.plugins.loader import PLUGINS_DIR

            content = await file.read()
            staging_dir, plugin_dir = _extract_plugin_from_zip(content, file.filename or "plugin.zip")

            try:
                import yaml

                with open(plugin_dir / "plugin.yaml", "r", encoding="utf-8") as yf:
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

                # 阶段 1：在临时目录中执行安装（DB 操作），不复制到 plugins/
                # install_from_path 内部的 lifecycle.install 会读取 manifest、注册 AI features 等
                # 但不触发文件系统变化（因为 staging_dir 在系统 temp 中，不被 --reload 监控）
                service = self.get_service(db)
                plugin = await service.install_from_path(plugin_dir, operator_id=admin.id)
                plugin_data = plugin.to_dict()

                # 阶段 2：DB 事务已在 service 层 flush，现在安全地 move 到 plugins/
                target_dir = PLUGINS_DIR / plugin_name
                if target_dir.exists():
                    shutil.rmtree(target_dir)
                shutil.copytree(plugin_dir, target_dir)

                return created(data=plugin_data)
            finally:
                shutil.rmtree(staging_dir, ignore_errors=True)

        @self.router.post("/{plugin_id}/enable")
        @action_update("action.plugin.enable")
        async def enable_plugin(plugin_id: int, db: DbSession, admin: ActiveAdmin):
            service = self.get_service(db)
            await service.enable_plugin(plugin_id, operator_id=admin.id)

            # 检查前端 npm 依赖是否已安装（仅 DEBUG 模式）
            missing_npm_deps: list[str] = []
            needs_restart = False
            from app.core.config import settings
            if settings.DEBUG:
                plugin = await service.repo.get_by_id(plugin_id)
                manifest_data = plugin.manifest or {}
                frontend = (manifest_data.get("extensions") or {}).get("frontend") or {}
                npm_deps = frontend.get("npm_dependencies") or []
                if npm_deps:
                    from app.plugins.loader import PLUGINS_DIR
                    frontend_node_modules = PLUGINS_DIR.parent.parent / "frontend" / "node_modules"
                    for pkg in npm_deps:
                        pkg_name = pkg.split("@")[0] if pkg.startswith("@") else pkg.split("@")[0]
                        if pkg.startswith("@"):
                            pkg_name = pkg  # scoped package like @tiptap/vue-3
                            if "/" in pkg_name and "@" in pkg_name[1:]:
                                pkg_name = pkg_name.rsplit("@", 1)[0]
                        pkg_dir = frontend_node_modules / pkg_name
                        if not pkg_dir.is_dir():
                            missing_npm_deps.append(pkg)
                    if missing_npm_deps:
                        needs_restart = True

            return success(data={
                "message": "Plugin enabled",
                "missing_npm_deps": missing_npm_deps,
                "needs_restart": needs_restart,
            })

        @self.router.post("/{plugin_id}/install-npm-deps")
        @action_update("action.plugin.enable")
        async def install_npm_deps(plugin_id: int, db: DbSession, admin: ActiveAdmin):
            """手动触发插件 npm 依赖安装（前端启用后调用）"""
            service = self.get_service(db)
            plugin = await service.repo.get_by_id(plugin_id)
            manifest_data = plugin.manifest or {}
            frontend = (manifest_data.get("extensions") or {}).get("frontend") or {}
            npm_deps = frontend.get("npm_dependencies") or []

            if not npm_deps:
                return success(data={"message": "No npm dependencies to install"})

            from app.plugins.lifecycle import PluginLifecycle
            lifecycle = PluginLifecycle(db)
            await lifecycle._install_npm_deps(plugin.name, npm_deps)
            return success(data={"message": f"Installed {len(npm_deps)} npm packages", "needs_restart": True})

        @self.router.post("/{plugin_id}/disable")
        @action_update("action.plugin.disable")
        async def disable_plugin(plugin_id: int, db: DbSession, admin: ActiveAdmin):
            service = self.get_service(db)
            await service.disable_plugin(plugin_id, operator_id=admin.id)
            return success(data={"message": "Plugin disabled"})

        @self.router.delete("/{plugin_id}")
        @action_delete("action.plugin.uninstall")
        async def uninstall_plugin(
            plugin_id: int,
            db: DbSession,
            admin: ActiveAdmin,
            confirm_data_delete: bool = False,
        ):
            service = self.get_service(db)
            await service.uninstall_plugin(plugin_id, confirm_data_delete, operator_id=admin.id)
            return deleted()

        @self.router.post("/{plugin_id}/repair")
        @action_update("action.plugin.repair")
        async def repair_plugin(plugin_id: int, db: DbSession, admin: ActiveAdmin):
            """修复插件（重置错误计数）"""
            from app.plugins.health import PluginHealthMonitor

            monitor = PluginHealthMonitor(db)
            plugin = await self.get_service(db).get(plugin_id)
            await monitor.reset_error(plugin.name)
            return success(data={"message": "Plugin repaired"})

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
            plugin = await service.update_plugin_config(plugin_id, body.config)
            return success(data={"message": "Config updated"})

        @self.router.put("/{plugin_id}/capabilities")
        @action_update("action.plugin.capabilities")
        async def update_capabilities(
            plugin_id: int,
            body: PluginCapabilitiesBody,
            db: DbSession = None,
            admin: ActiveAdmin = None,
        ):
            service = self.get_service(db)
            plugin = await service.update_capabilities(plugin_id, body.capabilities)
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

            # 更新 icon 字段为相对路径
            plugin.icon = f"/plugins/{plugin.name}/{icon_filename}"
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
            from app.plugins.license import create_trial_license, get_license_status_by_id

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
            db: DbSession = None,
            admin: ActiveAdmin = None,
            agent_id: int | None = None,
        ):
            """为插件 AI 功能绑定 Agent"""
            from sqlalchemy import select, update

            from app.models.system.agent_assignment import SystemAgentAssignment

            await db.execute(
                update(SystemAgentAssignment).where(
                    SystemAgentAssignment.id == assignment_id,
                ).values(agent_id=agent_id)
            )
            await db.flush()
            return success(data={"message": "AI feature binding updated"})

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
