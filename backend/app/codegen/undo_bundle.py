"""
Undo Bundle — 生成后回滚包

M58-T19: 批量生成成功后提供可逆的回滚能力

Undo Bundle 格式：
{
    "version": "1.0.0",
    "run_id": "...",
    "created_at": "ISO8601",
    "base_dir": "...",
    "files": [
        {
            "path": "relative/path",
            "action": "created|modified|deleted",
            "original_content": "..." | null,
            "new_content": "...",
            "hash_before": "..." | null,
            "hash_after": "..."
        }
    ]
}

安全边界：
- 所有路径必须在 base_dir 内（禁止目录穿越）
- 回滚时需 requires_confirmation
- dev-only
"""

from __future__ import annotations

import hashlib
import json
import os
import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


BUNDLE_VERSION = "1.0.0"


# ============================================================
# 枚举
# ============================================================


class FileAction(str, Enum):
    """文件操作类型"""

    CREATED = "created"
    MODIFIED = "modified"
    DELETED = "deleted"


# ============================================================
# 模型
# ============================================================


class UndoFileEntry(BaseModel):
    """单个文件的回滚记录"""

    path: str = Field(..., description="相对路径")
    action: FileAction = Field(...)
    original_content: str | None = Field(
        None, description="操作前内容（created 时为 None）",
    )
    new_content: str = Field("", description="操作后内容")
    hash_before: str | None = Field(None)
    hash_after: str = Field("")


class UndoBundle(BaseModel):
    """Undo Bundle"""

    version: str = Field(BUNDLE_VERSION)
    run_id: str = Field(
        default_factory=lambda: uuid.uuid4().hex[:12],
    )
    created_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(),
    )
    base_dir: str = Field("")
    files: list[UndoFileEntry] = Field(default_factory=list)

    def file_count(self) -> int:
        return len(self.files)

    def created_files(self) -> list[UndoFileEntry]:
        return [f for f in self.files if f.action == FileAction.CREATED]

    def modified_files(self) -> list[UndoFileEntry]:
        return [f for f in self.files if f.action == FileAction.MODIFIED]

    def summary(self) -> dict[str, Any]:
        return {
            "version": self.version,
            "run_id": self.run_id,
            "file_count": self.file_count(),
            "created": len(self.created_files()),
            "modified": len(self.modified_files()),
        }

    def to_json(self) -> str:
        return self.model_dump_json(indent=2)


class RevertResult(BaseModel):
    """回滚结果"""

    success: bool = Field(True)
    reverted: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)


# ============================================================
# 辅助
# ============================================================


def _content_hash(content: str) -> str:
    """计算内容 hash"""
    return hashlib.sha256(content.encode("utf-8")).hexdigest()[:12]


def _is_safe_path(path: str, base_dir: str) -> bool:
    """检查路径是否安全（在 base_dir 内）"""
    abs_path = os.path.normpath(os.path.join(base_dir, path))
    abs_base = os.path.normpath(base_dir)
    return abs_path.startswith(abs_base)


# ============================================================
# Bundle 构建
# ============================================================


def build_undo_bundle(
    base_dir: str,
    written_files: list[dict[str, Any]],
    run_id: str = "",
) -> UndoBundle:
    """从写盘结果构建 Undo Bundle

    Args:
        base_dir: 项目根目录
        written_files: 写盘结果列表，每项包含：
            - path: 相对路径
            - action: "created" | "modified"
            - original_content: 写入前内容（created 时为 None）
            - new_content: 写入后内容
        run_id: 关联的 run ID

    Returns:
        UndoBundle
    """
    entries: list[UndoFileEntry] = []

    for f in written_files:
        path = f.get("path", "")
        if not path:
            continue

        # 安全检查
        if not _is_safe_path(path, base_dir):
            continue

        action_str = f.get("action", "created")
        try:
            action = FileAction(action_str)
        except ValueError:
            action = FileAction.CREATED

        original = f.get("original_content")
        new_content = f.get("new_content", "")

        entries.append(UndoFileEntry(
            path=path,
            action=action,
            original_content=original,
            new_content=new_content,
            hash_before=_content_hash(original) if original else None,
            hash_after=_content_hash(new_content),
        ))

    return UndoBundle(
        run_id=run_id or uuid.uuid4().hex[:12],
        base_dir=base_dir,
        files=entries,
    )


# ============================================================
# 回滚
# ============================================================


def compute_revert_plan(bundle: UndoBundle) -> list[dict[str, Any]]:
    """计算回滚计划（不执行）

    Returns:
        [{"path": ..., "action": "delete"|"restore", "content": ...}, ...]
    """
    plan: list[dict[str, Any]] = []

    for entry in bundle.files:
        if entry.action == FileAction.CREATED:
            # 新建的文件 → 删除
            plan.append({
                "path": entry.path,
                "action": "delete",
                "content": None,
            })
        elif entry.action == FileAction.MODIFIED:
            # 修改的文件 → 恢复原内容
            plan.append({
                "path": entry.path,
                "action": "restore",
                "content": entry.original_content,
            })

    return plan


def apply_revert(
    bundle: UndoBundle,
    *,
    write_fn: Any | None = None,
    delete_fn: Any | None = None,
) -> RevertResult:
    """应用回滚

    Args:
        bundle: Undo Bundle
        write_fn: 写入函数 (path, content) → None
        delete_fn: 删除函数 (path) → None

    如果 write_fn/delete_fn 为 None，返回 dry-run 结果。

    Returns:
        RevertResult
    """
    result = RevertResult()
    plan = compute_revert_plan(bundle)
    dry_run = write_fn is None and delete_fn is None

    for step in plan:
        path = step["path"]

        # 安全检查
        if not _is_safe_path(path, bundle.base_dir):
            result.errors.append(f"Unsafe path: {path}")
            continue

        try:
            if step["action"] == "delete":
                if not dry_run and delete_fn:
                    delete_fn(os.path.join(bundle.base_dir, path))
                result.reverted.append(path)

            elif step["action"] == "restore":
                content = step["content"]
                if content is None:
                    result.errors.append(
                        f"Cannot restore '{path}': no original content recorded",
                    )
                    continue
                if not dry_run and write_fn:
                    write_fn(os.path.join(bundle.base_dir, path), content)
                result.reverted.append(path)

        except Exception as e:
            result.errors.append(f"Failed to revert '{path}': {e}")

    if result.errors:
        result.success = False

    return result


# ============================================================
# Bundle 序列化/反序列化
# ============================================================


def export_bundle(bundle: UndoBundle) -> str:
    """导出为 JSON 字符串"""
    return bundle.to_json()


def import_bundle(raw: str | dict[str, Any]) -> UndoBundle:
    """从 JSON 导入"""
    if isinstance(raw, str):
        data = json.loads(raw)
    else:
        data = raw
    return UndoBundle(**data)


__all__ = [
    "BUNDLE_VERSION",
    "FileAction",
    "RevertResult",
    "UndoBundle",
    "UndoFileEntry",
    "apply_revert",
    "build_undo_bundle",
    "compute_revert_plan",
    "export_bundle",
    "import_bundle",
]
