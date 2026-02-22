"""
平台管理端插件管理 API

提供插件的安装、卸载、启用/禁用、列表、详情等管理接口
"""

import shutil
import tempfile
from pathlib import Path as FilePath

from fastapi import File, Path, Query, Request, UploadFile
from fastapi.responses import FileResponse
from starlette.background import BackgroundTask

from app.core.base_controller import GlobalController
from app.core.deps import DbSession, QueryParams, ActiveAdmin
from app.core.i18n import _
from app.core.response import success, created, deleted, paginated
from app.enums.rbac import PermissionScope
from app.rbac.decorators import (
    permission_resource,
    MenuConfig,
    action_read,
    action_create,
    action_update,
    action_delete,
)
from app.schemas.system.plugin import (
    PluginResponse,
    PluginInstallRequest,
    PluginUpdateRequest,
    PluginToggleRequest,
)
from app.core.logging import LogManager
from app.services.system.plugin_service import PluginService

logger = LogManager.get_logger("app")


def _mask_plugin_response(plugin) -> dict:
    """序列化 Plugin 并对敏感配置字段脱敏 + 实时翻译 config_schema title/description"""
    from app.plugins.security import mask_sensitive_config
    resp = PluginResponse.model_validate(plugin, from_attributes=True).model_dump()
    if resp.get("default_config") and resp.get("config_schema"):
        resp["default_config"] = mask_sensitive_config(
            resp["default_config"], resp["config_schema"]
        )
    # 实时翻译 config_schema 中的 title/description（DB 中可能存储了 raw i18n key）
    if resp.get("config_schema"):
        resp["config_schema"] = _translate_config_schema(resp["config_schema"])
    return resp


def _translate_config_schema(schema: dict) -> dict:
    """实时翻译 config_schema properties 中的 title 和 description 字段"""
    from app.core.i18n import translate
    if not schema or "properties" not in schema:
        return schema
    result = dict(schema)
    props = dict(result.get("properties", {}))
    for field_name, field_schema in props.items():
        field_schema = dict(field_schema)
        for key in ("title", "description"):
            val = field_schema.get(key)
            if val and isinstance(val, str) and "." in val:
                translated = translate(val)
                if translated != val:
                    field_schema[key] = translated
        props[field_name] = field_schema
    result["properties"] = props
    return result


