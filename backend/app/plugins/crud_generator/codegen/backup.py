"""
CRUD Generator — 文件备份与回滚引擎

在代码生成写盘前备份即将被覆盖的文件，支持按生成记录回滚。

备份存储结构::

    .crud-backups/
      {record_id}/
        manifest.json          — 备份清单
        files/
          backend/app/...      — 原始文件镜像

回滚策略：
- create 类型文件 → 删除
- overwrite/merge 类型文件 → 从备份恢复
- hash 校验 → 检测手动修改冲突
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any  # retained for BackupManifest.files (dynamic JSON structure)

from app.core.logging import LogManager

logger = LogManager.get_logger("app")

# 默认备份保留次数
_DEFAULT_MAX_BACKUPS = 10

# 备份目录名
_BACKUP_DIR_NAME = ".crud-backups"


def _file_hash(path: Path) -> str:
    """计算文件 SHA-256 摘要"""
    h = hashlib.sha256()
    try:
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                h.update(chunk)
    except OSError:
        return ""
    return h.hexdigest()


@dataclass
class BackupManifest:
    """备份清单"""
    record_id: int | None
    created_at: str
    project_root: str
    files: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, object]:
        return {
            "record_id": self.record_id,
            "created_at": self.created_at,
            "project_root": self.project_root,
            "files": self.files,
        }

    @classmethod
    def from_dict(cls, data: dict[str, object]) -> BackupManifest:
        return cls(
            record_id=data.get("record_id"),
            created_at=data.get("created_at", ""),
            project_root=data.get("project_root", ""),
            files=data.get("files", []),
        )


@dataclass
class RollbackResult:
    """回滚结果"""
    restored: list[str] = field(default_factory=list)
    deleted: list[str] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)
    conflicts: list[dict[str, str]] = field(default_factory=list)
    errors: list[dict[str, str]] = field(default_factory=list)

    def to_dict(self) -> dict[str, object]:
        return {
            "restored": self.restored,
            "deleted": self.deleted,
            "skipped": self.skipped,
            "conflicts": self.conflicts,
            "errors": self.errors,
            "total_restored": len(self.restored),
            "total_deleted": len(self.deleted),
            "total_skipped": len(self.skipped),
            "total_conflicts": len(self.conflicts),
        }


class BackupEngine:
    """文件备份引擎

    在 CrudWriter.write() 前调用 backup_existing_files() 备份即将被覆盖的文件。

    用法::

        engine = BackupEngine(project_root)
        engine.backup_existing_files(files_dict, record_id=42)
        # ... writer.write(files_dict) ...
    """

    def __init__(self, project_root: str, max_backups: int = _DEFAULT_MAX_BACKUPS):
        self.project_root = Path(project_root)
        self.backup_root = self.project_root / _BACKUP_DIR_NAME
        self.max_backups = max_backups

    def _backup_dir(self, record_id: int | str) -> Path:
        return self.backup_root / str(record_id)

    def backup_existing_files(
        self,
        files: dict[str, str],
        record_id: int | None = None,
    ) -> BackupManifest | None:
        """备份即将被覆盖的现有文件

        只备份磁盘上已存在的文件（新建文件无需备份）。

        Args:
            files: Generator 输出的 {相对路径: 新内容}
            record_id: 生成记录 ID（用于备份目录命名）

        Returns:
            BackupManifest 或 None（无需备份时）
        """
        backup_id = record_id or int(datetime.now().timestamp())
        backup_dir = self._backup_dir(backup_id)
        files_dir = backup_dir / "files"

        manifest = BackupManifest(
            record_id=record_id,
            created_at=datetime.now().isoformat(),
            project_root=str(self.project_root),
        )

        backed_up = 0

        for rel_path in files:
            # 跳过虚拟文件
            if rel_path.startswith("__") and rel_path.endswith("__"):
                continue

            abs_path = self.project_root / rel_path
            if not abs_path.exists():
                manifest.files.append({
                    "path": rel_path,
                    "operation": "create",
                    "backed_up": False,
                })
                continue

            # 备份现有文件
            backup_path = files_dir / rel_path
            backup_path.parent.mkdir(parents=True, exist_ok=True)

            try:
                shutil.copy2(str(abs_path), str(backup_path))
                original_hash = _file_hash(abs_path)
                manifest.files.append({
                    "path": rel_path,
                    "operation": "overwrite",
                    "backed_up": True,
                    "original_hash": original_hash,
                    "original_size": abs_path.stat().st_size,
                })
                backed_up += 1
            except OSError as exc:
                logger.warning("Failed to backup %s: %s", rel_path, exc)
                manifest.files.append({
                    "path": rel_path,
                    "operation": "overwrite",
                    "backed_up": False,
                    "error": str(exc),
                })

        if backed_up == 0:
            # 没有需要备份的文件（全是新建），无需创建备份目录
            return manifest

        # 写入 manifest
        backup_dir.mkdir(parents=True, exist_ok=True)
        manifest_path = backup_dir / "manifest.json"
        manifest_path.write_text(
            json.dumps(manifest.to_dict(), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

        logger.info(
            "Backed up %d files for record %s → %s",
            backed_up, backup_id, backup_dir,
        )

        # 清理旧备份
        self._cleanup_old_backups()

        return manifest

    def rollback_by_record(
        self,
        record_id: int | str,
        file_paths: set[str] | None = None,
        force: bool = False,
    ) -> RollbackResult:
        """根据备份记录回滚文件

        Args:
            record_id: 备份记录 ID
            file_paths: 只回滚指定路径（None = 全部）
            force: 跳过 hash 校验冲突检查

        Returns:
            RollbackResult
        """
        result = RollbackResult()
        backup_dir = self._backup_dir(record_id)
        manifest_path = backup_dir / "manifest.json"

        if not manifest_path.exists():
            result.errors.append({
                "path": "", "error": f"Backup not found for record {record_id}",
            })
            return result

        manifest = BackupManifest.from_dict(
            json.loads(manifest_path.read_text(encoding="utf-8"))
        )

        files_dir = backup_dir / "files"

        for entry in manifest.files:
            rel_path = entry["path"]

            # 过滤指定路径
            if file_paths and rel_path not in file_paths:
                result.skipped.append(rel_path)
                continue

            abs_path = self.project_root / rel_path
            operation = entry.get("operation", "create")

            if operation == "create":
                # 新建的文件 → 删除
                if abs_path.exists():
                    try:
                        abs_path.unlink()
                        result.deleted.append(rel_path)
                    except OSError as exc:
                        result.errors.append({"path": rel_path, "error": str(exc)})
                else:
                    result.skipped.append(rel_path)

            elif entry.get("backed_up"):
                # 被覆盖的文件 → 从备份恢复
                backup_file = files_dir / rel_path

                if not backup_file.exists():
                    result.errors.append({
                        "path": rel_path, "error": "Backup file missing",
                    })
                    continue

                # Hash 校验：检测文件是否被手动修改
                if not force and abs_path.exists():
                    original_hash = entry.get("original_hash", "")
                    current_hash = _file_hash(abs_path)
                    # 如果当前文件既不是原始 hash 也不是生成时的内容
                    # 说明被手动修改过
                    if original_hash and current_hash != original_hash:
                        # 当前内容与备份不同 → 可能手动修改过
                        backup_hash = _file_hash(backup_file)
                        if current_hash != backup_hash:
                            result.conflicts.append({
                                "path": rel_path,
                                "reason": "File modified after generation",
                            })
                            continue

                try:
                    abs_path.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(str(backup_file), str(abs_path))
                    result.restored.append(rel_path)
                except OSError as exc:
                    result.errors.append({"path": rel_path, "error": str(exc)})
            else:
                result.skipped.append(rel_path)

        return result

    def rollback_by_manifest(
        self,
        file_manifest: list[dict[str, object]],
        force: bool = False,
    ) -> RollbackResult:
        """根据 CrudGenerationRecord.file_manifest 回滚（无备份时仅删除新建文件）

        Args:
            file_manifest: 生成记录的 file_manifest JSON
            force: 跳过确认

        Returns:
            RollbackResult
        """
        result = RollbackResult()

        for entry in file_manifest:
            rel_path = entry.get("path", "")
            if not rel_path:
                continue

            abs_path = self.project_root / rel_path
            operation = entry.get("operation", "preview")

            if operation in ("written", "merged") and abs_path.exists():
                try:
                    abs_path.unlink()
                    result.deleted.append(rel_path)
                except OSError as exc:
                    result.errors.append({"path": rel_path, "error": str(exc)})
            else:
                result.skipped.append(rel_path)

        return result

    def list_backups(self) -> list[dict[str, object]]:
        """列出所有备份"""
        if not self.backup_root.exists():
            return []

        backups: list[dict[str, object]] = []
        for d in sorted(self.backup_root.iterdir(), reverse=True):
            if not d.is_dir():
                continue
            manifest_path = d / "manifest.json"
            if manifest_path.exists():
                try:
                    data = json.loads(manifest_path.read_text(encoding="utf-8"))
                    file_count = len([f for f in data.get("files", []) if f.get("backed_up")])
                    backups.append({
                        "record_id": data.get("record_id"),
                        "created_at": data.get("created_at"),
                        "file_count": file_count,
                        "dir": str(d),
                    })
                except (json.JSONDecodeError, OSError):
                    continue

        return backups

    def _cleanup_old_backups(self) -> None:
        """清理超过 max_backups 的旧备份"""
        if not self.backup_root.exists():
            return

        dirs = sorted(
            [d for d in self.backup_root.iterdir() if d.is_dir()],
            key=lambda d: d.stat().st_mtime,
            reverse=True,
        )

        for old_dir in dirs[self.max_backups:]:
            try:
                shutil.rmtree(str(old_dir))
                logger.info("Cleaned up old backup: %s", old_dir.name)
            except OSError as exc:
                logger.warning("Failed to cleanup backup %s: %s", old_dir, exc)


    def delete_files_by_paths(self, relative_paths: list[str]) -> dict[str, object]:
        """Delete generated files by their relative paths.

        Args:
            relative_paths: List of project-relative file paths to delete.

        Returns:
            Dict with total_deleted, total_files, and errors.
        """
        deleted_count = 0
        errors: list[dict[str, str]] = []
        for path in relative_paths:
            abs_path = self.project_root / path
            if abs_path.exists():
                try:
                    abs_path.unlink()
                    deleted_count += 1
                except OSError as exc:
                    errors.append({"path": path, "error": str(exc)})
        return {
            "total_deleted": deleted_count,
            "total_files": len(relative_paths),
            "errors": errors,
        }


__all__ = [
    "BackupEngine",
    "BackupManifest",
    "RollbackResult",
]
