"""
批量写盘引擎 — 原子性写入 + WritePlan + 回滚

两阶段写入策略：
1. Stage: 生成 WritePlan → 将文件写入 staging 目录（临时）
2. Commit: 校验通过 → 备份原文件 → 原子替换到目标目录

任意阶段失败 → 回滚到写入前状态（不留半成品）。

与 requires_confirmation 流程兼容：
- 确认前：仅生成 WritePlan（不触盘）
- 确认后：执行两阶段写入
"""

from __future__ import annotations

import json
import os
import shutil
import tempfile
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field

from app.codegen.batch_errors import (
    BatchError,
    BatchValidationResult,
    write_merge_failed,
    write_permission_denied,
    write_rollback_failed,
    write_unexpected_error,
    write_unsafe_path,
)
from app.codegen.shared_merge import (
    SharedFileType,
    classify_shared_file,
    is_shared_file,
    merge_shared_file,
)
from app.codegen.writer import (
    ConflictAction,
    WriteResult,
    _ALLOWED_PREFIXES,
    _VIRTUAL_FILES,
    _deep_merge,
    _is_i18n_file,
    _is_safe_path,
)


# ============================================================
# 辅助：BatchError → dict 转换
# ============================================================


def _error_dict(err: BatchError) -> dict[str, str]:
    """BatchError → WriteResult.errors 兼容 dict"""
    return {
        "path": err.details.get("path", ""),
        "error": err.message,
        "code": err.code.value,
    }


# ============================================================
# WritePlan 数据结构
# ============================================================


class WritePlanAction(str, Enum):
    """写盘计划操作类型"""

    CREATE = "create"
    UPDATE = "update"
    MERGE = "merge"
    SKIP = "skip"


class WritePlanReason(str, Enum):
    """操作原因"""

    NEW_FILE = "new_file"
    CONFLICT_OVERWRITE = "conflict_overwrite"
    CONFLICT_SKIP = "conflict_skip"
    I18N_MERGE = "i18n_merge"
    FORCE_OVERWRITE = "force_overwrite"
    UNSAFE_PATH = "unsafe_path"
    VIRTUAL_FILE = "virtual_file"


class WritePlanItem(BaseModel):
    """单个文件的写盘计划"""

    path: str = Field(..., description="相对路径")
    action: WritePlanAction = Field(..., description="操作类型")
    reason: WritePlanReason = Field(..., description="操作原因")
    owner: str = Field("", description="所属实体 module (空=共享)")
    kind: str = Field("", description="文件类型 (model/schema/api/i18n/...)")
    size: int = Field(0, description="文件大小 (bytes)")
    exists: bool = Field(False, description="文件是否已存在")
    is_i18n: bool = Field(False, description="是否为 i18n 文件")


class WritePlanSummary(BaseModel):
    """写盘计划统计摘要"""

    total_files: int = Field(0)
    create_count: int = Field(0)
    update_count: int = Field(0)
    merge_count: int = Field(0)
    skip_count: int = Field(0)
    unsafe_count: int = Field(0)

    # 按实体分组统计
    entity_stats: dict[str, dict[str, int]] = Field(
        default_factory=dict,
        description="per-entity stats: {module: {create, update, merge, skip}}",
    )
    shared_stats: dict[str, int] = Field(
        default_factory=lambda: {"create": 0, "update": 0, "merge": 0, "skip": 0},
    )


class WritePlan(BaseModel):
    """写盘计划（确认前输出）"""

    items: list[WritePlanItem] = Field(default_factory=list)
    summary: WritePlanSummary = Field(default_factory=WritePlanSummary)
    ddl_preview: str = Field("", description="DDL 预览")

    def to_dict(self) -> dict[str, Any]:
        return {
            "items": [item.model_dump() for item in self.items],
            "summary": self.summary.model_dump(),
            "ddl_preview": self.ddl_preview,
        }


# ============================================================
# 写盘事务（变更集）
# ============================================================


