"""
插件管理 Controller（管理端）
"""

import shutil
import tempfile
import zipfile
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
    scope=PermissionScope.ADMIN,
    menu=MenuConfig(
        icon="lucide:puzzle",
        path="/plugins",
        component="admin/plugins/index",
        parent="system_maintenance",
        sort_order=90,
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
            import zipfile
            extract_dir = zip_path.parent / "extracted"
            with zipfile.ZipFile(zip_path, "r") as zf:
                zf.extractall(extract_dir)

            plugin_dir = None
            for child in extract_dir.iterdir():
                if child.is_dir() and (child / "plugin.yaml").is_file():
                    plugin_dir = child
                    break
            if not plugin_dir and (extract_dir / "plugin.yaml").is_file():
                plugin_dir = extract_dir

            if not plugin_dir:
                from app.plugins.exceptions import PluginManifestError
                raise PluginManifestError(message="No plugin.yaml found in downloaded package")

            from app.plugins.loader import PLUGINS_DIR, PluginLoader
            from app.plugins.preview import generate_preview

            temp_dir = PLUGINS_DIR / f"_market_{slug}"
            if temp_dir.exists():
                shutil.rmtree(temp_dir)
            shutil.copytree(plugin_dir, temp_dir)

            try:
                loader = PluginLoader()
                preview = await generate_preview(temp_dir, loader)
                # 保存下载路径供 confirm-install 使用
                preview_data = preview.model_dump()
                preview_data["_download_dir"] = str(plugin_dir)
                return success(data=preview_data)
            finally:
                shutil.rmtree(temp_dir, ignore_errors=True)

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

            import zipfile
            extract_dir = zip_path.parent / "extracted"
            with zipfile.ZipFile(zip_path, "r") as zf:
                zf.extractall(extract_dir)

            plugin_dir = None
            for child in extract_dir.iterdir():
                if child.is_dir() and (child / "plugin.yaml").is_file():
                    plugin_dir = child
                    break
            if not plugin_dir and (extract_dir / "plugin.yaml").is_file():
                plugin_dir = extract_dir

            if not plugin_dir:
                from app.plugins.exceptions import PluginManifestError
                raise PluginManifestError(message="No plugin.yaml in downloaded package")

            from app.plugins.loader import PLUGINS_DIR, PluginLoader

            loader = PluginLoader()
            manifest = loader.load_manifest(plugin_dir.name)
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
            staging_dir = Path(tempfile.mkdtemp(prefix="novusai_plugin_"))

            zip_path = staging_dir / filename
            with open(zip_path, "wb") as f:
                f.write(file_content)

            extract_dir = staging_dir / "extracted"
            with zipfile.ZipFile(zip_path, "r") as zf:
                zf.extractall(extract_dir)

            plugin_dir = None
            for child in extract_dir.iterdir():
                if child.is_dir() and (child / "plugin.yaml").is_file():
                    plugin_dir = child
                    break
            if not plugin_dir and (extract_dir / "plugin.yaml").is_file():
                plugin_dir = extract_dir

            if not plugin_dir:
                shutil.rmtree(staging_dir, ignore_errors=True)
                from app.plugins.exceptions import PluginManifestError
                raise PluginManifestError(message="No plugin.yaml found in uploaded ZIP")

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
                from app.plugins.manifest import PluginManifest

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
            """上传 ZIP 并安装插件（一步完成）"""
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

                target_dir = PLUGINS_DIR / plugin_name
                if target_dir.exists():
                    # 残留目录（无 DB 记录），清理后重新安装
                    shutil.rmtree(target_dir)
                shutil.copytree(plugin_dir, target_dir)

                service = self.get_service(db)
                plugin = await service.install_from_path(target_dir)
                return created(data=plugin.to_dict())
            finally:
                shutil.rmtree(staging_dir, ignore_errors=True)

        @self.router.post("/{plugin_id}/enable")
        @action_update("action.plugin.enable")
        async def enable_plugin(plugin_id: int, db: DbSession, admin: ActiveAdmin):
            service = self.get_service(db)
            await service.enable_plugin(plugin_id)
            return success(data={"message": "Plugin enabled"})

        @self.router.post("/{plugin_id}/disable")
        @action_update("action.plugin.disable")
        async def disable_plugin(plugin_id: int, db: DbSession, admin: ActiveAdmin):
            service = self.get_service(db)
            await service.disable_plugin(plugin_id)
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
            await service.uninstall_plugin(plugin_id, confirm_data_delete)
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

            # 保存文件
            icon_filename = f"icon{suffix}"
            icon_path = PLUGINS_DIR / plugin.name / icon_filename
            content = await file.read()
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
            from app.plugins.version_manager import VersionManager

            with tempfile.TemporaryDirectory() as tmp_dir:
                tmp_path = Path(tmp_dir) / file.filename
                with open(tmp_path, "wb") as f:
                    content = await file.read()
                    f.write(content)

                extract_dir = Path(tmp_dir) / "extracted"
                with zipfile.ZipFile(tmp_path, "r") as zf:
                    zf.extractall(extract_dir)

                plugin_dir = None
                for child in extract_dir.iterdir():
                    if child.is_dir() and (child / "plugin.yaml").is_file():
                        plugin_dir = child
                        break

                if not plugin_dir:
                    from app.plugins.exceptions import PluginManifestError
                    raise PluginManifestError(message="No plugin.yaml found in ZIP")

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

        @self.router.post("/{plugin_id}/activate-license")
        @action_update("action.plugin.activate_license")
        async def activate_license(
            plugin_id: int,
            body: PluginActivateLicenseBody,
            db: DbSession = None,
            admin: ActiveAdmin = None,
        ):
            service = self.get_service(db)
            await service.activate_license(plugin_id, body.license_key)
            return success(data={"message": "License activated"})

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
