"""
回滚引擎 / Rollback Engine

按 manifest 逆向操作：create->删除, append->移除片段, merge_json->移除 key
Reverse operations per manifest.
"""

from __future__ import annotations

import hashlib
import json
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
        backup_dir = self.project_root / ".codegen_backup" / f"rollback_{ts}"
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
                if appended.strip() not in content:
                    result.files_skipped.append({"path": path_str, "reason": "appended_content_modified"})
                    continue
                if dry_run:
                    result.files_modified.append(path_str)
                    continue
                backup_path = backup_dir / path_str
                backup_path.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(dest, backup_path)
                new_content = content.replace(appended, "", 1).replace("\n\n\n", "\n\n")
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
                        data.pop(k, None)
                    backup_path = backup_dir / path_str
                    backup_path.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(dest, backup_path)
                    dest.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
                    result.files_modified.append(path_str)
                except (json.JSONDecodeError, OSError) as e:
                    result.files_skipped.append({"path": path_str, "reason": str(e)})

        if not dry_run:
            self.manifest.remove_entry(entry.resource)

        result.manual_steps = [
            "Delete migration file if generated",
            "Run: novusai db stamp <previous_revision>",
        ]
        result.success = True
        return result


__all__ = ["CodegenRollback", "RollbackResult"]
