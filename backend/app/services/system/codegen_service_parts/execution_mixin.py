"""Execution concerns for CodegenService. / CodegenService 生成执行职责。"""

from __future__ import annotations

import hashlib
import json
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from filelock import FileLock, Timeout

from app.codegen.config_parser import ConfigParser
from app.codegen.constants import CODEGEN_PROJECT_ROOT as _PROJECT_ROOT
from app.codegen.file_writer import FileWriter, WriteResult
from app.codegen.generator import CodeGenerator, GeneratedFile
from app.codegen.manifest import ManifestEntry, ManifestManager
from app.codegen.migration_helper import run_rollback_migration_cleanup
from app.codegen.rollback import CodegenRollback, RollbackResult
from app.codegen.zip_exporter import export_zip, format_code
from app.core.i18n import _
from app.enums.codegen import CodegenConfigStatusEnum
from app.exceptions import ConflictException, NotFoundException

from .types import GenerateOutput

_LOCK_DIR_NAME = ".codegen_locks"
_GLOBAL_LOCK_FILE = "_codegen_global.lock"


@contextmanager
def _acquire_codegen_global_lock(
    project_root: Path,
    *,
    timeout: int = 60,
):
    """Guard write/rollback orchestration with one project-wide lock."""
    lock_dir = project_root / _LOCK_DIR_NAME
    lock_dir.mkdir(parents=True, exist_ok=True)
    lock = FileLock(lock_dir / _GLOBAL_LOCK_FILE, timeout=timeout)
    try:
        lock.acquire(timeout=timeout)
    except Timeout as exc:
        raise ConflictException(message=_("codegen.concurrent_operation")) from exc

    try:
        yield
    finally:
        if lock.is_locked:
            lock.release()


