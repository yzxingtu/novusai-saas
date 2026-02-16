"""
平台管理端插件管理 API

提供插件的安装、卸载、启用/禁用、列表、详情等管理接口
"""

import shutil
import tempfile
from pathlib import Path as FilePath

from fastapi import Path, Query, Request, UploadFile
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
from app.services.system.plugin_service import PluginService


def _mask_plugin_response(plugin) -> dict:
    """序列化 Plugin 并对敏感配置字段脱敏"""
    from app.plugins.security import mask_sensitive_config
    resp = PluginResponse.model_validate(plugin, from_attributes=True).model_dump()
    if resp.get("default_config") and resp.get("config_schema"):
        resp["default_config"] = mask_sensitive_config(
            resp["default_config"], resp["config_schema"]
        )
    return resp


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
            await manager.uninstall(db, plugin_id)
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
        ):
            from app.plugins.manager import get_plugin_manager

            manager = get_plugin_manager()
            plugin = await manager.enable_platform(db, plugin_id)
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
            plugin = await manager.disable_platform(db, plugin_id)
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

        @router.post("/upload", summary="上传插件包安装（.zip / .nap）")
        @action_create("action.plugin.upload")
        async def upload_plugin(
            request: Request,
            db: DbSession,
            current_admin: ActiveAdmin,
            file: UploadFile = ...,
            overwrite: bool = Query(False, description="Overwrite existing plugin (upgrade)"),
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

                if permanent_dir.exists():
                    if not overwrite:
                        # 返回冲突信息，前端可选择覆盖
                        repo = PluginRepository(db)
                        existing = await repo.get_by_name(plugin_name)
                        return success(data={
                            "conflict": True,
                            "plugin_name": plugin_name,
                            "existing_version": existing.version if existing else None,
                            "new_version": manifest.get("version", ""),
                            "message": _("plugin.upload_conflict"),
                        })

                    # 覆盖模式：备份旧目录 → 拷贝新文件
                    backup_dir = permanent_dir.with_suffix(".bak")
                    if backup_dir.exists():
                        shutil.rmtree(backup_dir, ignore_errors=True)
                    shutil.move(str(permanent_dir), str(backup_dir))
                    try:
                        shutil.copytree(plugin_dir, permanent_dir)
                    except Exception:
                        # 拷贝失败则回滚
                        shutil.rmtree(permanent_dir, ignore_errors=True)
                        shutil.move(str(backup_dir), str(permanent_dir))
                        raise
                else:
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
                try:
                    plugin = await manager.install(
                        db, entry_point=entry_point, is_system=False,
                    )
                except Exception:
                    shutil.rmtree(permanent_dir, ignore_errors=True)
                    raise

            return created(data=_mask_plugin_response(plugin))

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
            plugin_dir = plugins_base / plugin.name
            if not plugin_dir.exists():
                plugin_dir = (
                    FilePath(__file__).resolve().parent.parent.parent
                    / "plugins" / "builtin"
                )
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


def _load_plugin_locales(plugin_name: str) -> dict[str, dict]:
    """
    从插件目录读取 locales/{lang}.json 文件

    返回格式: {"zh-CN": {...}, "en-US": {...}}
    """
    import json

    plugins_base = FilePath(__file__).resolve().parent.parent.parent / "plugins"
    locales_dir = plugins_base / plugin_name / "locales"
    if not locales_dir.is_dir():
        # 尝试下划线目录名（Python 包命名）
        locales_dir = plugins_base / plugin_name.replace("-", "_") / "locales"
    if not locales_dir.is_dir():
        # 尝试 builtin 目录
        locales_dir = plugins_base / "builtin" / plugin_name / "locales"
        if not locales_dir.is_dir():
            return {}

    result: dict[str, dict] = {}
    for locale_file in locales_dir.glob("*.json"):
        lang = locale_file.stem  # e.g. "zh-CN", "en-US"
        try:
            with open(locale_file, encoding="utf-8") as f:
                result[lang] = json.load(f)
        except (json.JSONDecodeError, OSError):
            pass
    return result


router = AdminPluginController.get_router()
