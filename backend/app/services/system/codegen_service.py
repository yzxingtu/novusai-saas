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
from app.codegen.file_writer import FileWriter, WriteResult
from app.codegen.generator import CodeGenerator, GeneratedFile
from app.codegen.manifest import ManifestManager
from app.codegen.rollback import CodegenRollback, RollbackResult
from app.codegen.type_registry import type_registry
from app.codegen.zip_exporter import export_zip, format_code
from app.core.base_service import GlobalService
from app.core.i18n import _
from app.enums.codegen import CodegenConfigStatusEnum
from app.exceptions import NotFoundException
from app.models.system.codegen_config import CodegenConfig
from app.models.system.codegen_config_version import CodegenConfigVersion
from app.repositories.system.codegen_config_repository import (
    CodegenConfigRepository,
)
from app.repositories.system.codegen_config_version_repository import (
    CodegenConfigVersionRepository,
)

from app.codegen.constants import CODEGEN_PROJECT_ROOT as _PROJECT_ROOT


class CodegenService(GlobalService[CodegenConfig, CodegenConfigRepository]):
    """
    CRUD 代码生成服务 / Codegen service.

    平台级服务，无企业隔离。基础 CRUD，后续阶段会扩展 preview/generate 等
    Platform-level service, no tenant isolation.
    """

    model = CodegenConfig
    repository_class = CodegenConfigRepository

    @classmethod
    def create_standalone(cls) -> "CodegenService":
        """
        创建无数据库依赖的轻量实例，仅用于 preview/validate。
        Create minimal instance for preview/validate without DB.
        """
        instance = cls.__new__(cls)
        instance.db = None  # type: ignore[assignment]
        instance.repo = None  # type: ignore[assignment]
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

    async def _save_version(self, config: CodegenConfig, note: str | None = None) -> None:
        """保存配置版本快照 / Save config version snapshot."""
        version_repo = CodegenConfigVersionRepository(self.repo.db)
        await version_repo.create({
            "config_id": config.id,
            "config_json": dict(config.config_json) if config.config_json else {},
            "note": note,
        })

    async def _before_create(self, data: dict[str, Any]) -> None:
        """创建前计算 config_hash / Compute config_hash before create."""
        await super()._before_create(data)
        if config_json := data.get("config_json"):
            data["config_hash"] = hashlib.sha256(
                json.dumps(config_json, sort_keys=True).encode()
            ).hexdigest()[:16]

    async def _before_update(self, id: int, data: dict[str, Any]) -> None:
        """更新前计算 config_hash（当 config_json 变更时）/ Compute config_hash when config_json changes."""
        await super()._before_update(id, data)
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

    async def restore_version(self, config_id: int, version_id: int) -> CodegenConfig | None:
        """恢复配置到指定版本（经 service 钩子更新 hash 并创建版本快照）/ Restore config to version."""
        config_json = await self.get_version_config(config_id, version_id)
        if config_json is None:
            return None
        return await self.update(config_id, {"config_json": config_json})

    async def duplicate(self, id: int) -> CodegenConfig:
        """
        复制配置 / Duplicate config.

        创建一份配置的副本，名称追加 " (副本)"，状态重置为 draft
        Creates a copy with name suffixed " (副本)", status reset to draft.

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

        copy_data: dict[str, Any] = {
            "name": f"{source.name}{_('codegen.duplicate_suffix')}",
            "resource": f"{source.resource}_copy",
            "module": source.module,
            "display_name": source.display_name,
            "display_name_en": source.display_name_en,
            "status": CodegenConfigStatusEnum.DRAFT.value,
            "config_json": dict(source.config_json) if source.config_json else {},
            "generation_count": 0,
        }
        return await self.create(copy_data)

    # ==================== Preview / Generate / Rollback / Validate ====================

    def validate(self, config_json: dict[str, Any]) -> dict[str, Any]:
        """
        校验配置 JSON / Validate config JSON.

        Returns:
            {"valid": bool, "errors": [...], "warnings": [...]}
        """
        parser = ConfigParser()
        try:
            parsed = parser.parse(config_json)
            errors = parser.validate(parsed)
            return {
                "valid": len(errors) == 0,
                "errors": [{"code": e.code, "message": e.message, "path": e.path, "field": e.field} for e in errors],
                "warnings": [],
            }
        except Exception as e:
            # 脱敏：不向用户暴露堆栈 / Sanitize: do not expose stack trace
            err_str = str(e).lower()
            if any(x in err_str for x in ("traceback", "file ", ".py", "line ", "\\", "path")):
                safe_msg = _("codegen.validation.parse_error")
            else:
                safe_msg = str(e)[:200]  # 短错误可保留，截断防泄露
            return {"valid": False, "errors": [{"code": "parse_error", "message": safe_msg, "path": "", "field": ""}], "warnings": []}

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
                "summary": {"create_count": 0, "modify_count": 0, "backend_files": 0, "frontend_files": 0, "total_lines": 0},
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
            lang = "python" if f.path.endswith(".py") else ("typescript" if f.path.endswith((".ts", ".vue")) else "yaml")
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
    ) -> WriteResult:
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
            resource = config.resource
            module = config.module
        else:
            config_json = config_id_or_json
            config_id = None
            parsed = ConfigParser().parse(config_json)
            resource = parsed.resource
            module = parsed.module

        gen = CodeGenerator()
        gen_result = gen.generate(ConfigParser().parse(config_json), step=None)
        files = gen_result.files
        if not files:
            return WriteResult(success=False, errors=gen_result.errors or ["No files to generate"])

        writer = FileWriter(root)
        result = writer.write_atomic(files, root, force=force)

        # 合并模板渲染异常到写入结果 / Merge template render errors into write result
        if gen_result.errors:
            result = WriteResult(
                success=False,
                errors=(result.errors or []) + gen_result.errors,
            )

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

        if config_id is not None:
            update_data: dict[str, Any] = {
                "last_generated_at": datetime.now(timezone.utc),
                "generation_count": (config.generation_count or 0) + 1,
            }
            if result.success:
                update_data["status"] = CodegenConfigStatusEnum.GENERATED.value
                update_data["last_error"] = None
                update_data["config_hash"] = hashlib.sha256(
                    json.dumps(config_json, sort_keys=True).encode()
                ).hexdigest()[:16]
            else:
                update_data["last_error"] = "; ".join(result.errors) if result.errors else None
            await self.update(config_id, update_data)

        return result

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
        config_json = config.config_json or {}
        parsed = ConfigParser().parse(config_json)
        gen = CodeGenerator()
        gen_result = gen.generate(parsed, step=None)
        return export_zip(gen_result.files)

    def preview_zip(self, config_json: dict[str, Any], step: str | None = None) -> bytes:
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
            result.append({
                "name": name,
                "comment": None,
                "row_count": intro.get_row_count_estimate(name),
                "has_model": intro.has_model(name),
            })
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
            fields.append({
                "name": c["name"],
                **c.get("suggested_config", {}),
            })
        return {
            "resource": resource,
            "module": "system",
            "fields": fields,
        }


__all__ = ["CodegenService"]
