"""
CRUD 代码生成服务 / Codegen Service

提供代码生成配置的业务逻辑
Provides codegen config business logic.
"""

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.codegen.config_parser import ConfigParser
from app.codegen.db_introspector import DbIntrospector
from app.codegen.preset_loader import get_preset as load_codegen_preset
from app.codegen.preset_loader import list_presets as list_codegen_presets
from dataclasses import dataclass

from app.codegen.file_writer import FileWriter, WriteResult
from app.codegen.generator import CodeGenerator, GeneratedFile
from app.codegen.manifest import ManifestEntry, ManifestManager
from app.codegen.rollback import CodegenRollback, RollbackResult
from app.codegen.type_registry import type_registry
from app.codegen.zip_exporter import export_zip, format_code
from app.core.base_service import GlobalService
from app.core.i18n import _
from app.enums.codegen import CodegenConfigStatusEnum
from app.exceptions import ConflictException, NotFoundException
from app.models.system.codegen_config import CodegenConfig
from app.models.system.codegen_config_version import CodegenConfigVersion
from app.repositories.system.codegen_config_repository import (
    CodegenConfigRepository,
)
from app.repositories.system.codegen_config_version_repository import (
    CodegenConfigVersionRepository,
)

from app.codegen.constants import CODEGEN_PROJECT_ROOT as _PROJECT_ROOT


@dataclass
class GenerateOutput:
    """Generate 输出，包含 WriteResult 与配置元数据 / Generate output with result and config metadata."""

    result: WriteResult
    config_id: int | None = None
    resource: str | None = None
    module: str | None = None
    table_name: str | None = None


@dataclass(frozen=True)
class CodegenDeleteGuard:
    """Delete guard result / 删除保护判断结果."""

    allowed: bool
    reason_code: str | None = None
    message: str | None = None


@dataclass(frozen=True)
class CodegenWorkbenchEntry:
    """Workbench entry / 工作台条目."""

    config: CodegenConfig
    manifest_present: bool
    delete_guard: CodegenDeleteGuard


