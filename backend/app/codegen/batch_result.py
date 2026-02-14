"""
批量生成结果 — 按实体分组摘要 + i18n 冲突检测

M98-T3: 按实体分组的 preview/generate 结果摘要
M98-T4: i18n 合并冲突检测 + shared_enums 边界声明
"""

from __future__ import annotations

import json
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field

from app.codegen.batch_writer import (
    WritePlan,
    WritePlanAction,
    WritePlanItem,
)
from app.codegen.writer import _deep_merge


class I18nResolution(str, Enum):
    """i18n 冲突解决策略"""

    KEEP_EXISTING = "keep_existing"
    OVERWRITE = "overwrite"


# ============================================================
# Per-Entity 结果分组
# ============================================================


class EntityActionStats(BaseModel):
    """单个实体的操作统计"""

    module: str = Field(..., description="实体模块名")
    create: int = Field(0)
    update: int = Field(0)
    merge: int = Field(0)
    skip: int = Field(0)
    total: int = Field(0)
    files: list[str] = Field(default_factory=list, description="涉及的文件列表")
    errors: list[dict[str, Any]] = Field(
        default_factory=list, description="该实体的错误列表",
    )


class SharedActionStats(BaseModel):
    """共享文件操作统计"""

    create: int = Field(0)
    update: int = Field(0)
    merge: int = Field(0)
    skip: int = Field(0)
    total: int = Field(0)
    files: list[str] = Field(default_factory=list)


class BatchResultSummary(BaseModel):
    """批量生成结果摘要（按实体分组）"""

    entities: list[EntityActionStats] = Field(default_factory=list)
    shared: SharedActionStats = Field(default_factory=SharedActionStats)
    total_files: int = Field(0)
    total_entities: int = Field(0)
    ddl_preview: str = Field("")
    i18n_conflicts: list[I18nConflict] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "entities": [e.model_dump() for e in self.entities],
            "shared": self.shared.model_dump(),
            "total_files": self.total_files,
            "total_entities": self.total_entities,
            "ddl_preview": self.ddl_preview,
            "i18n_conflicts": [c.model_dump() for c in self.i18n_conflicts],
            "warnings": self.warnings,
        }


# ============================================================
# i18n 冲突检测
# ============================================================


class I18nConflict(BaseModel):
    """i18n 键冲突"""

    path: str = Field(..., description="i18n 文件路径")
    key: str = Field(..., description="冲突的键路径 (dot notation)")
    existing_value: str = Field("", description="现有值")
    new_value: str = Field("", description="新值")
    source_entity: str = Field("", description="产生新值的实体")
    resolution: I18nResolution = Field(
        I18nResolution.KEEP_EXISTING,
        description="解决策略",
    )


# Fix forward reference
BatchResultSummary.model_rebuild()


def detect_i18n_conflicts(
    existing_data: dict[str, Any],
    new_data: dict[str, Any],
    path: str,
    source_entity: str = "",
    key_prefix: str = "",
) -> list[I18nConflict]:
    """检测 i18n 深合并中的键冲突

    默认策略：保留既有值（keep_existing）。

    Args:
        existing_data: 现有 i18n 数据
        new_data: 新增 i18n 数据
        path: 文件路径
        source_entity: 产生新数据的实体
        key_prefix: 键路径前缀（递归用）

    Returns:
        冲突列表
    """
    conflicts: list[I18nConflict] = []

    for key, new_value in new_data.items():
        full_key = f"{key_prefix}.{key}" if key_prefix else key

        if key not in existing_data:
            continue  # 新增键，无冲突

        existing_value = existing_data[key]

        if isinstance(new_value, dict) and isinstance(existing_value, dict):
            # 递归检测嵌套对象
            sub_conflicts = detect_i18n_conflicts(
                existing_value, new_value, path,
                source_entity, full_key,
            )
            conflicts.extend(sub_conflicts)
        elif new_value != existing_value:
            # 值不同 → 冲突
            conflicts.append(I18nConflict(
                path=path,
                key=full_key,
                existing_value=str(existing_value),
                new_value=str(new_value),
                source_entity=source_entity,
                resolution="keep_existing",
            ))

    return conflicts


