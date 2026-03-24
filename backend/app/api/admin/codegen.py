"""
CRUD 代码生成器管理端 API / Codegen Admin API

提供配置 CRUD、版本历史、预览、生成、回滚、DB 反射等 24 个端点
Provides config CRUD, version history, preview, generate, rollback, DB introspection (24 endpoints).

DEBUG 模式下可用 / Available in DEBUG mode only.
"""

from pathlib import Path

from fastapi import Body, HTTPException, Query, Request, status
from fastapi.responses import Response, StreamingResponse

from filelock import FileLock, Timeout

from app.codegen.manifest import ManifestManager
from app.codegen.migration_helper import run_rollback_migration_cleanup
from app.codegen.rollback import CodegenRollback
from app.core.config import settings
from app.core.base_controller import GlobalController
from app.core.deps import ActiveAdmin, DbSession, QueryParams
from app.core.i18n import _
from app.core.response import paginated, success
from app.enums.codegen import CodegenConfigStatusEnum
from app.enums.rbac import PermissionScope
from app.exceptions import NotFoundException
from app.rbac.decorators import (
    MenuConfig,
    action_create,
    action_delete,
    action_read,
    action_update,
    permission_resource,
)
from app.schemas.codegen import (
    CodegenGenerateBodySchema,
    CodegenConfigCreate,
    CodegenConfigResponse,
    CodegenConfigUpdate,
    CodegenWorkbenchItemSchema,
    CodegenWorkbenchSummarySchema,
    CodegenPreviewBodySchema,
    CodegenValidateBodySchema,
    CodegenVersionItemSchema,
    ComponentInfoSchema,
    GenerateResultSchema,
    PresetInfoSchema,
    PreviewResultSchema,
    RollbackResultSchema,
    ValidationResultSchema,
    TableInfoSchema,
    ColumnInfoSchema,
    TypeInfoSchema,
)
from app.services.system.codegen_service import CodegenService


def _require_debug() -> None:
    """DEBUG 守卫：非 DEBUG 模式抛出 403 / DEBUG guard."""
    if not settings.DEBUG:
        raise HTTPException(status_code=403, detail=_("codegen.debug_only"))


from app.codegen.constants import CODEGEN_PROJECT_ROOT as _PROJECT_ROOT

_LOCK_DIR = _PROJECT_ROOT / ".codegen_locks"

_GLOBAL_LOCK_FILE = "_codegen_global.lock"


def _codegen_global_lock(timeout: int = 60) -> FileLock:
    """Global codegen lock to prevent concurrent generate/rollback (shared files like models/__init__.py)."""
    _LOCK_DIR.mkdir(parents=True, exist_ok=True)
    return FileLock(_LOCK_DIR / _GLOBAL_LOCK_FILE, timeout=timeout)