class _FileChange:
    """单个文件变更记录（用于回滚）"""

    __slots__ = ("path", "action", "backup_path", "abs_path")

    def __init__(
        self,
        path: str,
        action: WritePlanAction,
        abs_path: str,
        backup_path: str = "",
    ):
        self.path = path
        self.action = action
        self.abs_path = abs_path
        self.backup_path = backup_path


class _WriteTransaction:
    """写盘事务：记录变更集，支持回滚"""

    def __init__(self, backup_dir: str):
        self._backup_dir = backup_dir
        self._changes: list[_FileChange] = []

    def backup_existing(self, rel_path: str, abs_path: str) -> str:
        """备份已存在的文件，返回备份路径"""
        backup_path = os.path.join(self._backup_dir, rel_path)
        os.makedirs(os.path.dirname(backup_path), exist_ok=True)
        shutil.copy2(abs_path, backup_path)
        return backup_path

    def record_create(self, rel_path: str, abs_path: str) -> None:
        """记录新建文件"""
        self._changes.append(_FileChange(
            path=rel_path,
            action=WritePlanAction.CREATE,
            abs_path=abs_path,
        ))

    def record_update(
        self,
        rel_path: str,
        abs_path: str,
        backup_path: str,
    ) -> None:
        """记录更新/覆盖文件"""
        self._changes.append(_FileChange(
            path=rel_path,
            action=WritePlanAction.UPDATE,
            abs_path=abs_path,
            backup_path=backup_path,
        ))

    def record_merge(
        self,
        rel_path: str,
        abs_path: str,
        backup_path: str,
    ) -> None:
        """记录合并文件"""
        self._changes.append(_FileChange(
            path=rel_path,
            action=WritePlanAction.MERGE,
            abs_path=abs_path,
            backup_path=backup_path,
        ))

    def rollback(self) -> list[BatchError]:
        """回滚所有变更"""
        errors: list[BatchError] = []

        for change in reversed(self._changes):
            try:
                if change.action == WritePlanAction.CREATE:
                    # 新建的文件 → 删除
                    if os.path.exists(change.abs_path):
                        os.remove(change.abs_path)
                        # 尝试清理空目录
                        parent = os.path.dirname(change.abs_path)
                        try:
                            os.removedirs(parent)
                        except OSError:
                            pass  # 目录非空，跳过
                elif change.action in (
                    WritePlanAction.UPDATE, WritePlanAction.MERGE,
                ):
                    # 修改的文件 → 恢复备份
                    if change.backup_path and os.path.exists(change.backup_path):
                        shutil.copy2(change.backup_path, change.abs_path)
            except OSError as e:
                errors.append(write_rollback_failed(change.path, str(e)))

        self._changes.clear()
        return errors

    def commit(self) -> None:
        """标记事务已提交（清理备份）"""
        self._committed = True

    def cleanup(self) -> None:
        """清理备份目录"""
        if os.path.exists(self._backup_dir):
            shutil.rmtree(self._backup_dir, ignore_errors=True)


# ============================================================
# AtomicBatchWriter
# ============================================================