def deep_merge_with_conflict_detection(
    existing: dict[str, Any],
    new_data: dict[str, Any],
    path: str = "",
    source_entity: str = "",
) -> tuple[dict[str, Any], list[I18nConflict]]:
    """深合并 i18n JSON 并返回冲突列表

    规则：
    - 新增键：直接添加
    - 已有键 + 值相同：跳过
    - 已有键 + 值不同：保留旧值，记录冲突
    - 嵌套对象：递归合并

    Returns:
        (合并后的数据, 冲突列表)
    """
    conflicts = detect_i18n_conflicts(existing, new_data, path, source_entity)

    # 深合并（新增键加入，已有键保留旧值）
    merged = _deep_merge_keep_existing(existing, new_data)

    return merged, conflicts


# Reuse _deep_merge from writer.py (same semantics: keep existing keys)
_deep_merge_keep_existing = _deep_merge


# ============================================================
# WritePlan → BatchResultSummary 转换
# ============================================================


def build_result_summary(
    plan: WritePlan,
    entity_file_map: dict[str, str] | None = None,
    errors: list[dict[str, Any]] | None = None,
    i18n_conflicts: list[I18nConflict] | None = None,
) -> BatchResultSummary:
    """从 WritePlan 构建按实体分组的结果摘要

    Args:
        plan: 写盘计划
        entity_file_map: path → entity module 映射
        errors: 写盘错误列表
        i18n_conflicts: i18n 冲突列表

    Returns:
        BatchResultSummary
    """
    entity_file_map = entity_file_map or {}
    errors = errors or []
    i18n_conflicts = i18n_conflicts or []

    # 按实体分组
    entity_stats: dict[str, EntityActionStats] = {}
    shared = SharedActionStats()

    for item in plan.items:
        owner = entity_file_map.get(item.path, item.owner or "")
        action = item.action

        if owner:
            if owner not in entity_stats:
                entity_stats[owner] = EntityActionStats(module=owner)
            stats = entity_stats[owner]
            stats.files.append(item.path)
            stats.total += 1
            if action == WritePlanAction.CREATE:
                stats.create += 1
            elif action == WritePlanAction.UPDATE:
                stats.update += 1
            elif action == WritePlanAction.MERGE:
                stats.merge += 1
            elif action == WritePlanAction.SKIP:
                stats.skip += 1
        else:
            shared.files.append(item.path)
            shared.total += 1
            if action == WritePlanAction.CREATE:
                shared.create += 1
            elif action == WritePlanAction.UPDATE:
                shared.update += 1
            elif action == WritePlanAction.MERGE:
                shared.merge += 1
            elif action == WritePlanAction.SKIP:
                shared.skip += 1

    # 分配错误到实体
    for err in errors:
        err_path = err.get("path", "")
        owner = entity_file_map.get(err_path, "")
        if owner and owner in entity_stats:
            entity_stats[owner].errors.append(err)

    # 按模块名排序
    sorted_entities = sorted(entity_stats.values(), key=lambda s: s.module)

    # 构建 warnings
    warnings: list[str] = []

    # shared_enums v1 边界声明
    if not entity_file_map:
        warnings.append(
            "entity_file_map not provided; "
            "per-entity grouping may be incomplete"
        )

    summary = BatchResultSummary(
        entities=sorted_entities,
        shared=shared,
        total_files=plan.summary.total_files,
        total_entities=len(sorted_entities),
        ddl_preview=plan.ddl_preview,
        i18n_conflicts=i18n_conflicts,
        warnings=warnings,
    )

    return summary


# ============================================================
# shared_enums v1 边界
# ============================================================

SHARED_ENUMS_V1_WARNING = (
    "shared_enums is defined in BatchCrudProject schema but not yet "
    "implemented in v1. Each entity generates its own enums independently. "
    "Cross-entity enum sharing will be available in v2."
)


def check_shared_enums_boundary(
    shared_enums: list[dict[str, Any]] | None,
) -> list[str]:
    """检查 shared_enums 并返回 v1 边界 warning

    v1 策略：不实现 shared_enums 生成，但在输出中给出明确 warning。

    Returns:
        warning 列表
    """
    warnings: list[str] = []
    if shared_enums:
        warnings.append(SHARED_ENUMS_V1_WARNING)
        warnings.append(
            f"Found {len(shared_enums)} shared_enums definition(s) "
            f"that will be ignored in v1"
        )
    return warnings


__all__ = [
    "EntityActionStats",
    "I18nConflict",
    "I18nResolution",
    "SharedActionStats",
    "BatchResultSummary",
    "SHARED_ENUMS_V1_WARNING",
    "build_result_summary",
    "check_shared_enums_boundary",
    "deep_merge_with_conflict_detection",
    "detect_i18n_conflicts",
]