@permission_resource(
    resource="plugin",
    name="menu.admin.plugin",
    scope=PermissionScope.ADMIN,
    menu=MenuConfig(
        icon="lucide:plug",
        path="/system/plugins",
        component="admin/system/plugins/index",
        parent="system_maintenance",
        sort_order=70,
    ),
)
class AdminPluginController(GlobalController):
    """
    平台插件管理控制器
    """

    prefix = "/plugins"
    tags = ["Plugin Management"]
    service_class = PluginService

    def _register_routes(self) -> None:
        router = self.router

        @router.get("", summary="获取插件列表")
        @action_read("action.plugin.list")
        async def list_plugins(
            request: Request,
            db: DbSession,
            current_admin: ActiveAdmin,
            query: QueryParams,
        ):
            service = self.get_service(db)
            items, total = await service.query_list(query)
            return paginated(
                items=[
                    _mask_plugin_response(item)
                    for item in items
                ],
                total=total,
                page=query.page,
                page_size=query.size,
            )

        @router.get("/frontend-config", summary="获取已启用插件的前端配置")
        @action_read("action.plugin.list")
        async def get_plugin_frontend_config(
            request: Request,
            db: DbSession,
            current_admin: ActiveAdmin,
        ):
            """返回所有已启用且声明了 frontend 的插件前端配置（路由+菜单+i18n）"""
            service = self.get_service(db)
            from app.schemas.common.query import QuerySpec
            items, _ = await service.query_list(
                QuerySpec(page=1, size=100),
            )
            configs = []
            for plugin in items:
                if plugin.status != "enabled":
                    continue
                manifest = plugin.manifest or {}
                frontend = manifest.get("frontend")
                if not frontend:
                    continue
                # 读取插件 locales 目录下的 i18n 资源
                locales = frontend.get("locales", {})
                if not locales:
                    locales = _load_plugin_locales(plugin.name)
                configs.append({
                    "plugin_name": plugin.name,
                    "plugin_version": plugin.version,
                    "scope": plugin.scope,
                    "endpoint": frontend.get("endpoint", "admin"),
                    "menus": frontend.get("menus", []),
                    "routes": frontend.get("routes", []),
                    "locales": locales,
                })
            return success(data=configs)

        @router.get("/{plugin_id}", summary="获取插件详情")
        @action_read("action.plugin.detail")
        async def get_plugin(
            request: Request,
            db: DbSession,
            current_admin: ActiveAdmin,
            plugin_id: int = Path(..., description="插件 ID"),
        ):
            service = self.get_service(db)
            plugin = await service.get_by_id(plugin_id)
            return success(data=_mask_plugin_response(plugin))

        @router.post("/install", summary="安装插件")
        @action_create("action.plugin.install")
        async def install_plugin(
            request: Request,
            db: DbSession,
            current_admin: ActiveAdmin,
            body: PluginInstallRequest,
        ):
            from app.plugins.manager import get_plugin_manager

            manager = get_plugin_manager()
            plugin = await manager.install(
                db,
                entry_point=body.entry_point,
                is_system=body.is_system,
                admin_id=current_admin.id,
            )
            return created(data=_mask_plugin_response(plugin))

        @router.delete("/{plugin_id}", summary="卸载插件")
        @action_delete("action.plugin.uninstall")
        async def uninstall_plugin(
            request: Request,
            db: DbSession,
            current_admin: ActiveAdmin,
            plugin_id: int = Path(..., description="插件 ID"),
        ):
            from app.plugins.manager import get_plugin_manager

            manager = get_plugin_manager()
            await manager.uninstall(db, plugin_id, admin_id=current_admin.id)
            return deleted()

        @router.put("/{plugin_id}", summary="更新插件信息")
        @action_update("action.plugin.update")
        async def update_plugin(
            request: Request,
            db: DbSession,
            current_admin: ActiveAdmin,
            body: PluginUpdateRequest,
            plugin_id: int = Path(..., description="插件 ID"),
        ):
            service = self.get_service(db)
            data = body.model_dump(exclude_unset=True)

            # 处理 default_config 中的敏感字段
            if "default_config" in data and data["default_config"]:
                existing = await service.get_by_id(plugin_id)
                if existing and existing.config_schema:
                    from app.plugins.security import encrypt_sensitive_config
                    # 跳过未修改的密码字段（前端回传 ****** 表示未更改）
                    props = existing.config_schema.get("properties", {})
                    old_config = existing.default_config or {}
                    for field_name, field_schema in props.items():
                        if field_schema.get("format") == "password":
                            if data["default_config"].get(field_name) == "******":
                                data["default_config"][field_name] = old_config.get(field_name, "")
                    data["default_config"] = encrypt_sensitive_config(
                        data["default_config"], existing.config_schema
                    )

            plugin = await service.update(plugin_id, data)
            return success(data=_mask_plugin_response(plugin))

        @router.post("/{plugin_id}/enable", summary="启用插件（平台级）")
        @action_update("action.plugin.enable")
        async def enable_plugin(
            request: Request,
            db: DbSession,
            current_admin: ActiveAdmin,
            plugin_id: int = Path(..., description="插件 ID"),
            body: dict | None = None,
        ):
            from app.plugins.manager import get_plugin_manager

            model_id = (body or {}).get("model_id")
            manager = get_plugin_manager()
            plugin = await manager.enable_platform(
                db, plugin_id, admin_id=current_admin.id, model_id=model_id,
            )
            return success(data=_mask_plugin_response(plugin))

        @router.post("/{plugin_id}/disable", summary="禁用插件（平台级）")
        @action_update("action.plugin.disable")
        async def disable_plugin(
            request: Request,
            db: DbSession,
            current_admin: ActiveAdmin,
            plugin_id: int = Path(..., description="插件 ID"),
        ):
            from app.plugins.manager import get_plugin_manager

            manager = get_plugin_manager()
            plugin = await manager.disable_platform(db, plugin_id, admin_id=current_admin.id)
            return success(data=_mask_plugin_response(plugin))

        @router.post("/{plugin_id}/upgrade", summary="升级插件")
        @action_update("action.plugin.upgrade")
        async def upgrade_plugin(
            request: Request,
            db: DbSession,
            current_admin: ActiveAdmin,
            plugin_id: int = Path(..., description="插件 ID"),
        ):
            from app.plugins.manager import get_plugin_manager

            manager = get_plugin_manager()
            plugin = await manager.upgrade(db, plugin_id)
            return success(data=_mask_plugin_response(plugin))

        @router.get("/{plugin_id}/health", summary="插件健康检查")
        @action_read("action.plugin.health")
        async def health_check(
            request: Request,
            db: DbSession,
            current_admin: ActiveAdmin,
            plugin_id: int = Path(..., description="插件 ID"),
        ):
            from app.plugins.manager import get_plugin_manager
            from app.exceptions import NotFoundException as NF

            service = self.get_service(db)
            plugin = await service.get_by_id(plugin_id)
            if not plugin:
                raise NF(message=_("plugin.not_found"))

            manager = get_plugin_manager()
            try:
                instance = manager.get_or_load_instance(plugin.name, plugin.entry_point)
            except Exception:
                instance = None

            if not instance:
                return success(data={
                    "plugin_name": plugin.name,
                    "healthy": False,
                    "reason": "not_loaded",
                    "status": plugin.status,
                })

            try:
                ctx = await manager.build_execution_context(instance, db=db)
                result = await instance.health_check(ctx)
            except Exception as exc:
                return success(data={
                    "plugin_name": plugin.name,
                    "healthy": False,
                    "reason": str(exc),
                    "status": plugin.status,
                })

            return success(data={
                "plugin_name": plugin.name,
                "status": plugin.status,
                **result,
            })

        @router.post("/upload/preview", summary="预览插件包内容（不安装）")
        @action_create("action.plugin.upload")
        async def preview_plugin_package(
            request: Request,
            db: DbSession,
            current_admin: ActiveAdmin,
            file: UploadFile = File(..., description="Plugin package (.zip / .nap)"),
            lang: str = Query("", description="Language code for README (e.g. zh-CN, en-US)"),
        ):
            """
            解析 .nap/.zip 包的 manifest，返回插件结构预览：
            - 基本信息（名称/版本/作者/描述/图标）
            - 是否包含智能体（has_agent）
            - 技能信息（skill_type）
            - API 路由信息
            - 是否已安装（is_installed）
            """
            from app.plugins.packaging import (
                ALLOWED_PACKAGE_EXTENSIONS,
                PackageError,
                extract_package,
            )
            from app.exceptions import ValidationException
            from app.repositories.system.plugin_repository import PluginRepository

            if not file.filename:
                raise ValidationException(message=_("plugin.file_required"))

            ext = FilePath(file.filename).suffix.lower()
            if ext not in ALLOWED_PACKAGE_EXTENSIONS:
                raise ValidationException(message=_("plugin.file_must_be_zip_or_nap"))

            with tempfile.TemporaryDirectory() as tmp_dir:
                nap_path = FilePath(tmp_dir) / file.filename
                content = await file.read()
                nap_path.write_bytes(content)

                try:
                    plugin_dir = FilePath(tmp_dir) / "extracted"
                    manifest = extract_package(nap_path, plugin_dir)
                except PackageError as e:
                    raise ValidationException(message=str(e))

                plugin_name = manifest.get("name", "")
                plugin_type = manifest.get("plugin_type", "composite")

                # 检查是否已安装
                repo = PluginRepository(db)
                existing = await repo.get_by_name(plugin_name)

                # 检测插件结构
                has_readme = any(
                    f.name.lower().startswith("readme") and f.suffix.lower() == ".md"
                    for f in plugin_dir.iterdir() if f.is_file()
                )
                import base64
                has_icon = False
                icon_data_url = ""
                icon_mime_map = {
                    "png": "image/png", "svg": "image/svg+xml",
                    "jpg": "image/jpeg", "jpeg": "image/jpeg", "webp": "image/webp",
                }
                for icon_ext, icon_mime in icon_mime_map.items():
                    icon_path = plugin_dir / f"icon.{icon_ext}"
                    if icon_path.exists() and icon_path.stat().st_size < 512 * 1024:
                        icon_bytes = icon_path.read_bytes()
                        icon_data_url = f"data:{icon_mime};base64,{base64.b64encode(icon_bytes).decode()}"
                        has_icon = True
                        break

                # 检测迁移文件
                migrations_dir = plugin_dir / "migrations"
                migration_count = 0
                migration_names: list[str] = []
                if migrations_dir.is_dir():
                    mig_files = sorted([
                        f for f in migrations_dir.iterdir()
                        if f.is_file() and f.suffix == ".sql" and not f.name.endswith(".down.sql")
                    ], key=lambda f: f.name)
                    migration_count = len(mig_files)
                    migration_names = [f.stem for f in mig_files]

                # 检测 locale 文件
                locales_dir = plugin_dir / "locales"
                locale_langs = []
                if locales_dir.is_dir():
                    locale_langs = [f.stem for f in locales_dir.glob("*.json")]

                # 判断是否包含智能体/技能/API
                provides = manifest.get("provides", [])
                has_skill = plugin_type in ("skill", "composite") or "skill" in provides
                has_api = plugin_type in ("api", "composite") or "api" in provides
                has_hook = plugin_type in ("hook", "composite") or "hook" in provides
                has_adapter = plugin_type in ("adapter", "composite") or "adapter" in provides

                # 从 manifest 读取 agents 声明（插件可在 manifest 中声明其创建的 agents）
                agents_decl = manifest.get("agents", [])
                # 如果 manifest 没声明 agents 但是 skill/composite 类型，推断可能含 agent
                has_agent = len(agents_decl) > 0 or plugin_type in ("skill", "composite")

                # 从 manifest 读取 models 声明（数据库模型）
                models_decl = manifest.get("models", [])

                # 技能类型
                skill_type = manifest.get("skill_type", "")

                # 前端菜单/路由
                frontend_config = manifest.get("frontend", {})
                menus = frontend_config.get("menus", [])
                routes = frontend_config.get("routes", [])

                # 读取 README（多语言支持：README.zh-CN.md → README.md 回退）
                readme_preview = ""
                readme_candidates: list[str] = []
                if lang:
                    readme_candidates.append(f"README.{lang}.md")
                    readme_candidates.append(f"readme.{lang}.md")
                readme_candidates.extend(["README.md", "readme.md"])
                for rname in readme_candidates:
                    rpath = plugin_dir / rname
                    if rpath.exists():
                        readme_preview = rpath.read_text(encoding="utf-8")[:5000]
                        break

                # 构建结构摘要（含可展开的详情子项）
                structure_summary: list[dict] = []
                if has_agent:
                    agent_count = max(len(agents_decl), 1)
                    agent_details = [
                        a.get("name", a.get("description", "Agent"))
                        for a in agents_decl
                    ] if agents_decl else []
                    structure_summary.append({
                        "type": "agent",
                        "icon": "lucide:bot",
                        "count": agent_count,
                        "details": agent_details,
                    })
                if has_skill:
                    structure_summary.append({
                        "type": "skill_package",
                        "icon": "lucide:sparkles",
                        "count": 1,
                        "details": [skill_type] if skill_type else [],
                    })
                if has_api:
                    route_details = [
                        r.get("path", "?") for r in routes
                    ] if routes else []
                    structure_summary.append({
                        "type": "api_route",
                        "icon": "lucide:route",
                        "count": len(routes) or 1,
                        "details": route_details,
                    })
                if has_adapter:
                    structure_summary.append({
                        "type": "adapter",
                        "icon": "lucide:cpu",
                        "count": 1,
                        "details": [],
                    })
                if has_hook:
                    structure_summary.append({
                        "type": "hook",
                        "icon": "lucide:webhook",
                        "count": 1,
                        "details": [],
                    })
                if migration_count > 0:
                    structure_summary.append({
                        "type": "migration",
                        "icon": "lucide:database",
                        "count": migration_count,
                        "details": migration_names,
                    })
                if len(models_decl) > 0:
                    structure_summary.append({
                        "type": "model",
                        "icon": "lucide:table",
                        "count": len(models_decl),
                        "details": models_decl,
                    })
                if len(menus) > 0:
                    menu_detail = [
                        m.get("name", m.get("code", "?")) for m in menus
                    ]
                    structure_summary.append({
                        "type": "menu",
                        "icon": "lucide:layout-grid",
                        "count": len(menus),
                        "details": menu_detail,
                    })

                return success(data={
                    "name": plugin_name,
                    "display_name": manifest.get("display_name", plugin_name),
                    "version": manifest.get("version", "0.0.0"),
                    "description": manifest.get("description", ""),
                    "author": manifest.get("author", ""),
                    "plugin_type": plugin_type,
                    "icon": manifest.get("icon", ""),
                    "scope": manifest.get("scope", "all_tenants"),
                    # 结构信息
                    "has_agent": has_agent,
                    "has_skill": has_skill,
                    "has_api": has_api,
                    "has_readme": has_readme,
                    "has_icon": has_icon,
                    "icon_data_url": icon_data_url,
                    "migration_count": migration_count,
                    "locale_langs": locale_langs,
                    "readme_preview": readme_preview,
                    "skill_type": skill_type,
                    "structure_summary": structure_summary,
                    "agents": agents_decl,
                    "models": models_decl,
                    "frontend_menus": menus,
                    "frontend_routes": routes,
                    # 安装状态
                    "is_installed": existing is not None,
                    "existing_version": existing.version if existing else None,
                    # 配置
                    "config_schema": manifest.get("config_schema"),
                    "default_config": manifest.get("default_config"),
                    "required_permissions": manifest.get("required_permissions", []),
                    "dependencies": manifest.get("dependencies", {}),
                })

        @router.post("/upload", summary="上传插件包安装（.zip / .nap）")
        @action_create("action.plugin.upload")
        async def upload_plugin(
            request: Request,
            db: DbSession,
            current_admin: ActiveAdmin,
            file: UploadFile = File(..., description="Plugin package (.zip / .nap)"),
            overwrite: bool = Query(False, description="Overwrite existing plugin (upgrade)"),
            model_id: int | None = Query(None, description="AI model ID for agent creation"),
        ):
            from app.plugins.packaging import (
                ALLOWED_PACKAGE_EXTENSIONS,
                PackageError,
                extract_package,
            )
            from app.plugins.manager import get_plugin_manager
            from app.exceptions import ValidationException, BusinessException
            from app.repositories.system.plugin_repository import PluginRepository

            if not file.filename:
                raise ValidationException(
                    message=_("plugin.file_required"),
                )

            ext = FilePath(file.filename).suffix.lower()
            if ext not in ALLOWED_PACKAGE_EXTENSIONS:
                raise ValidationException(
                    message=_("plugin.file_must_be_zip_or_nap"),
                )

            with tempfile.TemporaryDirectory() as tmp_dir:
                nap_path = FilePath(tmp_dir) / file.filename
                content = await file.read()
                nap_path.write_bytes(content)

                try:
                    plugin_dir = FilePath(tmp_dir) / "extracted"
                    manifest = extract_package(nap_path, plugin_dir)
                except PackageError as e:
                    raise ValidationException(
                        message=str(e),
                    )

                plugin_name = manifest.get("name", "")
                raw_entry_point = manifest.get("entry_point", "")
                module_name = plugin_name.replace("-", "_")

                plugins_base = FilePath(__file__).resolve().parent.parent.parent / "plugins"
                permanent_dir = plugins_base / module_name

                # 检查 DB 中是否已有安装记录
                repo = PluginRepository(db)
                existing = await repo.get_by_name(plugin_name)

                if permanent_dir.exists() and existing:
                    # 目录存在 + DB 有记录 → 真正的已安装插件，需要覆盖升级
                    if not overwrite:
                        file_diff = _compute_file_diff(permanent_dir, plugin_dir)
                        return success(data={
                            "conflict": True,
                            "plugin_name": plugin_name,
                            "existing_version": existing.version if existing else None,
                            "new_version": manifest.get("version", ""),
                            "message": _("plugin.upload_conflict"),
                            "file_diff": file_diff,
                        })

                    # 覆盖模式：备份旧目录 → 拷贝新文件
                    backup_dir = permanent_dir.with_suffix(".bak")
                    if backup_dir.exists():
                        shutil.rmtree(backup_dir, ignore_errors=True)
                    shutil.move(str(permanent_dir), str(backup_dir))
                    try:
                        shutil.copytree(plugin_dir, permanent_dir)
                    except Exception:
                        shutil.rmtree(permanent_dir, ignore_errors=True)
                        shutil.move(str(backup_dir), str(permanent_dir))
                        raise
                elif permanent_dir.exists() and not existing:
                    # 目录存在但 DB 无记录 → 开发期间本地代码，视为首次安装
                    # 跳过文件拷贝（使用已有目录中的代码）
                    backup_dir = None
                else:
                    # 目录不存在 → 全新安装，拷贝文件
                    shutil.copytree(plugin_dir, permanent_dir)
                    backup_dir = None

            entry_point = f"app.plugins.{module_name}.{raw_entry_point}"
            manager = get_plugin_manager()

            # 安装 Python 依赖（requirements.txt）
            try:
                manager.install_plugin_requirements(plugin_name)
            except Exception:
                shutil.rmtree(permanent_dir, ignore_errors=True)
                if backup_dir and backup_dir.exists():
                    shutil.move(str(backup_dir), str(permanent_dir))
                raise

            if overwrite and backup_dir:
                # 升级已有插件
                try:
                    repo = PluginRepository(db)
                    existing = await repo.get_by_name(plugin_name)
                    if existing:
                        plugin = await manager.upgrade(
                            db,
                            plugin_id=existing.id,
                            new_entry_point=entry_point,
                        )
                    else:
                        plugin = await manager.install(
                            db, entry_point=entry_point, is_system=False,
                        )
                    # 升级成功，删除备份
                    shutil.rmtree(backup_dir, ignore_errors=True)
                except Exception:
                    # 升级失败：回滚文件
                    shutil.rmtree(permanent_dir, ignore_errors=True)
                    if backup_dir and backup_dir.exists():
                        shutil.move(str(backup_dir), str(permanent_dir))
                    raise
            else:
                # 全新安装
                # 标记是否为本地已有代码（目录已存在但 DB 无记录）
                is_local_code = permanent_dir.exists()
                try:
                    plugin = await manager.install(
                        db, entry_point=entry_point, is_system=False,
                    )
                except Exception:
                    # 安装失败：仅清理上传拷贝的目录，不删除本地已有代码
                    if not is_local_code:
                        shutil.rmtree(permanent_dir, ignore_errors=True)
                    raise

            # 上传安装的插件标记来源为 local
            from app.repositories.system.plugin_repository import PluginRepository as _PluginRepo
            try:
                _pr = _PluginRepo(db)
                await _pr.update(plugin.id, {"install_source": "local"})
            except Exception:
                pass

            # 自动启用插件（上传安装后自动启用，model_id 传递给 on_after_enable）
            enable_error: str | None = None
            try:
                plugin = await manager.enable_platform(
                    db, plugin.id,
                    admin_id=current_admin.id,
                    model_id=model_id,
                )
            except Exception as enable_exc:
                enable_error = str(enable_exc)
                logger.warning(
                    "Auto-enable after upload failed (plugin installed but not enabled): %s — %s",
                    plugin.name, enable_error,
                )

            resp = _mask_plugin_response(plugin)
            if enable_error:
                resp["enable_warning"] = enable_error
            return created(data=resp)

        @router.get("/{plugin_id}/assigned-tenants", summary="查看已分配租户列表")
        @action_read("action.plugin.list")
        async def get_assigned_tenants(
            request: Request,
            db: DbSession,
            current_admin: ActiveAdmin,
            plugin_id: int = Path(..., description="插件 ID"),
        ):
            """返回 scope=assigned_tenants 插件的已分配租户 ID 和名称"""
            from app.repositories.system.plugin_tenant_assignment_repository import (
                PluginTenantAssignmentRepository,
            )
            from app.models.tenant.tenant import Tenant
            from sqlalchemy import select

            service = self.get_service(db)
            plugin = await service.get_by_id(plugin_id)
            if not plugin:
                from app.exceptions import NotFoundException
                raise NotFoundException(message=_("plugin.not_found"))

            repo = PluginTenantAssignmentRepository(db)
            assignments = await repo.get_by_plugin(plugin_id)

            tenant_ids = [a.tenant_id for a in assignments]
            tenants_map: dict[int, str] = {}
            if tenant_ids:
                stmt = select(Tenant.id, Tenant.name).where(Tenant.id.in_(tenant_ids))
                result = await db.execute(stmt)
                tenants_map = {row[0]: row[1] for row in result.all()}

            return success(data=[
                {
                    "tenant_id": a.tenant_id,
                    "tenant_name": tenants_map.get(a.tenant_id, ""),
                    "assigned_by": a.assigned_by,
                    "assigned_at": a.assigned_at.isoformat() if a.assigned_at else None,
                }
                for a in assignments
            ])

        @router.post("/{plugin_id}/assign-tenants", summary="批量分配插件给租户")
        @action_update("action.plugin.update")
        async def assign_tenants(
            request: Request,
            db: DbSession,
            current_admin: ActiveAdmin,
            plugin_id: int = Path(..., description="插件 ID"),
            body: dict = None,
        ):
            """
            为 scope=assigned_tenants 的插件分配租户。
            同时自动创建 tenant_plugins 记录（is_active=True）。
            body: {"tenant_ids": [1, 2, 3]}
            """
            from app.repositories.system.plugin_tenant_assignment_repository import (
                PluginTenantAssignmentRepository,
            )
            from app.repositories.system.tenant_plugin_repository import TenantPluginRepository

            tenant_ids = (body or {}).get("tenant_ids", [])
            if not tenant_ids or not isinstance(tenant_ids, list):
                from app.exceptions import ValidationException
                raise ValidationException(message=_("plugin.tenant_ids_required"))

            service = self.get_service(db)
            plugin = await service.get_by_id(plugin_id)
            if not plugin:
                from app.exceptions import NotFoundException
                raise NotFoundException(message=_("plugin.not_found"))

            assign_repo = PluginTenantAssignmentRepository(db)
            tp_repo = TenantPluginRepository(db)

            created_assignments = await assign_repo.bulk_assign(
                plugin_id, tenant_ids, assigned_by=current_admin.id,
            )

            # 同步创建/激活 tenant_plugins 记录
            tp_count = 0
            for tid in tenant_ids:
                existing_tp = await tp_repo.get_by_tenant_and_plugin(tid, plugin_id)
                if existing_tp:
                    if not existing_tp.is_active:
                        await tp_repo.update(existing_tp.id, {"is_active": True})
                        tp_count += 1
                else:
                    await tp_repo.create({
                        "tenant_id": tid,
                        "plugin_id": plugin_id,
                        "is_active": True,
                        "config": None,
                    })
                    tp_count += 1

            await db.flush()

            from app.plugins.security import log_plugin_action
            log_plugin_action(
                action="assign_tenants",
                plugin_name=plugin.name,
                admin_id=current_admin.id,
                details={
                    "plugin_id": plugin_id,
                    "tenant_ids": tenant_ids,
                    "assignments_created": len(created_assignments),
                    "tenant_plugins_created": tp_count,
                },
            )

            return success(data={
                "assigned": len(created_assignments),
                "tenant_plugins_activated": tp_count,
            })

        @router.delete("/{plugin_id}/unassign-tenants", summary="批量取消分配租户")
        @action_update("action.plugin.update")
        async def unassign_tenants(
            request: Request,
            db: DbSession,
            current_admin: ActiveAdmin,
            plugin_id: int = Path(..., description="插件 ID"),
            body: dict = None,
        ):
            """
            取消插件对指定租户的分配。
            同时禁用 tenant_plugins 记录。
            body: {"tenant_ids": [1, 2, 3]}
            """
            from app.repositories.system.plugin_tenant_assignment_repository import (
                PluginTenantAssignmentRepository,
            )
            from app.repositories.system.tenant_plugin_repository import TenantPluginRepository

            tenant_ids = (body or {}).get("tenant_ids", [])
            if not tenant_ids or not isinstance(tenant_ids, list):
                from app.exceptions import ValidationException
                raise ValidationException(message=_("plugin.tenant_ids_required"))

            service = self.get_service(db)
            plugin = await service.get_by_id(plugin_id)
            if not plugin:
                from app.exceptions import NotFoundException
                raise NotFoundException(message=_("plugin.not_found"))

            assign_repo = PluginTenantAssignmentRepository(db)
            removed = await assign_repo.bulk_unassign(plugin_id, tenant_ids)

            # 同步禁用 tenant_plugins 记录
            tp_repo = TenantPluginRepository(db)
            tp_disabled = 0
            for tid in tenant_ids:
                existing_tp = await tp_repo.get_by_tenant_and_plugin(tid, plugin_id)
                if existing_tp and existing_tp.is_active:
                    await tp_repo.update(existing_tp.id, {"is_active": False})
                    tp_disabled += 1

            from app.plugins.security import log_plugin_action
            log_plugin_action(
                action="unassign_tenants",
                plugin_name=plugin.name,
                admin_id=current_admin.id,
                details={
                    "plugin_id": plugin_id,
                    "tenant_ids": tenant_ids,
                    "assignments_removed": removed,
                    "tenant_plugins_disabled": tp_disabled,
                },
            )

            return success(data={
                "unassigned": removed,
                "tenant_plugins_disabled": tp_disabled,
            })

        @router.get("/{plugin_id}/icon", summary="获取插件图标")
        async def get_plugin_icon(
            request: Request,
            db: DbSession,
            plugin_id: int = Path(..., description="插件 ID"),
        ):
            """读取插件目录下的图标文件（icon.png/icon.svg/icon.jpg）"""
            from app.exceptions import NotFoundException

            service = self.get_service(db)
            plugin = await service.get_by_id(plugin_id)
            if not plugin:
                raise NotFoundException(message=_("plugin.not_found"))

            plugins_base = FilePath(__file__).resolve().parent.parent.parent / "plugins"
            module_name = plugin.name.replace("-", "_")

            icon_names = ["icon.png", "icon.svg", "icon.jpg", "icon.jpeg", "icon.webp"]
            search_dirs = [
                plugins_base / module_name,
                plugins_base / plugin.name,
            ]
            media_types = {
                ".png": "image/png",
                ".svg": "image/svg+xml",
                ".jpg": "image/jpeg",
                ".jpeg": "image/jpeg",
                ".webp": "image/webp",
            }

            for d in search_dirs:
                if not d.is_dir():
                    continue
                for name in icon_names:
                    icon_path = d / name
                    if icon_path.exists():
                        ext = icon_path.suffix.lower()
                        return FileResponse(
                            path=str(icon_path),
                            media_type=media_types.get(ext, "image/png"),
                            headers={"Cache-Control": "public, max-age=86400"},
                        )

            raise NotFoundException(message=_("plugin.not_found"))

        @router.get("/{plugin_id}/readme", summary="获取插件文档")
        @action_read("action.plugin.list")
        async def get_plugin_readme(
            request: Request,
            db: DbSession,
            current_admin: ActiveAdmin,
            plugin_id: int = Path(..., description="插件 ID"),
            lang: str = Query("", description="Language code (e.g. zh-CN, en-US)"),
        ):
            """读取插件目录下的 README 文件（支持多语言：README.zh-CN.md → README.md 回退）"""
            from app.exceptions import NotFoundException

            service = self.get_service(db)
            plugin = await service.get_by_id(plugin_id)
            if not plugin:
                raise NotFoundException(message=_("plugin.not_found"))

            plugins_base = FilePath(__file__).resolve().parent.parent.parent / "plugins"
            module_name = plugin.name.replace("-", "_")

            search_dirs = [
                plugins_base / module_name,
                plugins_base / plugin.name,
                plugins_base / "builtin" / module_name,
                plugins_base / "demoPlugins" / module_name,
            ]

            # 多语言 README 优先级：README.{lang}.md → README.md
            readme_names: list[str] = []
            if lang:
                readme_names.extend([f"README.{lang}.md", f"readme.{lang}.md"])
            readme_names.extend(["README.md", "readme.md"])

            readme_content = None
            for d in search_dirs:
                if not d.is_dir():
                    continue
                for name in readme_names:
                    readme_path = d / name
                    if readme_path.exists():
                        readme_content = readme_path.read_text(encoding="utf-8")
                        break
                if readme_content is not None:
                    break

            return success(data={
                "plugin_name": plugin.name,
                "has_readme": readme_content is not None,
                "content": readme_content or "",
            })

        @router.get("/{plugin_id}/export", summary="导出插件为 .nap")
        @action_read("action.plugin.export")
        async def export_plugin_package(
            request: Request,
            db: DbSession,
            current_admin: ActiveAdmin,
            plugin_id: int = Path(..., description="插件 ID"),
        ):
            from app.plugins.packaging import pack_plugin, PackageError
            from app.exceptions import BusinessException, NotFoundException

            service = self.get_service(db)
            plugin = await service.get_by_id(plugin_id)
            if not plugin:
                raise NotFoundException(
                    message=_("plugin.not_found")
                )

            plugins_base = FilePath(__file__).resolve().parent.parent.parent / "plugins"
            module_name = plugin.name.replace("-", "_")
            plugin_dir = plugins_base / module_name
            if not plugin_dir.exists():
                plugin_dir = plugins_base / plugin.name
            if not plugin_dir.exists():
                plugin_dir = plugins_base / "builtin" / module_name
            if not plugin_dir.exists():
                plugin_dir = plugins_base / "builtin" / plugin.name
            if not plugin_dir.exists():
                raise NotFoundException(
                    message=_("plugin.plugin_dir_not_found")
                )

            # 使用持久化临时目录，避免 FileResponse 流式发送前目录被清理
            tmp_dir = tempfile.mkdtemp()
            try:
                nap_path = pack_plugin(
                    plugin_dir,
                    FilePath(tmp_dir) / f"{plugin.name}-{plugin.version}.nap",
                )
            except PackageError as e:
                shutil.rmtree(tmp_dir, ignore_errors=True)
                raise BusinessException(str(e)) from e

            return FileResponse(
                path=str(nap_path),
                filename=nap_path.name,
                media_type="application/zip",
                background=BackgroundTask(shutil.rmtree, tmp_dir, True),
            )