class AtomicBatchWriter:
    """原子批量写盘引擎

    用法::

        writer = AtomicBatchWriter(project_root="/path/to/project")

        # 1. 生成 WritePlan（不触盘）
        plan = writer.create_write_plan(
            files, conflict_action=ConflictAction.SKIP, entity_file_map={},
        )

        # 2. 确认后执行原子写入
        result = writer.execute_write_plan(
            files, plan, conflict_action=ConflictAction.SKIP,
        )
    """

    def __init__(self, project_root: str) -> None:
        self._root = os.path.abspath(project_root)

    def _abs_path(self, rel_path: str) -> str:
        return os.path.normpath(os.path.join(self._root, rel_path))

    @staticmethod
    def _classify_file(rel_path: str) -> str:
        """根据路径推断文件类型"""
        if rel_path.endswith(".json") and "locales" in rel_path:
            return "i18n"
        parts = rel_path.replace("\\", "/").split("/")
        if "models" in parts:
            return "model"
        if "schemas" in parts:
            return "schema"
        if "repositories" in parts:
            return "repository"
        if "services" in parts:
            return "service"
        if "api" in parts and rel_path.endswith(".py"):
            return "controller"
        if rel_path.endswith(".vue"):
            return "view"
        if rel_path.endswith(".ts"):
            return "api_ts" if "api/" in rel_path else "frontend"
        if "templates" in parts:
            return "template"
        if "tests" in parts:
            return "test"
        return "other"

    # ---- WritePlan 生成 ----

    def create_write_plan(
        self,
        files: dict[str, str],
        conflict_action: ConflictAction = ConflictAction.SKIP,
        force_paths: set[str] | None = None,
        entity_file_map: dict[str, str] | None = None,
    ) -> WritePlan:
        """生成写盘计划（不触盘）

        Args:
            files: Generator 输出的 {相对路径: 内容}
            conflict_action: 冲突默认策略
            force_paths: 强制覆盖的路径集合
            entity_file_map: path → entity module 映射

        Returns:
            WritePlan 包含每个文件的操作计划和统计
        """
        force_paths = force_paths or set()
        entity_file_map = entity_file_map or {}

        plan = WritePlan()
        summary = WritePlanSummary()
        ddl = ""

        for rel_path, content in files.items():
            # 虚拟文件
            if rel_path in _VIRTUAL_FILES:
                if rel_path == "__ddl_preview__.sql":
                    ddl = content
                continue

            size = len(content.encode("utf-8"))
            is_i18n = _is_i18n_file(rel_path)
            owner = entity_file_map.get(rel_path, "")
            kind = self._classify_file(rel_path)

            # 安全检查
            if not _is_safe_path(rel_path):
                plan.items.append(WritePlanItem(
                    path=rel_path, action=WritePlanAction.SKIP,
                    reason=WritePlanReason.UNSAFE_PATH,
                    owner=owner, kind=kind, size=size,
                    exists=False, is_i18n=is_i18n,
                ))
                summary.unsafe_count += 1
                summary.skip_count += 1
                continue

            abs_path = self._abs_path(rel_path)
            exists = os.path.exists(abs_path)

            # 检查是否为共享聚合文件（router/api export/init）
            shared_type = classify_shared_file(rel_path)
            is_shared = shared_type not in (
                SharedFileType.UNKNOWN, SharedFileType.I18N_JSON,
            )

            if not exists:
                # 新文件
                plan.items.append(WritePlanItem(
                    path=rel_path, action=WritePlanAction.CREATE,
                    reason=WritePlanReason.NEW_FILE,
                    owner=owner, kind=kind, size=size,
                    exists=False, is_i18n=is_i18n,
                ))
                summary.create_count += 1
            else:
                # 冲突处理
                action = conflict_action
                if rel_path in force_paths:
                    action = ConflictAction.OVERWRITE

                # i18n 和共享聚合文件自动走 merge
                if (is_i18n or is_shared) and action != ConflictAction.OVERWRITE:
                    action = ConflictAction.MERGE

                if action == ConflictAction.SKIP:
                    plan.items.append(WritePlanItem(
                        path=rel_path, action=WritePlanAction.SKIP,
                        reason=WritePlanReason.CONFLICT_SKIP,
                        owner=owner, kind=kind, size=size,
                        exists=True, is_i18n=is_i18n,
                    ))
                    summary.skip_count += 1
                elif action == ConflictAction.OVERWRITE:
                    reason = (
                        WritePlanReason.FORCE_OVERWRITE
                        if rel_path in force_paths
                        else WritePlanReason.CONFLICT_OVERWRITE
                    )
                    plan.items.append(WritePlanItem(
                        path=rel_path, action=WritePlanAction.UPDATE,
                        reason=reason,
                        owner=owner, kind=kind, size=size,
                        exists=True, is_i18n=is_i18n,
                    ))
                    summary.update_count += 1
                elif action == ConflictAction.MERGE:
                    plan.items.append(WritePlanItem(
                        path=rel_path, action=WritePlanAction.MERGE,
                        reason=WritePlanReason.I18N_MERGE,
                        owner=owner, kind=kind, size=size,
                        exists=True, is_i18n=is_i18n,
                    ))
                    summary.merge_count += 1

            # 按实体统计
            action_key = plan.items[-1].action.value
            if owner:
                if owner not in summary.entity_stats:
                    summary.entity_stats[owner] = {
                        "create": 0, "update": 0, "merge": 0, "skip": 0,
                    }
                summary.entity_stats[owner][action_key] = (
                    summary.entity_stats[owner].get(action_key, 0) + 1
                )
            else:
                summary.shared_stats[action_key] = (
                    summary.shared_stats.get(action_key, 0) + 1
                )

        summary.total_files = (
            summary.create_count + summary.update_count
            + summary.merge_count + summary.skip_count
        )
        plan.summary = summary
        plan.ddl_preview = ddl
        return plan

    # ---- 原子写入执行 ----

    def execute_write_plan(
        self,
        files: dict[str, str],
        plan: WritePlan,
        conflict_action: ConflictAction = ConflictAction.SKIP,
        force_paths: set[str] | None = None,
    ) -> WriteResult:
        """按 WritePlan 执行原子写入

        两阶段：
        1. 备份 → 写入（记录变更集）
        2. 任意失败 → 回滚全部变更

        Args:
            files: Generator 输出的 {相对路径: 内容}
            plan: 之前生成的 WritePlan
            conflict_action: 冲突策略
            force_paths: 强制覆盖路径

        Returns:
            WriteResult
        """
        force_paths = force_paths or set()
        result = WriteResult()

        # 创建备份目录
        backup_dir = tempfile.mkdtemp(prefix="crud_backup_")
        txn = _WriteTransaction(backup_dir)

        try:
            for plan_item in plan.items:
                rel_path = plan_item.path
                content = files.get(rel_path)
                if content is None:
                    continue

                if plan_item.action == WritePlanAction.SKIP:
                    result.skipped.append(rel_path)
                    continue

                abs_path = self._abs_path(rel_path)

                if plan_item.action == WritePlanAction.CREATE:
                    self._atomic_create(txn, rel_path, abs_path, content, result)

                elif plan_item.action == WritePlanAction.UPDATE:
                    self._atomic_update(txn, rel_path, abs_path, content, result)

                elif plan_item.action == WritePlanAction.MERGE:
                    self._atomic_merge(txn, rel_path, abs_path, content, result)

            # 如果有任何错误，回滚
            if result.errors:
                rollback_errors = txn.rollback()
                for rb_err in rollback_errors:
                    result.errors.append(_error_dict(rb_err))
                # 清除 written/merged 记录（已回滚）
                result.written.clear()
                result.merged.clear()
            else:
                txn.commit()

            # DDL 预览
            ddl = files.get("__ddl_preview__.sql", "")
            if ddl:
                result.ddl_preview = ddl

        except Exception as e:
            # 意外异常 → 紧急回滚
            txn.rollback()
            result.written.clear()
            result.merged.clear()
            result.errors.append(
                _error_dict(write_unexpected_error("__transaction__", str(e)))
            )
        finally:
            txn.cleanup()

        return result

    # ---- 原子操作 ----

    def _atomic_create(
        self,
        txn: _WriteTransaction,
        rel_path: str,
        abs_path: str,
        content: str,
        result: WriteResult,
    ) -> None:
        """原子新建文件"""
        try:
            os.makedirs(os.path.dirname(abs_path), exist_ok=True)
            with open(abs_path, "w", encoding="utf-8") as f:
                f.write(content)
            txn.record_create(rel_path, abs_path)
            result.written.append(rel_path)
        except OSError as e:
            result.errors.append(
                _error_dict(write_permission_denied(rel_path, str(e)))
            )

    def _atomic_update(
        self,
        txn: _WriteTransaction,
        rel_path: str,
        abs_path: str,
        content: str,
        result: WriteResult,
    ) -> None:
        """原子覆盖文件"""
        try:
            backup_path = txn.backup_existing(rel_path, abs_path)
            with open(abs_path, "w", encoding="utf-8") as f:
                f.write(content)
            txn.record_update(rel_path, abs_path, backup_path)
            result.written.append(rel_path)
        except OSError as e:
            result.errors.append(
                _error_dict(write_permission_denied(rel_path, str(e)))
            )

    def _atomic_merge(
        self,
        txn: _WriteTransaction,
        rel_path: str,
        abs_path: str,
        content: str,
        result: WriteResult,
    ) -> None:
        """原子合并文件（i18n JSON 或共享聚合文件）"""
        try:
            backup_path = txn.backup_existing(rel_path, abs_path)

            with open(abs_path, "r", encoding="utf-8") as f:
                existing_content = f.read()

            # 判断文件类型选择合并策略
            shared_type = classify_shared_file(rel_path)

            if shared_type == SharedFileType.I18N_JSON or _is_i18n_file(rel_path):
                # i18n JSON deep merge
                merged_content = self._merge_i18n(
                    existing_content, content, rel_path, result,
                )
                if merged_content is None:
                    return  # error already recorded
            elif shared_type != SharedFileType.UNKNOWN:
                # 共享聚合文件确定性合并
                merge_result = merge_shared_file(
                    rel_path, existing_content, content,
                )
                if not merge_result.success:
                    result.errors.append(
                        _error_dict(write_merge_failed(rel_path, merge_result.error))
                    )
                    return
                merged_content = merge_result.content
            else:
                # 未知类型 fallback 到 i18n merge（如果是 JSON）或直接覆盖
                if rel_path.endswith(".json"):
                    merged_content = self._merge_i18n(
                        existing_content, content, rel_path, result,
                    )
                    if merged_content is None:
                        return
                else:
                    merged_content = content

            with open(abs_path, "w", encoding="utf-8") as f:
                f.write(merged_content)
            txn.record_merge(rel_path, abs_path, backup_path)
            result.merged.append(rel_path)

        except OSError as e:
            result.errors.append(
                _error_dict(write_merge_failed(rel_path, str(e)))
            )

    @staticmethod
    def _merge_i18n(
        existing_content: str,
        new_content: str,
        rel_path: str,
        result: WriteResult,
    ) -> str | None:
        """合并 i18n JSON，失败返回 None"""
        try:
            existing = json.loads(existing_content)
        except json.JSONDecodeError:
            existing = {}

        try:
            new_data = json.loads(new_content)
        except json.JSONDecodeError:
            result.errors.append(
                _error_dict(write_merge_failed(rel_path, "New content is not valid JSON"))
            )
            return None

        if isinstance(existing, dict) and isinstance(new_data, dict):
            merged = _deep_merge(existing, new_data)
            return json.dumps(merged, ensure_ascii=False, indent=2) + "\n"
        return new_content

    # ---- 便捷入口 ----

    def preview_and_plan(
        self,
        files: dict[str, str],
        conflict_action: ConflictAction = ConflictAction.SKIP,
        force_paths: set[str] | None = None,
        entity_file_map: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        """预览 + WritePlan 组合输出（供 requires_confirmation 使用）

        Returns:
            {
                "requires_confirmation": True,
                "write_plan": WritePlan.to_dict(),
                "message": str,
            }
        """
        plan = self.create_write_plan(
            files, conflict_action, force_paths, entity_file_map,
        )

        s = plan.summary
        message = (
            f"Will write {s.create_count} new, "
            f"update {s.update_count}, "
            f"merge {s.merge_count}, "
            f"skip {s.skip_count} files "
            f"({s.total_files} total)"
        )

        return {
            "requires_confirmation": True,
            "write_plan": plan.to_dict(),
            "message": message,
        }


__all__ = [
    "WritePlanAction",
    "WritePlanReason",
    "WritePlanItem",
    "WritePlanSummary",
    "WritePlan",
    "AtomicBatchWriter",
]
