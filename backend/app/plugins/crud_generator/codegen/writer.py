"""
CRUD 代码生成器 — Writer（文件写入器）

负责将 Generator 输出的 {filepath: content} 写入磁盘。
- 冲突检测：文件已存在时返回冲突列表
- i18n 追加模式：合并 JSON 而非覆盖
- DDL 预览：不写入磁盘，仅返回 SQL
- 安全检查：路径白名单 + normalize
"""

from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass, field
from enum import Enum
from typing import Any  # retained for preview() entry dicts (dynamic keys)



# ============================================================
# 数据类型
# ============================================================


class ConflictAction(str, Enum):
    """冲突处理策略"""

    SKIP = "skip"
    OVERWRITE = "overwrite"
    MERGE = "merge"


@dataclass
class FileConflict:
    """文件冲突信息"""

    path: str
    existing_size: int
    new_size: int
    is_i18n: bool = False

    def to_dict(self) -> dict[str, object]:
        return {
            "path": self.path,
            "existing_size": self.existing_size,
            "new_size": self.new_size,
            "is_i18n": self.is_i18n,
        }


@dataclass
class WriteResult:
    """写入结果"""

    written: list[str] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)
    merged: list[str] = field(default_factory=list)
    errors: list[dict[str, str]] = field(default_factory=list)
    ddl_preview: str = ""
    file_hashes: dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> dict[str, object]:
        return {
            "written": self.written,
            "skipped": self.skipped,
            "merged": self.merged,
            "errors": self.errors,
            "ddl_preview": self.ddl_preview,
            "total_files": len(self.written) + len(self.merged),
            "file_hashes": self.file_hashes,
        }


# ============================================================
# 路径安全
# ============================================================

# 允许写入的目录前缀白名单（相对于项目根目录）
_ALLOWED_PREFIXES = (
    "backend/app/",
    "backend/tests/",
    "backend/migrations/versions/crud/",
    "frontend/apps/web-antd/src/",
)

# 特殊文件不写入磁盘
_VIRTUAL_FILES = ("__ddl_preview__.sql", "__entity_file_map__.json")


def _is_safe_path(rel_path: str) -> bool:
    """检查相对路径是否在白名单内

    安全规则:
    - 拒绝空路径
    - 拒绝包含 null 字节
    - 拒绝绝对路径 (以 / 开头)
    - 拒绝 Windows 盘符跳转 (C:, D: 等)
    - 拒绝路径穿越 (..)
    - 必须在白名单前缀内
    """
    if not rel_path:
        return False
    if "\x00" in rel_path:
        return False
    normalized = os.path.normpath(rel_path).replace("\\", "/")
    # 拒绝绝对路径
    if normalized.startswith("/"):
        return False
    # 拒绝 Windows 盘符 (e.g. C:, D:\)
    if len(normalized) >= 2 and normalized[1] == ":":
        return False
    # 拒绝路径穿越
    if ".." in normalized.split("/"):
        return False
    return any(normalized.startswith(prefix) for prefix in _ALLOWED_PREFIXES)


def _is_i18n_file(rel_path: str) -> bool:
    """判断是否为 i18n JSON 文件"""
    return rel_path.endswith(".json") and (
        "locales/" in rel_path or "locales\\" in rel_path
    )


# ============================================================
# Writer
# ============================================================