class CodegenExecutionMixin:
    """Execution mixin / 生成执行混入。"""

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
    def _lint_migration_file(backend_dir: Path, migration_path: Path) -> list:
        """Run migration lint on a single file via dynamic import.

        Returns a list of warning objects (empty = clean).
        """
        import importlib.util

        lint_script = backend_dir / "scripts" / "lint_migrations.py"
        if not lint_script.exists():
            return []
        spec = importlib.util.spec_from_file_location(
            "lint_migrations", str(lint_script)
        )
        if spec is None or spec.loader is None:
            return []
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod.lint_file(migration_path)

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
            err_str = str(e).lower()
            if any(
                x in err_str
                for x in ("traceback", "file ", ".py", "line ", "\\", "path")
            ):
                safe_msg = _("codegen.validation.parse_error")
            else:
                safe_msg = str(e)[:200]
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
        """
        try:
            parser = ConfigParser()
            parsed = parser.parse(config_json)
            facade = self._make_generator().as_facade()
            if step == "model":
                result = facade.generate_model_bundle(parsed)
            elif step == "controller":
                result = facade.generate_controller_bundle(parsed)
            elif step == "frontend":
                result = facade.generate_frontend_bundle(parsed)
            elif step == "test":
                result = facade.generate_test_bundle(parsed)
            else:
                result = facade.generate_all(parsed)
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

    async def generate_with_auto_migrate(
        self,
        config_id_or_json: int | dict[str, Any],
        *,
        force: bool = False,
        auto_migrate: bool = False,
        project_root: Path | None = None,
    ) -> dict[str, Any]:
        """Execute generate flow with lock + optional auto-migrate orchestration."""
        root = project_root or _PROJECT_ROOT
        with _acquire_codegen_global_lock(root):
            output = await self.generate(
                config_id_or_json,
                force=force,
                project_root=root,
            )
            result = output.result
            data: dict[str, Any] = {
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

            if auto_migrate and result.success and output.resource:
                await self._apply_auto_migrate_result(
                    output=output,
                    response_data=data,
                    project_root=root,
                )

            return data

    async def _apply_auto_migrate_result(
        self,
        *,
        output: GenerateOutput,
        response_data: dict[str, Any],
        project_root: Path,
    ) -> None:
        """Sync auto-migrate side effects back into manifest/config state."""
        resource = output.resource
        if not resource:
            return

        migrate_result = self.run_auto_migrate(resource, project_root)
        response_data["migration"] = migrate_result
        if migrate_result.get("success"):
            migration_path = migrate_result.get("migration_path")
            if migration_path:
                ManifestManager(project_root).update_migration_file(
                    resource,
                    migration_path,
                )
            if output.config_id is not None:
                await self.update(
                    output.config_id,
                    {
                        "status": CodegenConfigStatusEnum.APPLIED.value,
                        "last_error": None,
                    },
                )
            return

        err_msg = (
            f"auto_migrate failed at {migrate_result.get('phase', 'unknown')}: "
            f"{migrate_result.get('error', 'unknown error')}"
        )
        response_data["success"] = False
        response_data["errors"] = list(response_data.get("errors") or [])
        response_data["errors"].append(err_msg)
        if output.config_id is not None:
            await self.update(
                output.config_id,
                {
                    "status": CodegenConfigStatusEnum.GENERATED.value,
                    "last_error": err_msg,
                },
            )

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
        """
        root = project_root or _PROJECT_ROOT
        if isinstance(config_id_or_json, int):
            config = await self.get_by_id(config_id_or_json)
            if not config:
                raise NotFoundException(message=_("codegen.config_not_found"))
            config_json = config.config_json or {}
            config_id = config.id
        else:
            config_json = config_id_or_json
            config_id = None
            config = None

        parsed = ConfigParser().parse(config_json)
        resource = parsed.resource
        module = parsed.module

        generator = self._make_generator()
        gen_result = generator.generate(parsed)
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

        if gen_result.errors:
            return GenerateOutput(
                result=WriteResult(
                    success=False,
                    errors=gen_result.errors,
                    conflicts=[],
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
                "generation_count": (config.generation_count or 0) + 1,  # type: ignore[union-attr]
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

    @classmethod
    def run_auto_migrate(
        cls,
        resource: str,
        project_root: Path,
    ) -> dict[str, Any]:
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
                    if cls._table_exists(expected_table):
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

                lint_warnings = cls._lint_migration_file(
                    backend_dir,
                    _mp,
                )
                if lint_warnings:
                    warning_text = "\n".join(str(w) for w in lint_warnings)
                    return {
                        "success": False,
                        "error": f"Migration lint failed:\n{warning_text}",
                        "phase": "lint",
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

    async def rollback_config_with_cleanup(
        self,
        config_id: int,
        *,
        resource: str,
        migration_file: str | None = None,
        force: bool = False,
        dry_run: bool = False,
        project_root: Path | None = None,
    ) -> dict[str, Any]:
        """Rollback a generated config with lock + manifest cleanup orchestration."""
        root = project_root or _PROJECT_ROOT
        with _acquire_codegen_global_lock(root):
            result = await self.rollback_async(
                config_id,
                force=force,
                dry_run=dry_run,
                project_root=root,
            )
            return await self._finalize_rollback_cleanup(
                result=result,
                resource=resource,
                migration_file=migration_file,
                config_id=config_id,
                force=force,
                dry_run=dry_run,
                project_root=root,
            )

    async def rollback_resource_with_cleanup(
        self,
        resource: str,
        *,
        migration_file: str | None = None,
        force: bool = False,
        dry_run: bool = False,
        project_root: Path | None = None,
    ) -> dict[str, Any]:
        """Rollback a generated resource with lock + manifest cleanup orchestration."""
        root = project_root or _PROJECT_ROOT
        with _acquire_codegen_global_lock(root):
            rb = CodegenRollback(root)
            result = rb.rollback(resource=resource, force=force, dry_run=dry_run)
            return await self._finalize_rollback_cleanup(
                result=result,
                resource=resource,
                migration_file=migration_file,
                config_id=None,
                force=force,
                dry_run=dry_run,
                project_root=root,
            )

    async def _finalize_rollback_cleanup(
        self,
        *,
        result: RollbackResult,
        resource: str,
        migration_file: str | None,
        config_id: int | None,
        force: bool,
        dry_run: bool,
        project_root: Path,
    ) -> dict[str, Any]:
        """Apply manifest cleanup + config status sync after file rollback."""
        manifest = ManifestManager(project_root)
        migration_cleaned = False

        if not dry_run and result.success:
            migration_cleaned = run_rollback_migration_cleanup(
                resource=resource,
                migration_file=migration_file,
                project_root=project_root,
                force_drop=force,
            )

        config = None
        if not dry_run:
            if config_id is not None:
                config = await self.get_by_id(config_id)
            else:
                config = await self.get_by_resource(resource)

        overall_success = result.success
        errors = list(result.errors)
        if not dry_run and result.success:
            if migration_cleaned:
                manifest.remove_entry(resource)
                if config:
                    await self.update(
                        config.id,
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
                    await self.update(config.id, {"last_error": rollback_err})

        return {
            "success": overall_success,
            "files_deleted": result.files_deleted,
            "files_modified": result.files_modified,
            "files_skipped": result.files_skipped,
            "manual_steps": result.manual_steps,
            "errors": errors,
            "migration_cleaned": migration_cleaned,
        }

    async def download(self, config_id: int, project_root: Path | None = None) -> bytes:
        """
        下载生成的代码 ZIP / Download generated code as ZIP.
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
        """
        parser = ConfigParser()
        parsed = parser.parse(config_json)
        facade = self._make_generator().as_facade()
        if step == "model":
            gen_result = facade.generate_model_bundle(parsed)
        elif step == "controller":
            gen_result = facade.generate_controller_bundle(parsed)
        elif step == "frontend":
            gen_result = facade.generate_frontend_bundle(parsed)
        elif step == "test":
            gen_result = facade.generate_test_bundle(parsed)
        else:
            gen_result = facade.generate_all(parsed)
        return export_zip(gen_result.files)