class CodegenService(GlobalService[CodegenConfig, CodegenConfigRepository]):
    """
    CRUD 代码生成服务 / Codegen service.

    平台级服务，无企业隔离。基础 CRUD，后续阶段会扩展 preview/generate 等
    Platform-level service, no tenant isolation.
    """

    model = CodegenConfig
    repository_class = CodegenConfigRepository

    @staticmethod
    def _derive_top_level_fields(config_json: dict[str, Any]) -> dict[str, Any]:
        """从 config_json 派生顶层字段，统一以 config_json 为事实源 / Derive top-level fields from config_json."""
        parsed = ConfigParser().parse(config_json)
        display_name = parsed.display_name or parsed.resource
        display_name_en = (
            parsed.display_name_en or parsed.resource.replace("_", " ").title()
        )
        return {
            "name": config_json.get("name") or display_name,
            "resource": parsed.resource,
            "module": parsed.module,
            "display_name": display_name,
            "display_name_en": display_name_en,
        }

    @classmethod
    def _sync_data_from_config_json(cls, data: dict[str, Any]) -> None:
        """若包含 config_json，则同步顶层字段 / Sync top-level fields from config_json when present."""
        config_json = data.get("config_json")
        if isinstance(config_json, dict):
            data.update(cls._derive_top_level_fields(config_json))

    @staticmethod
    def _sync_config_json_from_top_level(
        base_config_json: dict[str, Any] | None,
        data: dict[str, Any],
    ) -> dict[str, Any] | None:
        """当仅更新顶层字段时，回写到 config_json / Push top-level field updates back into config_json."""
        tracked_fields = (
            "name",
            "resource",
            "module",
            "display_name",
            "display_name_en",
        )
        if not any(
            field in data and data[field] is not None for field in tracked_fields
        ):
            return None
        config_json = dict(base_config_json or {})
        for field in tracked_fields:
            if field in data and data[field] is not None:
                config_json[field] = data[field]
        return config_json

    @staticmethod
    def _build_generated_files_payload(
        result: WriteResult,
        *,
        resource: str,
        module: str,
        table_name: str,
    ) -> dict[str, Any]:
        """生成持久化 generated_files 载荷 / Build generated_files payload."""
        return {
            "resource": resource,
            "module": module,
            "table_name": table_name,
            "files_created": list(result.files_created),
            "files_modified": list(result.files_modified),
            "conflicts": list(result.conflicts),
        }

    @staticmethod
    def _iter_manifest_snapshot_paths(entry: ManifestEntry) -> list[str]:
        """提取 manifest 中可下载的文件路径 / Extract downloadable snapshot paths from manifest."""
        ordered_paths: list[str] = []
        seen: set[str] = set()

        for item in entry.files:
            raw_path = str(item.get("path") or "").strip()
            if not raw_path or raw_path in seen:
                continue
            seen.add(raw_path)
            ordered_paths.append(raw_path)

        migration_path = str(entry.migration_file or "").strip()
        if migration_path and migration_path not in seen:
            ordered_paths.append(migration_path)

        return ordered_paths

    @staticmethod
    def _resolve_manifest_snapshot_path(
        raw_path: str,
        project_root: Path,
    ) -> tuple[Path, str]:
        """将 manifest 路径解析为磁盘路径和 ZIP 内路径 / Resolve manifest path to disk path and ZIP path."""
        candidate = Path(raw_path)
        resolved = candidate if candidate.is_absolute() else project_root / candidate
        if candidate.is_absolute():
            try:
                zip_path = str(resolved.relative_to(project_root))
            except ValueError:
                zip_path = resolved.name
        else:
            zip_path = candidate.as_posix()
        return resolved, zip_path.replace("\\", "/")

    @staticmethod
    def _table_exists(table_name: str) -> bool:
        """检查表是否已存在 / Check whether table exists."""
        if not table_name:
            return False
        from sqlalchemy import text
        from app.core.database import sync_session_factory

        with sync_session_factory() as session:
            result = session.execute(
                text("SELECT to_regclass(:tbl)"), {"tbl": table_name}
            )
            return result.scalar_one_or_none() is not None

    @staticmethod
    def list_available_presets() -> list[dict[str, Any]]:
        """List available presets / 列出全部可用预设."""
        return list_codegen_presets()

    @staticmethod
    def get_preset_detail(name: str) -> dict[str, Any] | None:
        """Get preset detail / 获取预设详情."""
        return load_codegen_preset(name)

    @classmethod
    def create_standalone(cls) -> "CodegenService":
        """
        创建无数据库依赖的轻量实例，仅用于 preview/validate。
        Create minimal instance for preview/validate without DB.
        """
        instance = cls.__new__(cls)
        instance.db = None  # type: ignore[assignment]  # 类型存根 / typing stub
        instance.repo = None  # type: ignore[assignment]  # 类型存根 / typing stub
        return instance

    async def get_by_resource(self, resource: str) -> CodegenConfig | None:
        """
        根据资源名获取配置 / Get config by resource name.

        Args:
            resource: 资源名

        Returns:
            配置实例或 None
        """
        return await self.repo.get_by_resource(resource)

    async def get_by_status(
        self, status: CodegenConfigStatusEnum | str
    ) -> list[CodegenConfig]:
        """
        根据状态获取配置列表 / Get configs by status.

        Args:
            status: 状态枚举或字符串

        Returns:
            配置列表
        """
        status_val = status.value if hasattr(status, "value") else status
        return await self.repo.get_by_status(status_val)

    async def _save_version(
        self, config: CodegenConfig, note: str | None = None
    ) -> None:
        """保存配置版本快照 / Save config version snapshot."""
        version_repo = CodegenConfigVersionRepository(self.repo.db)
        await version_repo.create(
            {
                "config_id": config.id,
                "config_json": dict(config.config_json) if config.config_json else {},
                "note": note,
            }
        )

    async def _before_create(self, data: dict[str, Any]) -> None:
        """创建前计算 config_hash / Compute config_hash before create."""
        await super()._before_create(data)
        self._sync_data_from_config_json(data)
        if config_json := data.get("config_json"):
            data["config_hash"] = hashlib.sha256(
                json.dumps(config_json, sort_keys=True).encode()
            ).hexdigest()[:16]

    async def _before_update(self, id: int, data: dict[str, Any]) -> None:
        """更新前计算 config_hash（当 config_json 变更时）/ Compute config_hash when config_json changes."""
        await super()._before_update(id, data)
        if "config_json" in data and isinstance(data.get("config_json"), dict):
            self._sync_data_from_config_json(data)
        else:
            current = await self.get_by_id(id)
            if current:
                synced_config = self._sync_config_json_from_top_level(
                    current.config_json, data
                )
                if synced_config is not None:
                    data["config_json"] = synced_config
                    self._sync_data_from_config_json(data)
        if config_json := data.get("config_json"):
            data["config_hash"] = hashlib.sha256(
                json.dumps(config_json, sort_keys=True).encode()
            ).hexdigest()[:16]

    async def _after_create(self, instance: CodegenConfig) -> None:
        await super()._after_create(instance)
        await self._save_version(instance, note=_("codegen.version_initial"))

    async def _after_update(self, instance: CodegenConfig) -> None:
        await super()._after_update(instance)
        await self._save_version(instance)

    async def list_versions(self, config_id: int, limit: int = 50) -> list[dict]:
        """获取配置的版本列表 / List config versions."""
        version_repo = CodegenConfigVersionRepository(self.repo.db)
        versions = await version_repo.list_by_config_id(config_id, limit=limit)
        return [
            {
                "id": v.id,
                "config_id": v.config_id,
                "created_at": v.created_at.isoformat() if v.created_at else None,
                "note": v.note,
            }
            for v in versions
        ]

    async def get_version_config(self, config_id: int, version_id: int) -> dict | None:
        """获取指定版本的 config_json / Get config_json of a version."""
        version_repo = CodegenConfigVersionRepository(self.repo.db)
        version = await version_repo.get_version(config_id, version_id)
        if not version:
            return None
        return version.config_json

    async def restore_version(
        self, config_id: int, version_id: int
    ) -> CodegenConfig | None:
        """恢复配置到指定版本；同步顶层 name/resource/module/display_name 与 config_json。"""
        config_json = await self.get_version_config(config_id, version_id)
        if config_json is None:
            return None
        update_data: dict[str, Any] = {
            "config_json": config_json,
            "status": CodegenConfigStatusEnum.DRAFT.value,
            "generated_files": None,
            "last_error": None,
            "last_generated_at": None,
        }
        if isinstance(config_json, dict):
            if "display_name" in config_json:
                update_data["display_name"] = config_json["display_name"]
            if "display_name_en" in config_json:
                update_data["display_name_en"] = config_json["display_name_en"]
            if "resource" in config_json:
                update_data["resource"] = config_json["resource"]
            if "module" in config_json:
                update_data["module"] = config_json["module"]
            if "name" in config_json:
                update_data["name"] = config_json["name"]
        return await self.update(config_id, update_data)

    async def duplicate(self, id: int) -> CodegenConfig:
        """
        复制配置 / Duplicate config.

        创建一份配置的副本，名称追加 " (副本)"，状态重置为 draft。
        同步 config_json 中的 resource/module/display_name 与顶层字段一致。
        Creates a copy with name suffixed " (副本)", status reset to draft.
        Syncs config_json.resource/module/display_name to match top-level fields.

        Args:
            id: 源配置 ID

        Returns:
            新创建的配置

        Raises:
            NotFoundException: 源配置不存在
        """
        source = await self.get_by_id(id)
        if not source:
            raise NotFoundException(message=_("codegen.config_not_found"))

        duplicate_suffix = _("codegen.duplicate_suffix")
        new_resource = await self._allocate_duplicate_resource(source.resource)
        new_name = await self._allocate_duplicate_name(source.name, duplicate_suffix)
        config_json = dict(source.config_json) if source.config_json else {}
        config_json["resource"] = new_resource
        config_json["module"] = source.module
        config_json["display_name"] = source.display_name
        config_json["display_name_en"] = source.display_name_en

        copy_data: dict[str, Any] = {
            "name": new_name,
            "resource": new_resource,
            "module": source.module,
            "display_name": source.display_name,
            "display_name_en": source.display_name_en,
            "status": CodegenConfigStatusEnum.DRAFT.value,
            "config_json": config_json,
            "generation_count": 0,
        }
        return await self.create(copy_data)

    async def _allocate_duplicate_resource(self, base_resource: str) -> str:
        """Allocate a unique resource name for duplicates / 为复制配置分配唯一 resource."""
        candidate = f"{base_resource}_copy"
        index = 2
        while await self.get_by_resource(candidate):
            candidate = f"{base_resource}_copy_{index}"
            index += 1
        return candidate

    async def _allocate_duplicate_name(self, base_name: str, suffix: str) -> str:
        """Allocate a unique config name for duplicates / 为复制配置分配唯一名称."""
        existing = await self.get_list(limit=2000)
        existing_names = {str(item.name or "").strip() for item in existing}
        candidate = f"{base_name}{suffix}"
        index = 2
        while candidate in existing_names:
            candidate = f"{base_name}{suffix} {index}"
            index += 1
        return candidate

    @staticmethod
    def build_delete_guard(
        config: CodegenConfig,
        *,
        manifest_present: bool,
    ) -> CodegenDeleteGuard:
        """Build delete guard info from config state / 根据配置状态构建删除保护信息."""
        status = str(config.status or "")
        if manifest_present:
            return CodegenDeleteGuard(
                allowed=False,
                reason_code="manifest_present",
                message=_("codegen.delete_guard.manifest_present"),
            )
        if status == CodegenConfigStatusEnum.ROLLED_BACK.value:
            return CodegenDeleteGuard(allowed=True)
        if status in {
            CodegenConfigStatusEnum.GENERATED.value,
            CodegenConfigStatusEnum.APPLIED.value,
        }:
            return CodegenDeleteGuard(
                allowed=False,
                reason_code="generated_state",
                message=_("codegen.delete_guard.generated_state"),
            )
        if (
            config.generated_files
            or config.last_generated_at
            or (config.generation_count or 0) > 0
        ):
            return CodegenDeleteGuard(
                allowed=False,
                reason_code="generation_history_present",
                message=_("codegen.delete_guard.generation_history_present"),
            )
        return CodegenDeleteGuard(allowed=True)

    @staticmethod
    def _has_manifest_entry(
        config: CodegenConfig,
        *,
        manifest_resources: set[str],
        manifest_config_ids: set[int],
    ) -> bool:
        """判断配置是否存在 manifest 条目 / Check whether config has a manifest entry."""
        if config.resource and config.resource in manifest_resources:
            return True
        return config.id in manifest_config_ids

    @classmethod
    def build_workbench_summary(
        cls,
        items: list[CodegenConfig],
        *,
        manifest_resources: set[str],
        manifest_config_ids: set[int],
        focus_limit: int = 6,
    ) -> dict[str, Any]:
        """构建 codegen 工作台摘要 / Build codegen workbench summary."""
        stats = {
            "draft": 0,
            "generated": 0,
            "applied": 0,
            "rollback": 0,
            "attention": 0,
            "total": len(items),
        }
        sections: dict[str, list[CodegenWorkbenchEntry]] = {
            "draft": [],
            "generated": [],
            "applied": [],
            "rollback": [],
            "attention": [],
        }

        for item in items:
            manifest_present = cls._has_manifest_entry(
                item,
                manifest_resources=manifest_resources,
                manifest_config_ids=manifest_config_ids,
            )
            guard = cls.build_delete_guard(item, manifest_present=manifest_present)
            entry = CodegenWorkbenchEntry(
                config=item,
                manifest_present=manifest_present,
                delete_guard=guard,
            )
            status = str(item.status or "")

            if status in {"draft", "generated", "applied"}:
                stats[status] += 1
                if len(sections[status]) < focus_limit:
                    sections[status].append(entry)

            if manifest_present:
                stats["rollback"] += 1
                if len(sections["rollback"]) < focus_limit:
                    sections["rollback"].append(entry)

            needs_attention = bool(item.last_error) or not guard.allowed
            if needs_attention:
                stats["attention"] += 1
                if len(sections["attention"]) < focus_limit:
                    sections["attention"].append(entry)

        return {
            "stats": stats,
            "sections": sections,
        }

    async def get_workbench_summary(
        self,
        *,
        project_root: Path | None = None,
        focus_limit: int = 6,
    ) -> dict[str, Any]:
        """获取工作台摘要 / Get workbench summary."""
        root = project_root or _PROJECT_ROOT
        items = await self.repo.list_workbench_rows()
        manifest = ManifestManager(root)
        manifest_resources, manifest_config_ids = manifest.manifest_index()
        return self.build_workbench_summary(
            items,
            manifest_resources=manifest_resources,
            manifest_config_ids=manifest_config_ids,
            focus_limit=focus_limit,
        )

    async def get_delete_guard(
        self,
        config_id: int,
        *,
        project_root: Path | None = None,
    ) -> CodegenDeleteGuard:
        """Get delete guard info for a config / 获取配置删除保护信息."""
        config = await self.get_by_id(config_id)
        if not config:
            raise NotFoundException(message=_("codegen.config_not_found"))
        root = project_root or _PROJECT_ROOT
        manifest = ManifestManager(root)
        manifest_present = (
            manifest.find_entry_for_config(config.resource, config.id) is not None
        )
        return self.build_delete_guard(config, manifest_present=manifest_present)

    async def assert_can_delete(
        self,
        config_id: int,
        *,
        project_root: Path | None = None,
    ) -> CodegenDeleteGuard:
        """Raise when deleting is unsafe / 删除不安全时抛出异常."""
        guard = await self.get_delete_guard(config_id, project_root=project_root)
        if guard.allowed:
            return guard
        raise ConflictException(
            message=guard.message or _("common.failed"),
            data={
                "reason_code": guard.reason_code,
            },
        )

    # ==================== Preview / Generate / Rollback / Validate ==================== / 预览生成回滚校验 / preview generate rollback validate

    def validate(
        self,
        config_json: dict[str, Any],
        *,
        mode: str = "generate",
    ) -> dict[str, Any]:
        """
        校验配置 JSON / Validate config JSON.

        Returns:
            {"valid": bool, "errors": [...], "warnings": [...]}
        """
        parser = ConfigParser()
        try:
            parsed = parser.parse(config_json)
            require_fields = mode != "draft"
            errors = parser.validate(parsed, require_fields=require_fields)
            return {
                "valid": len(errors) == 0,
                "errors": [
                    {
                        "code": e.code,
                        "message": e.message,
                        "path": e.path,
                        "field": e.field,
                    }
                    for e in errors
                ],
                "warnings": [],
                "mode": mode,
            }
        except Exception as e:
            # 脱敏：不向用户暴露堆栈 / Sanitize: do not expose stack trace
            err_str = str(e).lower()
            if any(
                x in err_str
                for x in ("traceback", "file ", ".py", "line ", "\\", "path")
            ):
                safe_msg = _("codegen.validation.parse_error")
            else:
                safe_msg = str(e)[:200]  # 短错误可保留，截断防泄露 / policy guard
            return {
                "valid": False,
                "errors": [
                    {
                        "code": "parse_error",
                        "message": safe_msg,
                        "path": "",
                        "field": "",
                    }
                ],
                "warnings": [],
                "mode": mode,
            }

    def preview(
        self,
        config_json: dict[str, Any],
        step: str | None = None,
        project_root: Path | None = None,
    ) -> dict[str, Any]:
        """
        预览生成结果 / Preview generation result.

        Args:
            config_json: 配置 JSON
            step: model | controller | frontend | None(全量)
            project_root: 项目根目录，用于检测已存在文件冲突

        Returns:
            {"success": True, "files": [...], "summary": {...}, "warnings": [], "conflicts": []}
            解析或生成失败时返回 {"success": False, "error": "..."}
        """
        try:
            parser = ConfigParser()
            parsed = parser.parse(config_json)
            gen = CodeGenerator()
            result = gen.generate(parsed, step=step)
            files = result.files
            render_errors = result.errors
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "files": [],
                "summary": {
                    "create_count": 0,
                    "modify_count": 0,
                    "backend_files": 0,
                    "frontend_files": 0,
                    "total_lines": 0,
                },
                "warnings": [],
                "conflicts": [],
            }

        root = project_root or _PROJECT_ROOT
        conflicts: list[dict] = []
        for f in files:
            if f.action == "create" and f.path:
                dest = root / f.path
                if dest.exists():
                    conflicts.append({"path": f.path, "reason": "file_exists"})

        file_list: list[dict] = []
        create_count = modify_count = 0
        backend_count = frontend_count = 0
        total_lines = 0

        for f in files:
            lang = (
                "python"
                if f.path.endswith(".py")
                else ("typescript" if f.path.endswith((".ts", ".vue")) else "yaml")
            )
            if f.path.startswith("backend/"):
                backend_count += 1
            elif f.path.startswith("frontend/"):
                frontend_count += 1
            line_count = f.content.count("\n") + (1 if f.content else 0)
            total_lines += line_count
            if f.action == "create":
                create_count += 1
            else:
                modify_count += 1

            original_content: str | None = None
            new_content: str | None = None
            dest = root / f.path if f.path else None
            if dest and dest.exists():
                try:
                    orig = dest.read_text(encoding="utf-8", errors="replace")
                except Exception:
                    orig = ""
                if f.action == "append" and f.appended_content:
                    original_content = orig
                    new_content = orig.rstrip() + "\n" + f.appended_content + "\n"
                elif f.action == "merge_json" and f.merged_keys:
                    original_content = orig
                    try:
                        data = json.loads(orig or "{}")
                        for k in f.merged_keys:
                            data.setdefault(k, {})
                        new_content = json.dumps(data, ensure_ascii=False, indent=2)
                    except Exception:
                        new_content = f.content
                else:
                    original_content = orig
                    new_content = f.content
            elif f.action == "append" and f.appended_content:
                original_content = ""
                new_content = f.appended_content + "\n"

            item: dict[str, Any] = {
                "path": f.path,
                "type": f.action,
                "language": lang,
                "content": new_content if new_content is not None else f.content,
                "line_count": line_count,
            }
            if original_content is not None and new_content is not None:
                item["original_content"] = original_content
                item["new_content"] = new_content
            file_list.append(item)

        return {
            "success": len(render_errors) == 0,
            "files": file_list,
            "summary": {
                "create_count": create_count,
                "modify_count": modify_count,
                "backend_files": backend_count,
                "frontend_files": frontend_count,
                "total_lines": total_lines,
            },
            "warnings": render_errors if render_errors else [],
            "conflicts": conflicts,
            "error": "; ".join(render_errors) if render_errors else None,
        }

    async def generate(
        self,
        config_id_or_json: int | dict[str, Any],
        force: bool = False,
        project_root: Path | None = None,
    ) -> GenerateOutput:
        """
        执行生成 / Execute generation.

        Args:
            config_id_or_json: 配置 ID 或 配置 JSON
            force: 是否覆盖已存在文件
            project_root: 项目根目录

        Returns:
            WriteResult
        """
        root = project_root or _PROJECT_ROOT
        if isinstance(config_id_or_json, int):
            config = await self.get_by_id(config_id_or_json)
            if not config:
                raise NotFoundException(message=_("codegen.config_not_found"))
            config_json = config.config_json or {}
            config_id = config.id
            config = config
        else:
            config_json = config_id_or_json
            config_id = None
            config = None

        parsed = ConfigParser().parse(config_json)
        resource = parsed.resource
        module = parsed.module

        gen = CodeGenerator()
        parsed = ConfigParser().parse(config_json)
        gen_result = gen.generate(parsed, step=None)
        files = gen_result.files
        table_name = CodeGenerator._pluralize(parsed.resource.replace("-", "_"))
        if not files:
            return GenerateOutput(
                result=WriteResult(
                    success=False, errors=gen_result.errors or ["No files to generate"]
                ),
                config_id=config_id,
                resource=parsed.resource,
                module=parsed.module,
                table_name=table_name,
            )

        # 模板渲染有错误时禁止落盘，杜绝无 manifest 半成品
        if gen_result.errors:
            return GenerateOutput(
                result=WriteResult(
                    success=False,
                    errors=gen_result.errors,
                    conflicts=[],  # 可预计算 conflicts 但不写盘
                ),
                config_id=config_id,
                resource=parsed.resource,
                module=parsed.module,
                table_name=table_name,
            )

        writer = FileWriter(root)
        result = writer.write_atomic(files, root, force=force)

        if result.success and resource and module:
            manifest = ManifestManager(root)
            config_hash_val = hashlib.sha256(
                json.dumps(config_json, sort_keys=True).encode()
            ).hexdigest()
            manifest.add_entry(
                resource=resource,
                module=module,
                config_id=config_id,
                files=files,
                config_hash=config_hash_val,
            )

        if result.success:
            format_code(root, files)

        # CLI generate from YAML: auto-save to DB so config appears in Web UI / CLI 生成并落库 / CLI generate persists to DB
        if (
            result.success
            and config_id is None
            and resource
            and module
            and self.db is not None
        ):
            existing = await self.get_by_resource(resource)
            if existing:
                update_data: dict[str, Any] = {"config_json": config_json}
                if isinstance(config_json, dict):
                    update_data.update(self._derive_top_level_fields(config_json))
                await self.update(existing.id, update_data)
                config_id = existing.id
                config = existing
            else:
                created = await self.create(
                    {
                        "name": parsed.display_name or resource,
                        "resource": resource,
                        "module": module,
                        "display_name": parsed.display_name or resource,
                        "display_name_en": parsed.display_name_en
                        or resource.replace("_", " ").title(),
                        "config_json": config_json,
                        "status": CodegenConfigStatusEnum.DRAFT.value,
                    }
                )
                config_id = created.id
                config = created

        if config_id is not None and resource and module:
            manifest = ManifestManager(root)
            manifest.update_config_id(resource, config_id)

        if config_id is not None:
            update_data: dict[str, Any] = {
                "last_generated_at": datetime.now(timezone.utc),
                "generation_count": (config.generation_count or 0) + 1,
            }
            if result.success:
                if isinstance(config_json, dict):
                    update_data.update(self._derive_top_level_fields(config_json))
                update_data["status"] = CodegenConfigStatusEnum.GENERATED.value
                update_data["last_error"] = None
                update_data["config_hash"] = hashlib.sha256(
                    json.dumps(config_json, sort_keys=True).encode()
                ).hexdigest()[:16]
                update_data["generated_files"] = self._build_generated_files_payload(
                    result,
                    resource=resource,
                    module=module,
                    table_name=table_name,
                )
            else:
                update_data["last_error"] = (
                    "; ".join(result.errors) if result.errors else None
                )
            await self.update(config_id, update_data)

        return GenerateOutput(
            result=result,
            config_id=config_id,
            resource=resource,
            module=module,
            table_name=table_name,
        )

    @staticmethod
    def run_auto_migrate(resource: str, project_root: Path) -> dict[str, Any]:
        """
        Full auto-migrate cycle: purge orphaned stamps → pre-upgrade → autogenerate → inject metadata → post-upgrade.
        完整自动迁移周期：清理孤立 stamp → 预升级 → 自动生成 → 注入元数据 → 后升级。
        """
        import re as _re
        import subprocess
        import sys

        backend_dir = project_root / "backend"
        if not backend_dir.exists():
            return {"success": False, "error": "backend dir not found"}

        from app.core.database import purge_orphaned_alembic_stamps

        purge_orphaned_alembic_stamps(backend_dir)

        _up_pre = subprocess.run(
            [sys.executable, "-m", "alembic", "upgrade", "head"],
            cwd=str(backend_dir),
            capture_output=True,
            text=True,
        )
        if _up_pre.returncode != 0:
            return {
                "success": False,
                "error": f"pre-upgrade failed: {_up_pre.stderr}",
                "phase": "pre_upgrade",
            }

        _rev = subprocess.run(
            [
                sys.executable,
                "-m",
                "alembic",
                "revision",
                "--autogenerate",
                "-m",
                f"codegen_{resource}",
            ],
            cwd=str(backend_dir),
            capture_output=True,
            text=True,
        )
        if _rev.returncode != 0:
            return {
                "success": False,
                "error": f"autogenerate failed: {_rev.stderr}",
                "phase": "autogenerate",
            }

        migration_path = None
        _out = (_rev.stdout or "") + (_rev.stderr or "")
        _m = _re.search(r"Generating\s+(.+\.py)", _out)
        if _m:
            migration_path = _m.group(1).strip()

        if migration_path:
            from app.codegen.migration_helper import inject_migration_metadata

            _mp = Path(migration_path)
            if not _mp.is_absolute():
                _mp = backend_dir / _mp
            if _mp.exists():
                content = _mp.read_text(encoding="utf-8", errors="replace")
                patched = inject_migration_metadata(content, resource)
                if patched != content:
                    _mp.write_text(patched, encoding="utf-8")
                # 校验迁移内容：允许 add/alter/drop 等任意 op.* 调用；空迁移仅在表已存在时视为 no-op
                upgrade_body = ""
                _upgrade_match = _re.search(
                    r"def upgrade\([^)]*\)\s*(?:->\s*[^:]+)?\s*:\s*(.*?)(?:\n\s*def downgrade\(|\Z)",
                    patched,
                    _re.DOTALL,
                )
                if _upgrade_match:
                    upgrade_body = _upgrade_match.group(1)
                has_ops = bool(_re.search(r"\bop\.[a-zA-Z_]+\(", upgrade_body))
                if not has_ops:
                    expected_table = CodeGenerator._pluralize(
                        resource.replace("-", "_")
                    )
                    if CodegenService._table_exists(expected_table):
                        _mp.unlink(missing_ok=True)
                        return {
                            "success": True,
                            "message": f"No schema changes detected for {resource}",
                            "phase": "noop",
                            "migration_path": None,
                        }
                    return {
                        "success": False,
                        "error": (
                            f"Migration file has no alembic operations; "
                            f"expected schema changes for table {expected_table!r}."
                        ),
                        "phase": "validation",
                        "migration_path": migration_path,
                    }

        _up_post = subprocess.run(
            [sys.executable, "-m", "alembic", "upgrade", "head"],
            cwd=str(backend_dir),
            capture_output=True,
            text=True,
        )
        if _up_post.returncode != 0:
            return {
                "success": False,
                "error": f"post-upgrade failed: {_up_post.stderr}",
                "phase": "post_upgrade",
                "migration_path": migration_path,
            }

        rel_path = migration_path
        if migration_path:
            try:
                rel_path = str(Path(migration_path).relative_to(project_root))
            except ValueError:
                rel_path = migration_path

        return {
            "success": True,
            "message": f"Migration generated and applied for {resource}",
            "migration_path": rel_path,
        }

    def rollback(
        self,
        config_id: int,
        force: bool = False,
        dry_run: bool = False,
        project_root: Path | None = None,
    ) -> RollbackResult:
        """
        回滚生成的代码 / Rollback generated code.

        Args:
            config_id: 配置 ID
            force: 强制回滚
            dry_run: 仅预览
            project_root: 项目根目录

        Returns:
            RollbackResult
        """
        root = project_root or _PROJECT_ROOT
        rb = CodegenRollback(root)
        return rb.rollback(config_id=config_id, force=force, dry_run=dry_run)

    async def rollback_async(
        self,
        config_id: int,
        force: bool = False,
        dry_run: bool = False,
        project_root: Path | None = None,
    ) -> RollbackResult:
        """
        回滚生成的代码（支持 config_id 查找失败时按 resource 回退）/ Rollback with resource fallback.
        """
        root = project_root or _PROJECT_ROOT
        rb = CodegenRollback(root)
        result = rb.rollback(config_id=config_id, force=force, dry_run=dry_run)
        if not result.success and result.errors and self.db is not None:
            config = await self.get_by_id(config_id)
            if config:
                result = rb.rollback(
                    resource=config.resource, force=force, dry_run=dry_run
                )
        return result

    async def download(self, config_id: int, project_root: Path | None = None) -> bytes:
        """
        下载生成的代码 ZIP / Download generated code as ZIP.

        Args:
            config_id: 配置 ID
            project_root: 项目根目录

        Returns:
            ZIP 二进制内容
        """
        config = await self.get_by_id(config_id)
        if not config:
            raise NotFoundException(message=_("codegen.config_not_found"))
        root = project_root or _PROJECT_ROOT
        manifest = ManifestManager(root)
        entry = manifest.find_entry_for_config(config.resource, config.id)
        if not entry:
            raise ConflictException(
                message=_("codegen.download.no_manifest_entry"),
                data={
                    "config_id": config.id,
                    "resource": config.resource,
                },
            )

        snapshot_paths = self._iter_manifest_snapshot_paths(entry)
        if not snapshot_paths:
            raise ConflictException(
                message=_("codegen.download.no_tracked_files"),
                data={
                    "config_id": config.id,
                    "resource": entry.resource,
                },
            )

        zip_files: list[GeneratedFile] = []
        missing_paths: list[str] = []
        for raw_path in snapshot_paths:
            resolved, zip_path = self._resolve_manifest_snapshot_path(raw_path, root)
            if not resolved.exists() or not resolved.is_file():
                missing_paths.append(raw_path.replace("\\", "/"))
                continue
            zip_files.append(
                GeneratedFile(
                    path=zip_path,
                    content=resolved.read_text(encoding="utf-8", errors="replace"),
                    action="create",
                )
            )

        if missing_paths:
            raise ConflictException(
                message=_(
                    "codegen.download.missing_files",
                    paths=", ".join(missing_paths),
                ),
                data={
                    "config_id": config.id,
                    "resource": entry.resource,
                    "missing_files": missing_paths,
                },
            )

        return export_zip(zip_files)

    def preview_zip(
        self, config_json: dict[str, Any], step: str | None = None
    ) -> bytes:
        """
        预览 ZIP（不写入项目，仅用于下载审查）/ Preview ZIP without writing to project.

        Args:
            config_json: 配置 JSON
            step: model | controller | frontend | None(全量)

        Returns:
            ZIP 二进制内容
        """
        parser = ConfigParser()
        parsed = parser.parse(config_json)
        gen = CodeGenerator()
        gen_result = gen.generate(parsed, step=step)
        return export_zip(gen_result.files)

    def get_table_names(self) -> list[str]:
        """获取所有表名（白名单校验用）/ Get all table names for whitelist validation."""
        intro = DbIntrospector()
        return intro.get_table_names()

    def introspect_tables(self) -> list[dict[str, Any]]:
        """列出数据库所有表 / List all DB tables."""
        intro = DbIntrospector()
        names = intro.get_table_names()
        result = []
        for name in names:
            result.append(
                {
                    "name": name,
                    "comment": None,
                    "row_count": intro.get_row_count_estimate(name),
                    "has_model": intro.has_model(name),
                }
            )
        return result

    def introspect_columns(self, table_name: str) -> list[dict[str, Any]]:
        """获取表的列定义 / Get table column definitions."""
        intro = DbIntrospector()
        cols = intro.get_columns(table_name)
        return [
            {
                "name": c.name,
                "type": c.type,
                "nullable": c.nullable,
                "default": c.default,
                "primary_key": c.primary_key,
                "unique": c.unique,
                "comment": c.comment,
                "foreign_keys": c.foreign_keys,
                "suggested_config": c.suggested_config,
            }
            for c in cols
        ]

    def introspect_rows(
        self,
        table_name: str,
        value_field: str = "id",
        display_field: str = "name",
        limit: int = 200,
        search: str | None = None,
    ) -> dict[str, Any]:
        """
        获取表行数据（供关联下拉预览）/ Get table rows for relation select preview.

        Returns:
            {"items": [{"value": ..., "label": ...}, ...], "total": int}
        """
        intro = DbIntrospector()
        items = intro.get_table_rows(
            table_name=table_name,
            value_field=value_field,
            display_field=display_field,
            limit=limit,
            search=search,
        )
        return {"items": items, "total": len(items)}

    def import_from_table(self, table_name: str) -> dict[str, Any]:
        """
        从 DB 表导入为配置 JSON / Import from DB table to config JSON.

        Returns:
            包含 module, resource, fields 等的配置片段
        """
        cols = self.introspect_columns(table_name)
        # 表名转 resource: categories -> category, boxes -> box, users -> user
        # 复数→单数: 先查 ies→y，再查 ses/xes/ches/shes→去 es，最后查 s→去 s
        resource = table_name
        if len(table_name) > 1:
            if table_name.endswith("ies") and len(table_name) > 3:
                resource = table_name[:-3] + "y"
            elif table_name.endswith(("ses", "xes", "ches", "shes")):
                resource = table_name[:-2]
            elif table_name.endswith("s") and not table_name.endswith("ss"):
                resource = table_name[:-1]
        fields = []
        for c in cols:
            fields.append(
                {
                    "name": c["name"],
                    **c.get("suggested_config", {}),
                }
            )
        return {
            "resource": resource,
            "module": "system",
            "fields": fields,
        }


__all__ = ["CodegenService"]
