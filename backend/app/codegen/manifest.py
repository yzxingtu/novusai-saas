"""
生成清单管理 / Manifest Manager

codegen_manifest.json 记录每次生成的文件，供回滚使用
Records generated files for rollback.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from filelock import FileLock

from app.codegen.generator import GeneratedFile

MANIFEST_FILENAME = "codegen_manifest.json"


@dataclass
class ManifestEntry:
    """清单条目 / Manifest entry."""

    resource: str
    module: str
    generated_at: str
    config_id: int | None
    config_hash: str | None
    files: list[dict[str, Any]] = field(default_factory=list)
    migration_file: str | None = None
    file_rollback_completed: bool = False


class ManifestManager:
    """
    清单管理器 / Manifest manager.

    管理 codegen_manifest.json 的读写
    """

    def __init__(self, project_root: Path | None = None):
        self.project_root = Path(project_root) if project_root else Path.cwd()
        self.path = self.project_root / MANIFEST_FILENAME

    def _load(self) -> dict[str, Any]:
        """加载清单 / Load manifest."""
        if not self.path.exists():
            return {"entries": [], "version": 1}
        try:
            return json.loads(self.path.read_text(encoding="utf-8", errors="replace"))
        except json.JSONDecodeError:
            return {"entries": [], "version": 1}

    def _save_unlocked(self, data: dict[str, Any]) -> None:
        """保存清单(内部) / Save manifest (internal, caller holds lock)."""
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(
            json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )

    def _file_hash(self, path: Path) -> str | None:
        """计算文件 hash 用于回滚校验 / Compute file hash for rollback verification."""
        if not path.exists() or not path.is_file():
            return None
        return hashlib.sha256(path.read_bytes()).hexdigest()

    def add_entry(
        self,
        resource: str,
        module: str,
        config_id: int | None,
        files: list[GeneratedFile],
        config_hash: str | None = None,
    ) -> None:
        """
        添加清单条目 / Add manifest entry.

        覆盖同 resource 的旧条目；仅对 create 记录文件 hash，
        对共享文件动作记录片段级快照，避免其他资源变更后整文件 hash 误伤回滚。
        Overwrites existing entry for same resource. Records create hashes and fragment snapshots
        for shared-file rollback.
        """
        file_list: list[dict[str, Any]] = []
        for f in files:
            item: dict[str, Any] = {"path": f.path, "action": f.action}
            if f.action == "create" and f.content:
                item["content_hash"] = hashlib.sha256(
                    f.content.encode("utf-8")
                ).hexdigest()
            elif f.action == "append" and f.appended_content:
                item["appended_content"] = f.appended_content
            elif f.action == "merge_json" and f.merged_keys:
                item["merged_keys"] = f.merged_keys
                try:
                    item["merged_data"] = json.loads(f.content) if f.content else {}
                except json.JSONDecodeError:
                    item["merged_data"] = {}
            elif f.action == "register_route" and f.route_meta:
                item["route_meta"] = f.route_meta
            elif f.action == "register_model" and f.model_meta:
                item["model_meta"] = f.model_meta
            file_list.append(item)

        lock_path = Path(str(self.path) + ".lock")
        with FileLock(lock_path):
            data = self._load()
            entries = data.get("entries", [])
            entries = [e for e in entries if e.get("resource") != resource]
            entries.append(
                {
                    "resource": resource,
                    "module": module,
                    "generated_at": datetime.now(timezone.utc).isoformat(),
                    "config_id": config_id,
                    "config_hash": config_hash,
                    "files": file_list,
                    "migration_file": None,
                    "file_rollback_completed": False,
                }
            )
            data["entries"] = entries
            self._save_unlocked(data)

    def update_config_id(self, resource: str, config_id: int) -> None:
        """更新某 resource 对应条目的 config_id / Update config_id for resource entry."""
        lock_path = Path(str(self.path) + ".lock")
        with FileLock(lock_path):
            data = self._load()
            for e in data.get("entries", []):
                if e.get("resource") == resource:
                    e["config_id"] = config_id
                    break
            self._save_unlocked(data)

    def update_migration_file(self, resource: str, migration_path: str) -> None:
        """更新某 resource 对应条目的 migration_file / Update migration file path for resource entry."""
        lock_path = Path(str(self.path) + ".lock")
        with FileLock(lock_path):
            data = self._load()
            for e in data.get("entries", []):
                if e.get("resource") == resource:
                    e["migration_file"] = migration_path
                    break
            self._save_unlocked(data)

    def mark_file_rollback_completed(
        self, resource: str, completed: bool = True
    ) -> None:
        """标记文件回滚阶段是否已完成 / Mark whether file rollback stage completed."""
        lock_path = Path(str(self.path) + ".lock")
        with FileLock(lock_path):
            data = self._load()
            for e in data.get("entries", []):
                if e.get("resource") == resource:
                    e["file_rollback_completed"] = completed
                    break
            self._save_unlocked(data)

    def get_entry(self, resource: str) -> ManifestEntry | None:
        """获取资源对应条目 / Get entry by resource."""
        data = self._load()
        for e in data.get("entries", []):
            if e.get("resource") == resource:
                return ManifestEntry(
                    resource=str(e.get("resource", "")),
                    module=str(e.get("module", "")),
                    generated_at=str(e.get("generated_at", "")),
                    config_id=e.get("config_id"),
                    config_hash=e.get("config_hash"),
                    files=list(e.get("files", [])),
                    migration_file=e.get("migration_file"),
                    file_rollback_completed=bool(
                        e.get("file_rollback_completed", False)
                    ),
                )
        return None

    def find_entry_for_config(
        self, resource: str | None, config_id: int
    ) -> ManifestEntry | None:
        """
        按 resource 或 config_id 查找清单条目（与回滚 API 查找逻辑一致）.
        Match rollback API lookup: by resource first, then by config_id.
        """
        entries = self.list_entries()
        if resource:
            for e in entries:
                if e.resource == resource:
                    return e
        for e in entries:
            if e.config_id == config_id:
                return e
        return None

    def manifest_index(self) -> tuple[set[str], set[int]]:
        """
        单次读盘：有清单条目的 resource 集合、config_id 集合 / One load for batch lookups.
        """
        entries = self.list_entries()
        resources = {e.resource for e in entries if e.resource}
        cids = {e.config_id for e in entries if e.config_id is not None}
        return resources, cids

    def remove_entry(self, resource: str) -> None:
        """移除条目 / Remove entry."""
        lock_path = Path(str(self.path) + ".lock")
        with FileLock(lock_path):
            data = self._load()
            data["entries"] = [
                e for e in data.get("entries", []) if e.get("resource") != resource
            ]
            self._save_unlocked(data)

    def list_entries(self) -> list[ManifestEntry]:
        """列出所有条目 / List all entries."""
        data = self._load()
        result: list[ManifestEntry] = []
        for e in data.get("entries", []):
            result.append(
                ManifestEntry(
                    resource=str(e.get("resource", "")),
                    module=str(e.get("module", "")),
                    generated_at=str(e.get("generated_at", "")),
                    config_id=e.get("config_id"),
                    config_hash=e.get("config_hash"),
                    files=list(e.get("files", [])),
                    migration_file=e.get("migration_file"),
                    file_rollback_completed=bool(
                        e.get("file_rollback_completed", False)
                    ),
                )
            )
        return result


__all__ = ["ManifestManager", "ManifestEntry", "MANIFEST_FILENAME"]
