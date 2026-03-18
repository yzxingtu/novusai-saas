"""
生成清单管理 / Manifest Manager

codegen_manifest.json 记录每次生成的文件，供回滚使用
Records generated files for rollback.
"""

from __future__ import annotations

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

        覆盖同 resource 的旧条目
        Overwrites existing entry for same resource.
        """
        file_list: list[dict[str, Any]] = []
        for f in files:
            item: dict[str, Any] = {"path": f.path, "action": f.action}
            if f.action == "append" and f.appended_content:
                item["appended_content"] = f.appended_content
            elif f.action == "merge_json" and f.merged_keys:
                item["merged_keys"] = f.merged_keys
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
                }
            )
            data["entries"] = entries
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
                )
        return None

    def remove_entry(self, resource: str) -> None:
        """移除条目 / Remove entry."""
        lock_path = Path(str(self.path) + ".lock")
        with FileLock(lock_path):
            data = self._load()
            data["entries"] = [e for e in data.get("entries", []) if e.get("resource") != resource]
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
                )
            )
        return result


__all__ = ["ManifestManager", "ManifestEntry", "MANIFEST_FILENAME"]