def _compute_file_diff(
    existing_dir: FilePath, new_dir: FilePath
) -> dict[str, list[str]]:
    """
    比较已安装插件目录与新上传插件目录的文件差异

    Args:
        existing_dir: 已安装的插件目录
        new_dir: 新上传解压的插件目录

    Returns:
        {"added": [...], "modified": [...], "removed": [...]}
    """
    import hashlib

    def _file_hash(path: FilePath) -> str:
        return hashlib.md5(path.read_bytes()).hexdigest()

    def _scan(base: FilePath) -> dict[str, str]:
        result: dict[str, str] = {}
        for f in base.rglob("*"):
            if f.is_file() and "__pycache__" not in f.parts:
                rel = f.relative_to(base).as_posix()
                result[rel] = _file_hash(f)
        return result

    old_files = _scan(existing_dir)
    new_files = _scan(new_dir)

    added = sorted(f for f in new_files if f not in old_files)
    removed = sorted(f for f in old_files if f not in new_files)
    modified = sorted(
        f for f in new_files
        if f in old_files and new_files[f] != old_files[f]
    )

    return {"added": added, "modified": modified, "removed": removed}


def _load_plugin_locales(plugin_name: str) -> dict[str, dict]:
    """
    从插件目录读取 locales/{lang}.json 和 frontend/locales/{lang}.json

    后端 locales/ 提供插件级 i18n（如 plugin.{name}.menu.*），
    前端 frontend/locales/ 提供组件级 i18n（如 {pluginName}.toolbar.*）。
    两者深度合并后返回。

    返回格式: {"zh-CN": {...}, "en-US": {...}}
    """
    import json

    plugins_base = FilePath(__file__).resolve().parent.parent.parent / "plugins"
    module_name = plugin_name.replace("-", "_")

    # 查找插件根目录
    plugin_root = None
    for candidate in [
        plugins_base / plugin_name,
        plugins_base / module_name,
        plugins_base / "builtin" / module_name,
        plugins_base / "demoPlugins" / module_name,
    ]:
        if candidate.is_dir():
            plugin_root = candidate
            break

    if not plugin_root:
        return {}

    def _deep_merge(base: dict, override: dict) -> dict:
        result = base.copy()
        for key, value in override.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = _deep_merge(result[key], value)
            else:
                result[key] = value
        return result

    result: dict[str, dict] = {}

    # 1. 加载后端 locales（plugin.xxx.* 格式，用于菜单名等）
    backend_locales_dir = plugin_root / "locales"
    if backend_locales_dir.is_dir():
        for locale_file in backend_locales_dir.glob("*.json"):
            lang = locale_file.stem
            try:
                with open(locale_file, encoding="utf-8") as f:
                    result[lang] = json.load(f)
            except (json.JSONDecodeError, OSError):
                pass

    # 2. 加载前端 locales（{pluginName}.* 格式，用于 Vue 组件）
    frontend_locales_dir = plugin_root / "frontend" / "locales"
    if frontend_locales_dir.is_dir():
        for locale_file in frontend_locales_dir.glob("*.json"):
            lang = locale_file.stem
            try:
                with open(locale_file, encoding="utf-8") as f:
                    data = json.load(f)
                    if lang in result:
                        result[lang] = _deep_merge(result[lang], data)
                    else:
                        result[lang] = data
            except (json.JSONDecodeError, OSError):
                pass

    return result


router = AdminPluginController.get_router()