@permission_resource(
    resource="codegen",
    name="menu.admin.codegen",
    scope=PermissionScope.ADMIN,
    parent_resource="system_config",
    menu=MenuConfig(
        icon="lucide:code-2",
        path="/system/codegen",
        component="system/codegen/index",
        parent="system_maintenance",
        sort_order=90,
    ),
)
class AdminCodegenController(GlobalController):
    """
    代码生成器管理控制器 / Codegen Admin Controller

    21 个端点，DEBUG 守卫 / 21 endpoints, DEBUG guard
    """

    prefix = "/codegen"
    tags = ["Codegen"]
    service_class = CodegenService

    @staticmethod
    def _serialize_config(
        obj,
        *,
        manifest_present: bool = False,
    ) -> CodegenConfigResponse:
        guard = CodegenService.build_delete_guard(
            obj, manifest_present=manifest_present
        )
        return CodegenConfigResponse.from_model(
            obj,
            manifest_present=manifest_present,
            delete_allowed=guard.allowed,
            delete_reason_code=guard.reason_code,
            delete_reason_message=guard.message,
        )

    def _register_routes(self) -> None:
        """注册路由 / Register routes"""
        router = self.router

        # ========== 配置 CRUD ==========
        @router.get("/configs", summary=_("codegen.api.configs.list"))
        @action_read("action.codegen.list")
        async def list_configs(
            request: Request,
            db: DbSession,
            spec: QueryParams,
            current_admin: ActiveAdmin,
        ):
            _require_debug()
            service = CodegenService(db)
            items, total = await service.query_list(spec)
            manifest = ManifestManager(_PROJECT_ROOT)
            res_set, cid_set = manifest.manifest_index()

            def _row_has_manifest(x) -> bool:
                if x.resource and x.resource in res_set:
                    return True
                return x.id in cid_set

            return paginated(
                items=[
                    self._serialize_config(x, manifest_present=_row_has_manifest(x))
                    for x in items
                ],
                total=total,
                page=spec.page or 1,
                page_size=spec.size or 20,
            )

        @router.get("/workbench-summary", summary=_("codegen.api.workbench_summary"))
        @action_read("action.codegen.list")
        async def get_workbench_summary(
            request: Request,
            db: DbSession,
            current_admin: ActiveAdmin,
        ):
            _require_debug()
            service = CodegenService(db)
            summary = await service.get_workbench_summary(project_root=_PROJECT_ROOT)

            def _serialize_item(entry) -> CodegenWorkbenchItemSchema:
                return CodegenWorkbenchItemSchema(
                    id=entry.config.id,
                    name=entry.config.name,
                    resource=entry.config.resource,
                    status=entry.config.status,
                    manifest_present=entry.manifest_present,
                    delete_allowed=entry.delete_guard.allowed,
                    delete_reason_message=entry.delete_guard.message,
                    last_generated_at=entry.config.last_generated_at,
                    generation_count=entry.config.generation_count or 0,
                    last_error=entry.config.last_error,
                )

            validated = CodegenWorkbenchSummarySchema.model_validate(
                {
                    "stats": summary["stats"],
                    "sections": {
                        key: [_serialize_item(entry).model_dump() for entry in entries]
                        for key, entries in summary["sections"].items()
                    },
                }
            )
            return success(data=validated.model_dump())

        @router.get("/configs/{id}", summary=_("codegen.api.configs.detail"))
        @action_read("action.codegen.detail")
        async def get_config(
            request: Request,
            id: int,
            db: DbSession,
            current_admin: ActiveAdmin,
        ):
            _require_debug()
            service = CodegenService(db)
            obj = await service.get_by_id(id)
            if not obj:
                raise NotFoundException(message=_("codegen.config_not_found"))
            manifest = ManifestManager(_PROJECT_ROOT)
            mp = manifest.find_entry_for_config(obj.resource, obj.id) is not None
            return success(data=self._serialize_config(obj, manifest_present=mp))

        @router.post("/configs", summary=_("codegen.api.configs.create"))
        @action_create("action.codegen.create")
        async def create_config(
            request: Request,
            db: DbSession,
            body: CodegenConfigCreate,
            current_admin: ActiveAdmin,
        ):
            _require_debug()
            service = CodegenService(db)
            obj = await service.create(body.model_dump())
            await db.commit()
            return success(
                data=self._serialize_config(obj, manifest_present=False),
                message=_("common.created"),
            )

        @router.put("/configs/{id}", summary=_("codegen.api.configs.update"))
        @action_update("action.codegen.update")
        async def update_config(
            request: Request,
            id: int,
            db: DbSession,
            body: CodegenConfigUpdate,
            current_admin: ActiveAdmin,
        ):
            _require_debug()
            service = CodegenService(db)
            obj = await service.update(id, body.model_dump(exclude_unset=True))
            if not obj:
                raise NotFoundException(message=_("codegen.config_not_found"))
            await db.commit()
            manifest = ManifestManager(_PROJECT_ROOT)
            mp = manifest.find_entry_for_config(obj.resource, obj.id) is not None
            return success(
                data=self._serialize_config(obj, manifest_present=mp),
                message=_("common.updated"),
            )

        @router.delete("/configs/{id}", summary=_("codegen.api.configs.delete"))
        @action_delete("action.codegen.delete")
        async def delete_config(
            request: Request,
            id: int,
            db: DbSession,
            current_admin: ActiveAdmin,
        ):
            _require_debug()
            service = CodegenService(db)
            await service.assert_can_delete(id, project_root=_PROJECT_ROOT)
            await service.delete(id)
            await db.commit()
            return success(message=_("common.deleted"))

        @router.post(
            "/configs/{id}/duplicate", summary=_("codegen.api.configs.duplicate")
        )
        @action_create("action.codegen.duplicate")
        async def duplicate_config(
            request: Request,
            id: int,
            db: DbSession,
            current_admin: ActiveAdmin,
        ):
            _require_debug()
            service = CodegenService(db)
            obj = await service.duplicate(id)
            await db.commit()
            return success(
                data=self._serialize_config(obj, manifest_present=False),
                message=_("common.created"),
            )

        # ========== 配置版本历史 / Config Version History ==========
        @router.get("/configs/{id}/versions", summary=_("codegen.api.configs.versions"))
        @action_read("action.codegen.update")
        async def list_config_versions(
            request: Request,
            id: int,
            db: DbSession,
            current_admin: ActiveAdmin,
            limit: int = Query(50, ge=1, le=200),
        ):
            _require_debug()
            service = CodegenService(db)
            config = await service.get_by_id(id)
            if not config:
                raise NotFoundException(message=_("codegen.config_not_found"))
            versions = await service.list_versions(id, limit=limit)
            validated = [CodegenVersionItemSchema.model_validate(v) for v in versions]
            return success(data=[v.model_dump() for v in validated])

        @router.get(
            "/configs/{id}/versions/{vid}", summary=_("codegen.api.configs.version_get")
        )
        @action_read("action.codegen.update")
        async def get_config_version(
            request: Request,
            id: int,
            vid: int,
            db: DbSession,
            current_admin: ActiveAdmin,
        ):
            _require_debug()
            service = CodegenService(db)
            config = await service.get_by_id(id)
            if not config:
                raise NotFoundException(message=_("codegen.config_not_found"))
            config_json = await service.get_version_config(id, vid)
            if config_json is None:
                raise NotFoundException(message=_("common.not_found"))
            return success(data={"config_json": config_json})

        @router.post(
            "/configs/{id}/versions/{vid}/restore",
            summary=_("codegen.api.configs.restore_version"),
        )
        @action_update("action.codegen.update")
        async def restore_config_version(
            request: Request,
            id: int,
            vid: int,
            db: DbSession,
            current_admin: ActiveAdmin,
        ):
            _require_debug()
            service = CodegenService(db)
            obj = await service.restore_version(id, vid)
            if not obj:
                raise NotFoundException(message=_("common.not_found"))
            await db.commit()
            manifest = ManifestManager(_PROJECT_ROOT)
            mp = manifest.find_entry_for_config(obj.resource, obj.id) is not None
            return success(
                data=self._serialize_config(obj, manifest_present=mp),
                message=_("common.updated"),
            )

        # ========== 元数据 ========== / Metadata
        @router.get("/types", summary=_("codegen.api.types"))
        @action_read("action.codegen.types")
        async def get_types(request: Request, current_admin: ActiveAdmin):
            _require_debug()
            from app.codegen.type_registry import type_registry

            type_map = type_registry.get_type_map()
            items = [
                TypeInfoSchema.model_validate(
                    {
                        "type": k,
                        "python_type": v.get("python_type", ""),
                        "ts_type": v.get("ts_type", ""),
                        "form_component": v.get("default_form_component", ""),
                        "search_type": v.get("default_search_type"),
                    }
                )
                for k, v in type_map.items()
            ]
            return success(data=[x.model_dump() for x in items])

        @router.get("/components", summary=_("codegen.api.components"))
        @action_read("action.codegen.components")
        async def get_components(request: Request, current_admin: ActiveAdmin):
            _require_debug()
            from app.codegen.type_registry import type_registry

            type_map = type_registry.get_type_map()
            seen: set[str] = set()
            raw: list[dict] = []
            _advanced = {
                "ImageUpload",
                "RichText",
                "FilePicker",
                "CronPicker",
                "IconPicker",
                "CodeEditor",
            }
            _select_category = {"select", "ApiSelect"}
            for v in type_map.values():
                comp = v.get("default_form_component") or ""
                if comp and comp not in seen:
                    seen.add(comp)
                    cat = (
                        "advanced"
                        if comp in _advanced
                        else ("select" if comp in _select_category else "input")
                    )
                    raw.append(
                        {
                            "name": comp,
                            "label": comp.replace("_", " ").title(),
                            "category": cat,
                        }
                    )
            raw.sort(key=lambda x: (x["category"], x["name"]))
            components = [ComponentInfoSchema.model_validate(x) for x in raw]
            return success(data=[x.model_dump() for x in components])

        @router.get("/models", summary=_("codegen.api.models"))
        @action_read("action.codegen.models")
        async def get_models(request: Request, current_admin: ActiveAdmin):
            _require_debug()
            from app.models import __all__ as model_all

            return success(data=sorted(model_all))

        @router.get("/presets", summary=_("codegen.api.presets.list"))
        @action_read("action.codegen.presets")
        async def list_presets(request: Request, current_admin: ActiveAdmin):
            _require_debug()
            items = CodegenService.list_available_presets()
            validated = [PresetInfoSchema.model_validate(item) for item in items]
            return success(data=[item.model_dump() for item in validated])

        @router.get("/presets/{name}", summary=_("codegen.api.presets.get"))
        @action_read("action.codegen.presets")
        async def get_preset(
            request: Request,
            name: str,
            current_admin: ActiveAdmin,
        ):
            _require_debug()
            import re

            # 防止路径遍历：仅允许字母、数字、下划线、连字符
            # Prevent path traversal: only allow alphanumeric, underscore, hyphen
            if not re.match(r"^[a-zA-Z0-9_-]+$", name):
                raise NotFoundException(message=_("codegen.preset_not_found"))
            presets_dir = (
                Path(__file__).resolve().parent.parent.parent
                / "codegen"
                / "templates"
                / "presets"
            )
            path = (presets_dir / f"{name}.yaml").resolve()
            if not path.is_relative_to(presets_dir.resolve()):
                raise NotFoundException(message=_("codegen.preset_not_found"))
            if not path.exists():
                raise NotFoundException(message=_("codegen.preset_not_found"))
            preset = CodegenService.get_preset_detail(name)
            if not preset:
                raise NotFoundException(message=_("codegen.preset_not_found"))
            return success(data=preset)

        @router.get("/parent-resources", summary=_("codegen.api.parent_resources"))
        @action_read("action.codegen.parent_resources")
        async def get_parent_resources(request: Request, current_admin: ActiveAdmin):
            _require_debug()
            from app.codegen.options import PARENT_RESOURCES

            return success(data=PARENT_RESOURCES)

        @router.get("/options", summary=_("codegen.api.options"))
        @action_read("action.codegen.options")
        async def get_options(request: Request, current_admin: ActiveAdmin):
            _require_debug()
            from app.codegen.options import get_codegen_options

            return success(data=get_codegen_options())

        # ========== DB 反射 ==========
        @router.get("/db/tables", summary=_("codegen.api.db.tables"))
        @action_read("action.codegen.db")
        async def list_db_tables(
            request: Request,
            db: DbSession,
            current_admin: ActiveAdmin,
        ):
            _require_debug()
            service = CodegenService(db)
            items = service.introspect_tables()
            validated = [TableInfoSchema.model_validate(x) for x in items]
            return success(data=[x.model_dump() for x in validated])

        @router.get("/db/tables/{name}/columns", summary=_("codegen.api.db.columns"))
        @action_read("action.codegen.db")
        async def get_table_columns(
            request: Request,
            name: str,
            db: DbSession,
            current_admin: ActiveAdmin,
        ):
            _require_debug()
            service = CodegenService(db)
            if name not in service.get_table_names():
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=_("codegen.db.table_not_found", name=name),
                )
            items = service.introspect_columns(name)
            validated = [ColumnInfoSchema.model_validate(x) for x in items]
            return success(data=[x.model_dump() for x in validated])

        @router.get("/db/tables/{name}/rows", summary=_("codegen.api.db.rows"))
        @action_read("action.codegen.db")
        async def get_table_rows(
            request: Request,
            name: str,
            db: DbSession,
            current_admin: ActiveAdmin,
            value_field: str = "id",
            display_field: str = "name",
            limit: int = 200,
            search: str | None = None,
        ):
            _require_debug()
            service = CodegenService(db)
            if name not in service.get_table_names():
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=_("codegen.db.table_not_found", name=name),
                )
            data = service.introspect_rows(
                table_name=name,
                value_field=value_field,
                display_field=display_field,
                limit=min(limit, 500),
                search=search,
            )
            return success(data=data)

        @router.post("/db/import", summary=_("codegen.api.db.import"))
        @action_create("action.codegen.db")
        async def import_from_table(
            request: Request,
            db: DbSession,
            current_admin: ActiveAdmin,
            table_name: str = Body(..., embed=True),
        ):
            _require_debug()
            service = CodegenService(db)
            if table_name not in service.get_table_names():
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=_("codegen.db.table_not_found", name=table_name),
                )
            data = service.import_from_table(table_name)
            return success(data=data)

        # ========== 核心操作 ========== / Core operations
        @router.post("/validate", summary=_("codegen.api.validate"))
        @action_read("action.codegen.validate")
        async def validate_config(
            request: Request,
            db: DbSession,
            current_admin: ActiveAdmin,
            body: CodegenValidateBodySchema,
        ):
            _require_debug()
            service = CodegenService(db)
            config = body.config_json or {}
            result = service.validate(config, mode=body.mode)
            validated = ValidationResultSchema.model_validate(result)
            return success(data=validated.model_dump())

        @router.post("/preview", summary=_("codegen.api.preview"))
        @action_read("action.codegen.preview")
        async def preview_generate(
            request: Request,
            db: DbSession,
            current_admin: ActiveAdmin,
            body: CodegenPreviewBodySchema,
        ):
            _require_debug()
            service = CodegenService(db)
            config = body.config_json or {}
            result = service.preview(config, step=body.step, project_root=_PROJECT_ROOT)
            validated = PreviewResultSchema.model_validate(result)
            return success(data=validated.model_dump())

        @router.post("/preview/download", summary=_("codegen.api.preview_download"))
        @action_read("action.codegen.preview")
        async def preview_download_zip(
            request: Request,
            db: DbSession,
            current_admin: ActiveAdmin,
            body: CodegenPreviewBodySchema,
            step: str | None = None,
        ):
            """预览 ZIP 下载（不写入项目）/ Preview ZIP download (no write to project)."""
            _require_debug()
            try:
                service = CodegenService(db)
                config = body.config_json or {}
                step_val = body.step or step
                zip_bytes = service.preview_zip(config, step=step_val)
                return Response(
                    content=zip_bytes,
                    media_type="application/zip",
                    headers={
                        "Content-Disposition": "attachment; filename=codegen_preview.zip",
                    },
                )
            except Exception as e:
                err_msg = str(e)
                if any(s in err_msg for s in ("/", "\\", ".py", "Traceback")):
                    err_msg = _("codegen.preview_download_error_sanitized")
                raise HTTPException(
                    status_code=400,
                    detail={"error": err_msg, "code": "preview_download_failed"},
                )

        @router.post("/generate", summary=_("codegen.api.generate"))
        @action_create("action.codegen.generate")
        async def do_generate(
            request: Request,
            db: DbSession,
            current_admin: ActiveAdmin,
            body: CodegenGenerateBodySchema,
        ):
            _require_debug()
            service = CodegenService(db)
            if body.config_id is not None:
                inp = body.config_id
            elif body.config_json is not None:
                inp = body.config_json
            else:
                raise HTTPException(400, _("codegen.need_config_id_or_json"))

            resource = None
            if body.config_id is not None:
                cfg = await service.get_by_id(body.config_id)
                resource = cfg.resource if cfg else None
            elif body.config_json:
                from app.codegen.config_parser import ConfigParser

                parsed = ConfigParser().parse(body.config_json)
                resource = parsed.resource

            try:
                lock = _codegen_global_lock()
                lock.acquire(timeout=60)
            except Timeout:
                raise HTTPException(409, _("codegen.concurrent_operation"))

            try:
                output = await service.generate(
                    inp, force=body.force, project_root=_PROJECT_ROOT
                )
                result = output.result
                data = {
                    "success": result.success,
                    "files_created": result.files_created,
                    "files_modified": result.files_modified,
                    "conflicts": result.conflicts,
                    "errors": result.errors,
                    "backup_dir": result.backup_dir,
                    "config_id": output.config_id,
                    "resource": output.resource,
                    "module": output.module,
                    "table_name": output.table_name,
                }
                if body.auto_migrate and result.success and output.resource:
                    migrate_result = CodegenService.run_auto_migrate(
                        output.resource, _PROJECT_ROOT
                    )
                    data["migration"] = migrate_result
                    if migrate_result.get("success"):
                        if migrate_result.get("migration_path"):
                            manifest = ManifestManager(_PROJECT_ROOT)
                            manifest.update_migration_file(
                                output.resource, migrate_result["migration_path"]
                            )
                        if output.config_id is not None:
                            await service.update(
                                output.config_id,
                                {
                                    "status": CodegenConfigStatusEnum.APPLIED.value,
                                    "last_error": None,
                                },
                            )
                    else:
                        err_msg = (
                            f"auto_migrate failed at {migrate_result.get('phase', 'unknown')}: "
                            f"{migrate_result.get('error', 'unknown error')}"
                        )
                        data["success"] = False
                        data["errors"] = list(data.get("errors") or [])
                        data["errors"].append(err_msg)
                        if output.config_id is not None:
                            await service.update(
                                output.config_id,
                                {
                                    "status": CodegenConfigStatusEnum.GENERATED.value,
                                    "last_error": err_msg,
                                },
                            )
                validated = GenerateResultSchema.model_validate(data)
                return success(data=validated.model_dump())
            finally:
                lock.release()

        @router.get("/download/{config_id}", summary=_("codegen.api.download"))
        @action_read("action.codegen.download")
        async def download_zip(
            request: Request,
            config_id: int,
            db: DbSession,
            current_admin: ActiveAdmin,
        ):
            _require_debug()
            service = CodegenService(db)
            zip_bytes = await service.download(config_id, project_root=_PROJECT_ROOT)
            return StreamingResponse(
                iter([zip_bytes]),
                media_type="application/zip",
                headers={
                    "Content-Disposition": f"attachment; filename=codegen_{config_id}.zip"
                },
            )

        @router.get("/history", summary=_("codegen.api.history"))
        @action_read("action.codegen.history")
        async def get_history(
            request: Request,
            db: DbSession,
            current_admin: ActiveAdmin,
            resource: str | None = None,
        ):
            _require_debug()
            from app.codegen.manifest import ManifestManager

            manifest = ManifestManager(_PROJECT_ROOT)
            entries = manifest.list_entries()
            if resource:
                entries = [e for e in entries if e.resource == resource]
            data = [
                {
                    "resource": e.resource,
                    "module": e.module,
                    "generated_at": e.generated_at,
                    "config_id": e.config_id,
                    "file_count": len(e.files),
                }
                for e in entries
            ]
            return success(data=data)

        # ========== 回滚 ========== / Rollback
        @router.delete("/configs/{id}/rollback", summary=_("codegen.api.rollback"))
        @action_delete("action.codegen.rollback")
        async def rollback_config(
            request: Request,
            id: int,
            db: DbSession,
            current_admin: ActiveAdmin,
            force: bool = False,
            dry_run: bool = False,
        ):
            _require_debug()
            service = CodegenService(db)
            config = await service.get_by_id(id)
            if not config:
                raise NotFoundException(message=_("codegen.config_not_found"))
            manifest = ManifestManager(_PROJECT_ROOT)
            entry = manifest.find_entry_for_config(config.resource, id)
            if not entry:
                raise HTTPException(
                    status.HTTP_400_BAD_REQUEST,
                    _("codegen.rollback.no_manifest_entry"),
                )
            resource = entry.resource
            migration_file = entry.migration_file

            try:
                lock = _codegen_global_lock()
                lock.acquire(timeout=60)
            except Timeout:
                raise HTTPException(409, _("codegen.concurrent_operation"))

            try:
                result = await service.rollback_async(
                    id, force=force, dry_run=dry_run, project_root=_PROJECT_ROOT
                )

                migration_cleaned = False
                if not dry_run and resource and result.success:
                    migration_cleaned = run_rollback_migration_cleanup(
                        resource=resource,
                        migration_file=migration_file,
                        project_root=_PROJECT_ROOT,
                        force_drop=force,
                    )

                overall_success = result.success
                errors = list(result.errors)
                if not dry_run and resource and result.success:
                    if migration_cleaned:
                        manifest.remove_entry(resource)
                        if config:
                            await service.update(
                                id,
                                {
                                    "status": CodegenConfigStatusEnum.ROLLED_BACK.value,
                                    "generated_files": None,
                                    "last_error": None,
                                },
                            )
                    else:
                        overall_success = False
                        rollback_err = _("codegen.rollback.cleanup_failed")
                        errors.append(rollback_err)
                        if config:
                            await service.update(id, {"last_error": rollback_err})

                data = {
                    "success": overall_success,
                    "files_deleted": result.files_deleted,
                    "files_modified": result.files_modified,
                    "files_skipped": result.files_skipped,
                    "manual_steps": result.manual_steps,
                    "errors": errors,
                    "migration_cleaned": migration_cleaned,
                }
                validated = RollbackResultSchema.model_validate(data)
                return success(data=validated.model_dump())
            finally:
                lock.release()

        @router.delete(
            "/rollback/{resource}",
            summary=_("codegen.api.rollback_by_resource"),
        )
        @action_delete("action.codegen.rollback")
        async def rollback_by_resource(
            request: Request,
            resource: str,
            db: DbSession,
            current_admin: ActiveAdmin,
            force: bool = False,
            dry_run: bool = False,
        ):
            """按 resource 回滚 / Rollback by resource name."""
            _require_debug()
            manifest = ManifestManager(_PROJECT_ROOT)
            entry = manifest.get_entry(resource)
            if not entry:
                raise HTTPException(
                    400,
                    _("codegen.rollback.no_manifest_entry"),
                )
            migration_file = entry.migration_file if entry else None

            try:
                lock = _codegen_global_lock()
                lock.acquire(timeout=60)
            except Timeout:
                raise HTTPException(409, _("codegen.concurrent_operation"))

            try:
                rb = CodegenRollback(_PROJECT_ROOT)
                result = rb.rollback(resource=resource, force=force, dry_run=dry_run)

                migration_cleaned = False
                if not dry_run and result.success:
                    migration_cleaned = run_rollback_migration_cleanup(
                        resource=resource,
                        migration_file=migration_file,
                        project_root=_PROJECT_ROOT,
                        force_drop=force,
                    )

                svc = CodegenService(db)
                cfg = await svc.get_by_resource(resource) if not dry_run else None
                overall_success = result.success
                errors = list(result.errors)
                if not dry_run and result.success:
                    if migration_cleaned:
                        manifest.remove_entry(resource)
                        if cfg:
                            await svc.update(
                                cfg.id,
                                {
                                    "status": CodegenConfigStatusEnum.ROLLED_BACK.value,
                                    "generated_files": None,
                                    "last_error": None,
                                },
                            )
                    else:
                        overall_success = False
                        rollback_err = _("codegen.rollback.cleanup_failed")
                        errors.append(rollback_err)
                        if cfg:
                            await svc.update(cfg.id, {"last_error": rollback_err})

                data = {
                    "success": overall_success,
                    "files_deleted": result.files_deleted,
                    "files_modified": result.files_modified,
                    "files_skipped": result.files_skipped,
                    "manual_steps": result.manual_steps,
                    "errors": errors,
                    "migration_cleaned": migration_cleaned,
                }
                validated = RollbackResultSchema.model_validate(data)
                return success(data=validated.model_dump())
            finally:
                lock.release()


router = AdminCodegenController.get_router()
