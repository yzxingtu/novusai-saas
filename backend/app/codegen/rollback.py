"""
回滚引擎 / Rollback Engine

按 manifest 逆向操作：create->删除, append->移除片段, merge_json->移除 key,
register_route->移除路由注册, register_model->移除模型注册
Reverse operations per manifest.
"""

from __future__ import annotations

import hashlib
import json
import re
import shutil
import time
from dataclasses import dataclass, field
from pathlib import Path

from app.codegen.manifest import ManifestManager
from app.core.i18n import _


@dataclass
class RollbackResult:
    """回滚结果 / Rollback result."""

    success: bool
    files_deleted: list[str] = field(default_factory=list)
    files_modified: list[str] = field(default_factory=list)
    files_skipped: list[dict] = field(default_factory=list)
    manual_steps: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


def _file_hash(path: Path) -> str | None:
    """计算文件 hash / Compute file hash."""
    if not path.exists() or not path.is_file():
        return None
    return hashlib.sha256(path.read_bytes()).hexdigest()


class CodegenRollback:
    """
    回滚引擎 / Rollback engine.

    按 manifest 逆向操作，支持 hash 校验
    """

    def __init__(self, project_root: Path | None = None):
        self.project_root = Path(project_root) if project_root else Path.cwd()
        self.manifest = ManifestManager(self.project_root)

    def rollback(
        self,
        resource: str | None = None,
        config_id: int | None = None,
        force: bool = False,
        dry_run: bool = False,
    ) -> RollbackResult:
        """
        回滚生成代码 / Rollback generated code.

        Args:
            resource: 资源名，与 config_id 二选一
            config_id: 配置 ID，用于查找 manifest 中对应条目
            force: 强制删除，即使文件已修改
            dry_run: 仅列出将执行的操作，不实际执行

        Returns:
            RollbackResult
        """
        result = RollbackResult(success=False)

        entry = None
        if resource:
            entry = self.manifest.get_entry(resource)
        elif config_id is not None:
            for e in self.manifest.list_entries():
                if e.config_id == config_id:
                    entry = e
                    break

        if not entry:
            result.errors.append(_("codegen.rollback.no_manifest_entry"))
            return result

        ts = int(time.time() * 1000)
        backup_dir = self.project_root / ".novus_codegen_backup" / f"rollback_{ts}"
        if not dry_run:
            backup_dir.mkdir(parents=True, exist_ok=True)

        for f in entry.files:
            path_str = f.get("path", "")
            action = f.get("action", "create")
            dest = self.project_root / path_str

            if action == "create":
                if dry_run:
                    result.files_deleted.append(path_str)
                    continue
                if dest.exists():
                    dest.unlink()
                    result.files_deleted.append(path_str)
                else:
                    result.files_skipped.append({"path": path_str, "reason": "file_not_found"})

            elif action == "append":
                appended = f.get("appended_content", "")
                if not appended:
                    continue
                if not dest.exists():
                    result.files_skipped.append({"path": path_str, "reason": "file_not_found"})
                    continue
                content = dest.read_text(encoding="utf-8", errors="replace")
                appended_stripped = appended.strip()
                if appended_stripped not in content:
                    result.files_skipped.append({"path": path_str, "reason": "appended_content_modified"})
                    continue
                if dry_run:
                    result.files_modified.append(path_str)
                    continue
                backup_path = backup_dir / path_str
                backup_path.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(dest, backup_path)
                # 使用与检查相同的字符串进行替换 / Use same string for replace as for check
                new_content = content.replace(appended_stripped, "", 1).replace("\n\n\n", "\n\n")
                dest.write_text(new_content.strip() + "\n", encoding="utf-8")
                result.files_modified.append(path_str)

            elif action == "merge_json":
                merged_keys = f.get("merged_keys", [])
                if not merged_keys:
                    continue
                if not dest.exists():
                    result.files_skipped.append({"path": path_str, "reason": "file_not_found"})
                    continue
                if dry_run:
                    result.files_modified.append(path_str)
                    continue
                try:
                    data = json.loads(dest.read_text(encoding="utf-8", errors="replace"))
                    for k in merged_keys:
                        if "." in k:
                            parts = k.split(".")
                            target = data
                            for p in parts[:-1]:
                                target = target.get(p, {})
                            if isinstance(target, dict):
                                target.pop(parts[-1], None)
                        else:
                            data.pop(k, None)
                    backup_path = backup_dir / path_str
                    backup_path.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(dest, backup_path)
                    dest.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
                    result.files_modified.append(path_str)
                except (json.JSONDecodeError, OSError) as e:
                    result.files_skipped.append({"path": path_str, "reason": str(e)})

            elif action == "register_route":
                route_meta = f.get("route_meta") or {}
                scope = route_meta.get("scope", "")
                resource = route_meta.get("resource", "")
                if not scope or not resource:
                    continue
                if not dest.exists():
                    result.files_skipped.append({"path": path_str, "reason": "file_not_found"})
                    continue
                pascal = "".join(
                    w.capitalize() for w in str(resource).replace("-", "_").split("_")
                )
                prefix = "Admin" if scope == "admin" else "Tenant"
                controller_name = f"{prefix}{pascal}Controller"
                router_var = f"{scope}_router"
                include_line = f"{router_var}.include_router({resource}_router)"
                import_controller = f"from app.api.{scope}.{resource} import {controller_name}"
                import_router = f"from app.api.{scope}.{resource} import router as {resource}_router"
                comment = f"# Codegen auto-registered: {resource}"
                if dry_run:
                    result.files_modified.append(path_str)
                    continue
                content = dest.read_text(encoding="utf-8", errors="replace")
                if include_line not in content:
                    result.files_skipped.append(
                        {"path": path_str, "reason": "register_block_modified"}
                    )
                    continue
                backup_path = backup_dir / path_str
                backup_path.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(dest, backup_path)
                lines = content.splitlines()
                new_lines = []
                for line in lines:
                    stripped = line.strip()
                    if stripped == import_controller or stripped == import_router:
                        continue
                    if stripped == include_line or stripped == comment:
                        continue
                    if re.search(
                        rf'^\s*["\']{re.escape(controller_name)}["\']\s*,?\s*$',
                        line,
                    ):
                        continue
                    new_lines.append(line)
                new_content = "\n".join(new_lines).replace("\n\n\n", "\n\n")
                dest.write_text(new_content.strip() + "\n", encoding="utf-8")
                result.files_modified.append(path_str)

            elif action == "register_model":
                model_meta = f.get("model_meta") or {}
                module = model_meta.get("module", "")
                resource = model_meta.get("resource", "")
                pascal = model_meta.get("pascal", "")
                target = model_meta.get("target", "module")
                if not module or not resource or not pascal:
                    continue
                if not dest.exists():
                    result.files_skipped.append({"path": path_str, "reason": "file_not_found"})
                    continue
                if dry_run:
                    result.files_modified.append(path_str)
                    continue
                content = dest.read_text(encoding="utf-8", errors="replace")
                # 检查是否存在可回滚的内容 / Check if rollback content exists
                is_multiline_block = target in ("root", "env") and (
                    (target == "root" and module == "tenant")
                    or target == "env"
                )
                if is_multiline_block:
                    # 多行块内应有 symbol 行如 "    Article," / Multiline block should have symbol line
                    has_symbol = any(
                        line.strip().rstrip(",").strip() == pascal
                        for line in content.splitlines()
                    )
                    if not has_symbol:
                        result.files_skipped.append(
                            {"path": path_str, "reason": "model_import_modified"}
                        )
                        continue
                else:
                    # 独立 import 行 / Standalone import line
                    import_line = f"from app.models.{module}.{resource} import {pascal}"
                    if import_line not in content:
                        result.files_skipped.append(
                            {"path": path_str, "reason": "model_import_modified"}
                        )
                        continue
                backup_path = backup_dir / path_str
                backup_path.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(dest, backup_path)
                lines = content.splitlines()
                new_lines = []
                for line in lines:
                    stripped = line.strip()
                    sym_in_line = line.strip().rstrip(",").strip() == pascal
                    if is_multiline_block:
                        if sym_in_line:
                            continue
                    else:
                        if stripped == f"from app.models.{module}.{resource} import {pascal}":
                            continue
                    if target != "env" and "__all__" in content and re.search(
                        rf'^\s*["\']{re.escape(pascal)}["\']\s*,?\s*(#.*)?$', line
                    ):
                        continue
                    new_lines.append(line)
                new_content = "\n".join(new_lines).replace("\n\n\n", "\n\n")
                dest.write_text(new_content.strip() + "\n", encoding="utf-8")
                result.files_modified.append(path_str)

        if not dry_run:
            self.manifest.remove_entry(entry.resource)
            # 清理空目录 / Clean up empty directories
            deleted_paths = {self.project_root / f.get("path", "") for f in entry.files if f.get("action") == "create"}
            for p in deleted_paths:
                parent = p.parent if p.suffix else p
                while parent != self.project_root and parent.exists():
                    try:
                        if not any(parent.iterdir()):
                            parent.rmdir()
                            parent = parent.parent
                        else:
                            break
                    except OSError:
                        break

        result.success = True
        return result


__all__ = ["CodegenRollback", "RollbackResult"]