class CrudWriter:
    """CRUD 文件写入器

    用法::

        writer = CrudWriter(project_root="/path/to/project")

        # 1. 冲突检测（预览模式）
        conflicts = writer.detect_conflicts(files)

        # 2. 写入磁盘
        result = writer.write(files, conflict_action=ConflictAction.SKIP)
    """

    def __init__(self, project_root: str) -> None:
        self._root = os.path.abspath(project_root)

    def _abs_path(self, rel_path: str) -> str:
        """转为绝对路径"""
        normalized = os.path.normpath(rel_path).replace("\\", "/")
        return os.path.join(self._root, normalized)

    # ---- 冲突检测 ----

    def detect_conflicts(self, files: dict[str, str]) -> list[FileConflict]:
        """检测哪些文件已存在

        Args:
            files: Generator 输出的 {相对路径: 内容}

        Returns:
            已存在文件的冲突列表
        """
        conflicts: list[FileConflict] = []

        for rel_path, content in files.items():
            if rel_path in _VIRTUAL_FILES:
                continue
            abs_path = self._abs_path(rel_path)
            if os.path.exists(abs_path):
                existing_size = os.path.getsize(abs_path)
                conflicts.append(
                    FileConflict(
                        path=rel_path,
                        existing_size=existing_size,
                        new_size=len(content.encode("utf-8")),
                        is_i18n=_is_i18n_file(rel_path),
                    )
                )

        return conflicts

    # ---- i18n JSON 合并 ----

    @staticmethod
    def _merge_i18n_json(existing_content: str, new_content: str) -> str:
        """合并 i18n JSON，已有 key 不覆盖，新 key 追加

        Args:
            existing_content: 现有文件内容
            new_content: 新生成的内容

        Returns:
            合并后的 JSON 字符串
        """
        try:
            existing = json.loads(existing_content)
        except json.JSONDecodeError:
            return new_content

        try:
            new_data = json.loads(new_content)
        except json.JSONDecodeError:
            return existing_content

        merged = _deep_merge(existing, new_data)
        return json.dumps(merged, ensure_ascii=False, indent=2) + "\n"

    # ---- 写入文件 ----

    def _write_file(self, rel_path: str, content: str) -> None:
        """写入单个文件，自动创建目录"""
        abs_path = self._abs_path(rel_path)
        os.makedirs(os.path.dirname(abs_path), exist_ok=True)
        with open(abs_path, "w", encoding="utf-8") as f:
            f.write(content)

    def write(
        self,
        files: dict[str, str],
        conflict_action: ConflictAction = ConflictAction.SKIP,
        force_paths: set[str] | None = None,
        backup_record_id: int | None = None,
    ) -> WriteResult:
        """将文件写入磁盘

        Args:
            files: Generator 输出的 {相对路径: 内容}
            conflict_action: 冲突时的默认处理策略
            force_paths: 强制覆盖的路径集合（无论 conflict_action）
            backup_record_id: 生成记录 ID，传入时自动备份被覆盖的文件

        Returns:
            WriteResult 包含写入/跳过/合并/错误详情
        """
        # 写盘前备份（best-effort）
        if backup_record_id is not None:
            try:
                from app.plugins.crud_generator.codegen.backup import BackupEngine
                engine = BackupEngine(self._root)
                engine.backup_existing_files(files, record_id=backup_record_id)
            except Exception as exc:
                from app.core.logging import LogManager
                LogManager.get_logger("app").warning(
                    "Backup failed (non-blocking): %s", exc,
                )
        result = WriteResult()
        force_paths = force_paths or set()

        for rel_path, content in files.items():
            # 虚拟文件
            if rel_path in _VIRTUAL_FILES:
                if rel_path == "__ddl_preview__.sql":
                    result.ddl_preview = content
                continue

            # 路径安全检查
            if not _is_safe_path(rel_path):
                result.errors.append(
                    {"path": rel_path, "error": "Path not in allowed whitelist",
                     "code": "W_UNSAFE_PATH"}
                )
                continue

            abs_path = self._abs_path(rel_path)
            exists = os.path.exists(abs_path)

            if not exists:
                # 新文件，直接写入
                try:
                    self._write_file(rel_path, content)
                    result.written.append(rel_path)
                    result.file_hashes[rel_path] = hashlib.sha256(
                        content.encode("utf-8")
                    ).hexdigest()
                except OSError as e:
                    result.errors.append(
                        {"path": rel_path, "error": str(e),
                         "code": "W_PERMISSION_DENIED"}
                    )
                continue

            # 文件已存在 —— 冲突处理
            action = conflict_action
            if rel_path in force_paths:
                action = ConflictAction.OVERWRITE

            # i18n 文件默认使用合并模式
            if _is_i18n_file(rel_path) and action != ConflictAction.OVERWRITE:
                action = ConflictAction.MERGE

            if action == ConflictAction.SKIP:
                result.skipped.append(rel_path)
            elif action == ConflictAction.OVERWRITE:
                try:
                    self._write_file(rel_path, content)
                    result.written.append(rel_path)
                    result.file_hashes[rel_path] = hashlib.sha256(
                        content.encode("utf-8")
                    ).hexdigest()
                except OSError as e:
                    result.errors.append(
                        {"path": rel_path, "error": str(e),
                         "code": "W_PERMISSION_DENIED"}
                    )
            elif action == ConflictAction.MERGE:
                try:
                    with open(abs_path, "r", encoding="utf-8") as f:
                        existing_content = f.read()
                    merged = self._merge_i18n_json(existing_content, content)
                    self._write_file(rel_path, merged)
                    result.merged.append(rel_path)
                    result.file_hashes[rel_path] = hashlib.sha256(
                        merged.encode("utf-8")
                    ).hexdigest()
                except (OSError, ValueError) as e:
                    result.errors.append(
                        {"path": rel_path, "error": str(e),
                         "code": "W_MERGE_FAILED"}
                    )

        return result

    # ---- 预览模式 ----

    def preview(
        self,
        files: dict[str, str],
        include_content: bool = False,
        warnings: list[str] | None = None,
    ) -> dict[str, object]:
        """预览生成结果（不写入磁盘）

        Args:
            files: Generator 输出的 {相对路径: 内容}
            include_content: 是否在文件列表中包含文件内容
            warnings: 来自上层的警告信息列表

        Returns:
            {
                "files": [{path, size, exists, is_i18n, operation, content?}],
                "conflicts": [FileConflict],
                "warnings": [str],
                "ddl_preview": str,
                "total_new": int,
                "total_conflict": int,
            }
        """
        conflicts = self.detect_conflicts(files)
        conflict_paths = {c.path for c in conflicts}

        file_list: list[dict[str, object]] = []
        ddl = ""

        for rel_path, content in files.items():
            if rel_path in _VIRTUAL_FILES:
                if rel_path == "__ddl_preview__.sql":
                    ddl = content
                continue

            exists = rel_path in conflict_paths
            is_i18n = _is_i18n_file(rel_path)

            if not exists:
                operation = "create"
            elif is_i18n:
                operation = "merge"
            else:
                operation = "conflict"

            entry: dict[str, object] = {
                "path": rel_path,
                "size": len(content.encode("utf-8")),
                "exists": exists,
                "is_i18n": is_i18n,
                "operation": operation,
            }
            if include_content:
                entry["content"] = content

            file_list.append(entry)

        return {
            "files": file_list,
            "conflicts": [c.to_dict() for c in conflicts],
            "warnings": warnings or [],
            "ddl_preview": ddl,
            "total_new": len(file_list) - len(conflicts),
            "total_conflict": len(conflicts),
        }



# ============================================================
# 辅助函数
# ============================================================


def _deep_merge(base: dict, overlay: dict) -> dict:
    """深度合并字典，已有 key 不覆盖

    Args:
        base: 基础字典（保留已有 key）
        overlay: 新增字典（仅追加不存在的 key）

    Returns:
        合并后的字典
    """
    result = dict(base)
    for key, value in overlay.items():
        if key not in result:
            result[key] = value
        elif isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = _deep_merge(result[key], value)
        # 已有 key 且非 dict → 保留原值
    return result


__all__ = [
    "ConflictAction",
    "CrudWriter",
    "FileConflict",
    "WriteResult",
]
