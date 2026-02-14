"""
BatchCrudProject 增量合并引擎

支持 AI 追加/修正某个实体配置时，与现有 BatchCrudProject 进行幂等合并，
避免覆盖用户已修改内容。

核心规则：
- entity.module 作为实体稳定主键
- 子结构（fields/relations/enums/indexes）按各自主键幂等去重
- touchedPaths 保护用户已编辑的路径不被 AI 覆盖
- 合并结果返回结构化 merge_summary
"""

from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field

from app.codegen.schemas import (
    BatchCrudProject,
    CrudConfig,
    EntityRelation,
    EnumDefinition,
    FieldConfig,
    IndexConfig,
    RelationConfig,
)


# ============================================================
# 枚举 & 常量
# ============================================================


class MergeAction(str, Enum):
    """合并操作类型"""

    ADDED = "added"
    UPDATED = "updated"
    SKIPPED = "skipped"


class SkipReason(str, Enum):
    """跳过原因"""

    TOUCHED_PATH = "touched_path"
    IDENTICAL = "identical"
    DELETE_FORBIDDEN = "delete_forbidden"


# touchedPaths 可保护的路径前缀
PROTECTABLE_PATHS = frozenset({
    "fields",
    "relations",
    "enums",
    "indexes",
    "search_config",
    "list_config",
    "form_config",
    "permissions",
    "hooks",
    "custom_slots",
    "layout",
    "style",
    "animation",
    "import_export",
    "selectable",
    "i18n_keys",
    "logic_flows",
    "operations",
    "scope",
    "parent_menu",
    "display_name",
    "display_name_en",
    "description",
    "soft_delete",
    "drag_sort",
    "has_status_toggle",
    "recyclable",
    "inline_edit",
    "observability",
    "nl_query",
    "git",
    "audit",
    "test",
})


# ============================================================
# merge_summary 输出结构
# ============================================================


class PathChange(BaseModel):
    """单个路径的变更记录"""

    path: str = Field(..., description="变更路径 (如 'fields', 'enums')")
    action: MergeAction = Field(..., description="操作类型")
    detail: str = Field("", description="变更细节")
    skip_reason: SkipReason | None = Field(None, description="跳过原因")


class EntityMergeSummary(BaseModel):
    """单个实体的合并摘要"""

    module: str = Field(..., description="实体 module")
    action: MergeAction = Field(..., description="实体级操作: added/updated/skipped")
    changes: list[PathChange] = Field(default_factory=list, description="路径级变更")


class MergeSummary(BaseModel):
    """BatchCrudProject 合并摘要"""

    entities: list[EntityMergeSummary] = Field(default_factory=list)
    cross_relations: PathChange | None = Field(None)
    shared_enums: PathChange | None = Field(None)
    generation_order: PathChange | None = Field(None)
    project_level: list[PathChange] = Field(default_factory=list)

    @property
    def total_added(self) -> int:
        return sum(1 for e in self.entities if e.action == MergeAction.ADDED)

    @property
    def total_updated(self) -> int:
        return sum(1 for e in self.entities if e.action == MergeAction.UPDATED)

    @property
    def total_skipped(self) -> int:
        return sum(1 for e in self.entities if e.action == MergeAction.SKIPPED)


# ============================================================
# 子结构去重工具
# ============================================================


def _merge_fields(
    existing: list[FieldConfig],
    incoming: list[FieldConfig],
    touched: bool,
) -> tuple[list[FieldConfig], list[PathChange]]:
    """合并字段列表，以 field.name 为主键"""
    if touched:
        return existing, [PathChange(
            path="fields",
            action=MergeAction.SKIPPED,
            detail=f"fields locked ({len(incoming)} incoming ignored)",
            skip_reason=SkipReason.TOUCHED_PATH,
        )]

    changes: list[PathChange] = []
    by_name = {f.name: (i, f) for i, f in enumerate(existing)}
    result = list(existing)

    for field in incoming:
        if field.name in by_name:
            idx, old = by_name[field.name]
            if old.model_dump() != field.model_dump():
                result[idx] = field
                changes.append(PathChange(
                    path=f"fields.{field.name}",
                    action=MergeAction.UPDATED,
                    detail=f"field '{field.name}' updated",
                ))
            # identical → skip silently (idempotent)
        else:
            result.append(field)
            by_name[field.name] = (len(result) - 1, field)
            changes.append(PathChange(
                path=f"fields.{field.name}",
                action=MergeAction.ADDED,
                detail=f"field '{field.name}' added",
            ))

    return result, changes


def _merge_relations(
    existing: list[RelationConfig],
    incoming: list[RelationConfig],
    touched: bool,
) -> tuple[list[RelationConfig], list[PathChange]]:
    """合并关联关系列表，以 relation.name 为主键"""
    if touched:
        return existing, [PathChange(
            path="relations",
            action=MergeAction.SKIPPED,
            detail=f"relations locked ({len(incoming)} incoming ignored)",
            skip_reason=SkipReason.TOUCHED_PATH,
        )]

    changes: list[PathChange] = []
    by_name = {r.name: (i, r) for i, r in enumerate(existing)}
    result = list(existing)

    for rel in incoming:
        if rel.name in by_name:
            idx, old = by_name[rel.name]
            if old.model_dump() != rel.model_dump():
                result[idx] = rel
                changes.append(PathChange(
                    path=f"relations.{rel.name}",
                    action=MergeAction.UPDATED,
                    detail=f"relation '{rel.name}' updated",
                ))
        else:
            result.append(rel)
            by_name[rel.name] = (len(result) - 1, rel)
            changes.append(PathChange(
                path=f"relations.{rel.name}",
                action=MergeAction.ADDED,
                detail=f"relation '{rel.name}' added",
            ))

    return result, changes


def _merge_enums(
    existing: list[EnumDefinition],
    incoming: list[EnumDefinition],
    touched: bool,
) -> tuple[list[EnumDefinition], list[PathChange]]:
    """合并枚举定义列表，以 enum.name 为主键"""
    if touched:
        return existing, [PathChange(
            path="enums",
            action=MergeAction.SKIPPED,
            detail=f"enums locked ({len(incoming)} incoming ignored)",
            skip_reason=SkipReason.TOUCHED_PATH,
        )]

    changes: list[PathChange] = []
    by_name = {e.name: (i, e) for i, e in enumerate(existing)}
    result = list(existing)

    for enum in incoming:
        if enum.name in by_name:
            idx, old = by_name[enum.name]
            if old.model_dump() != enum.model_dump():
                result[idx] = enum
                changes.append(PathChange(
                    path=f"enums.{enum.name}",
                    action=MergeAction.UPDATED,
                    detail=f"enum '{enum.name}' updated",
                ))
        else:
            result.append(enum)
            by_name[enum.name] = (len(result) - 1, enum)
            changes.append(PathChange(
                path=f"enums.{enum.name}",
                action=MergeAction.ADDED,
                detail=f"enum '{enum.name}' added",
            ))

    return result, changes


def _merge_indexes(
    existing: list[IndexConfig],
    incoming: list[IndexConfig],
    touched: bool,
) -> tuple[list[IndexConfig], list[PathChange]]:
    """合并索引列表，以 fields 元组为主键"""
    if touched:
        return existing, [PathChange(
            path="indexes",
            action=MergeAction.SKIPPED,
            detail=f"indexes locked ({len(incoming)} incoming ignored)",
            skip_reason=SkipReason.TOUCHED_PATH,
        )]

    changes: list[PathChange] = []

    def _idx_key(idx: IndexConfig) -> tuple[str, ...]:
        return tuple(sorted(idx.fields))

    by_key = {_idx_key(idx): (i, idx) for i, idx in enumerate(existing)}
    result = list(existing)

    for idx in incoming:
        key = _idx_key(idx)
        if key in by_key:
            pos, old = by_key[key]
            if old.model_dump() != idx.model_dump():
                result[pos] = idx
                changes.append(PathChange(
                    path=f"indexes.{','.join(key)}",
                    action=MergeAction.UPDATED,
                    detail=f"index on ({','.join(key)}) updated",
                ))
        else:
            result.append(idx)
            by_key[key] = (len(result) - 1, idx)
            changes.append(PathChange(
                path=f"indexes.{','.join(key)}",
                action=MergeAction.ADDED,
                detail=f"index on ({','.join(key)}) added",
            ))

    return result, changes


def _merge_cross_relations(
    existing: list[EntityRelation],
    incoming: list[EntityRelation],
) -> tuple[list[EntityRelation], PathChange]:
    """合并跨实体关联列表，以 (source, target, type) 为主键"""
    def _rel_key(r: EntityRelation) -> tuple[str, str, str]:
        return (r.source_entity, r.target_entity, r.relation_type.value)

    by_key = {_rel_key(r): r for r in existing}
    result = list(existing)
    added = 0
    updated = 0

    for rel in incoming:
        key = _rel_key(rel)
        if key in by_key:
            old = by_key[key]
            if old.model_dump() != rel.model_dump():
                idx = next(i for i, r in enumerate(result) if _rel_key(r) == key)
                result[idx] = rel
                by_key[key] = rel
                updated += 1
        else:
            result.append(rel)
            by_key[key] = rel
            added += 1

    detail_parts = []
    if added:
        detail_parts.append(f"{added} added")
    if updated:
        detail_parts.append(f"{updated} updated")

    action = MergeAction.UPDATED if (added or updated) else MergeAction.SKIPPED
    return result, PathChange(
        path="cross_relations",
        action=action,
        detail=", ".join(detail_parts) if detail_parts else "no changes",
        skip_reason=SkipReason.IDENTICAL if not (added or updated) else None,
    )


def _merge_shared_enums(
    existing: list[EnumDefinition],
    incoming: list[EnumDefinition],
) -> tuple[list[EnumDefinition], PathChange]:
    """合并共享枚举列表，以 enum.name 为主键"""
    by_name = {e.name: (i, e) for i, e in enumerate(existing)}
    result = list(existing)
    added = 0
    updated = 0

    for enum in incoming:
        if enum.name in by_name:
            idx, old = by_name[enum.name]
            if old.model_dump() != enum.model_dump():
                result[idx] = enum
                by_name[enum.name] = (idx, enum)
                updated += 1
        else:
            result.append(enum)
            by_name[enum.name] = (len(result) - 1, enum)
            added += 1

    detail_parts = []
    if added:
        detail_parts.append(f"{added} added")
    if updated:
        detail_parts.append(f"{updated} updated")

    action = MergeAction.UPDATED if (added or updated) else MergeAction.SKIPPED
    return result, PathChange(
        path="shared_enums",
        action=action,
        detail=", ".join(detail_parts) if detail_parts else "no changes",
        skip_reason=SkipReason.IDENTICAL if not (added or updated) else None,
    )


# ============================================================
# 实体级合并
# ============================================================


# CrudConfig 中需要子结构合并的路径 → 合并函数映射
_SCALAR_MERGE_PATHS = frozenset({
    "scope", "parent_menu", "display_name", "display_name_en",
    "description", "soft_delete", "drag_sort", "has_status_toggle",
    "recyclable",
})

_OBJECT_MERGE_PATHS = frozenset({
    "search_config", "list_config", "form_config", "permissions",
    "selectable", "layout", "style", "animation", "import_export",
    "inline_edit", "observability", "nl_query", "git", "audit", "test",
})


def _merge_entity(
    existing: CrudConfig,
    incoming: CrudConfig,
    touched_paths: set[str],
) -> tuple[CrudConfig, EntityMergeSummary]:
    """合并两个同 module 的 CrudConfig"""
    changes: list[PathChange] = []
    data = existing.model_dump()

    # 1. 子列表结构合并
    new_fields, fc = _merge_fields(
        existing.fields, incoming.fields, "fields" in touched_paths,
    )
    data["fields"] = [f.model_dump() for f in new_fields]
    changes.extend(fc)

    new_rels, rc = _merge_relations(
        existing.relations, incoming.relations, "relations" in touched_paths,
    )
    data["relations"] = [r.model_dump() for r in new_rels]
    changes.extend(rc)

    new_enums, ec = _merge_enums(
        existing.enums, incoming.enums, "enums" in touched_paths,
    )
    data["enums"] = [e.model_dump() for e in new_enums]
    changes.extend(ec)

    new_indexes, ic = _merge_indexes(
        existing.indexes, incoming.indexes, "indexes" in touched_paths,
    )
    data["indexes"] = [i.model_dump() for i in new_indexes]
    changes.extend(ic)

    # 2. 标量字段合并
    incoming_data = incoming.model_dump()
    for path in _SCALAR_MERGE_PATHS:
        if path in touched_paths:
            changes.append(PathChange(
                path=path,
                action=MergeAction.SKIPPED,
                skip_reason=SkipReason.TOUCHED_PATH,
                detail=f"{path} locked by user",
            ))
            continue
        if incoming_data.get(path) != data.get(path):
            data[path] = incoming_data[path]
            changes.append(PathChange(
                path=path,
                action=MergeAction.UPDATED,
                detail=f"{path} updated",
            ))

    # 3. 对象字段合并（整体替换，但尊重 touchedPaths）
    for path in _OBJECT_MERGE_PATHS:
        if path in touched_paths:
            changes.append(PathChange(
                path=path,
                action=MergeAction.SKIPPED,
                skip_reason=SkipReason.TOUCHED_PATH,
                detail=f"{path} locked by user",
            ))
            continue
        incoming_val = incoming_data.get(path)
        existing_val = data.get(path)
        if incoming_val is not None and incoming_val != existing_val:
            data[path] = incoming_val
            changes.append(PathChange(
                path=path,
                action=MergeAction.UPDATED,
                detail=f"{path} updated",
            ))

    # 4. 列表字段合并（hooks, operations, custom_slots, logic_flows）
    for list_path in ("hooks", "operations", "custom_slots", "logic_flows"):
        if list_path in touched_paths:
            changes.append(PathChange(
                path=list_path,
                action=MergeAction.SKIPPED,
                skip_reason=SkipReason.TOUCHED_PATH,
                detail=f"{list_path} locked by user",
            ))
            continue
        incoming_val = incoming_data.get(list_path)
        existing_val = data.get(list_path)
        if incoming_val is not None and incoming_val != existing_val:
            data[list_path] = incoming_val
            changes.append(PathChange(
                path=list_path,
                action=MergeAction.UPDATED,
                detail=f"{list_path} updated",
            ))

    merged = CrudConfig.model_validate(data)

    has_updates = any(c.action != MergeAction.SKIPPED for c in changes)
    action = MergeAction.UPDATED if has_updates else MergeAction.SKIPPED

    return merged, EntityMergeSummary(
        module=existing.module,
        action=action,
        changes=changes,
    )


# ============================================================
# 主入口
# ============================================================


class BatchMergePatch(BaseModel):
    """BatchCrudProject 增量合并输入

    可以只包含部分实体——仅需要追加/修正的实体。
    """

    project_name: str | None = Field(None, description="项目名称 (None 不修改)")
    description: str | None = Field(None, description="项目描述 (None 不修改)")
    entities: list[CrudConfig] = Field(default_factory=list, description="要合并的实体")
    cross_relations: list[EntityRelation] | None = Field(
        None, description="跨表关联 (None 不修改)"
    )
    shared_enums: list[EnumDefinition] | None = Field(
        None, description="共享枚举 (None 不修改)"
    )
    generation_order: list[str] | None = Field(
        None, description="生成顺序 (None 不修改)"
    )


class BatchMergeResult(BaseModel):
    """BatchCrudProject 合并结果"""

    project: BatchCrudProject = Field(..., description="合并后的项目")
    summary: MergeSummary = Field(..., description="合并摘要")


def merge_batch_project(
    base: BatchCrudProject,
    patch: BatchMergePatch,
    touched_paths: dict[str, set[str]] | None = None,
) -> BatchMergeResult:
    """将 patch 幂等合并到 base BatchCrudProject

    Args:
        base: 现有的 BatchCrudProject
        patch: 增量修改（可以只包含部分实体）
        touched_paths: 用户已编辑的路径集合，key 为 entity.module，
                       value 为该实体下被保护的路径集合。
                       特殊 key "__project__" 用于保护项目级字段。

    Returns:
        BatchMergeResult 包含合并后的 project 和 merge_summary
    """
    if touched_paths is None:
        touched_paths = {}

    summary = MergeSummary()

    # 1. 项目级标量字段合并
    project_touched = touched_paths.get("__project__", set())
    project_name = base.project_name
    project_desc = base.description

    if patch.project_name is not None and patch.project_name != base.project_name:
        if "project_name" in project_touched:
            summary.project_level.append(PathChange(
                path="project_name",
                action=MergeAction.SKIPPED,
                skip_reason=SkipReason.TOUCHED_PATH,
                detail="project_name locked by user",
            ))
        else:
            project_name = patch.project_name
            summary.project_level.append(PathChange(
                path="project_name",
                action=MergeAction.UPDATED,
                detail=f"project_name updated to '{patch.project_name}'",
            ))

    if patch.description is not None and patch.description != base.description:
        if "description" in project_touched:
            summary.project_level.append(PathChange(
                path="description",
                action=MergeAction.SKIPPED,
                skip_reason=SkipReason.TOUCHED_PATH,
                detail="description locked by user",
            ))
        else:
            project_desc = patch.description
            summary.project_level.append(PathChange(
                path="description",
                action=MergeAction.UPDATED,
                detail="description updated",
            ))

    # 2. 实体级合并
    entity_map: dict[str, CrudConfig] = {e.module: e for e in base.entities}
    merged_entities: list[CrudConfig] = list(base.entities)

    for incoming_entity in patch.entities:
        module = incoming_entity.module
        entity_touched = touched_paths.get(module, set())

        if module in entity_map:
            # 更新已存在的实体
            existing = entity_map[module]
            idx = next(i for i, e in enumerate(merged_entities) if e.module == module)
            merged_entity, entity_summary = _merge_entity(
                existing, incoming_entity, entity_touched,
            )
            merged_entities[idx] = merged_entity
            entity_map[module] = merged_entity
            summary.entities.append(entity_summary)
        else:
            # 新增实体
            merged_entities.append(incoming_entity)
            entity_map[module] = incoming_entity
            summary.entities.append(EntityMergeSummary(
                module=module,
                action=MergeAction.ADDED,
                changes=[PathChange(
                    path="*",
                    action=MergeAction.ADDED,
                    detail=f"new entity '{module}' added",
                )],
            ))

    # 3. cross_relations 合并
    if patch.cross_relations is not None:
        merged_cross, cr_change = _merge_cross_relations(
            base.cross_relations, patch.cross_relations,
        )
        summary.cross_relations = cr_change
    else:
        merged_cross = list(base.cross_relations)

    # 4. shared_enums 合并
    if patch.shared_enums is not None:
        merged_shared, se_change = _merge_shared_enums(
            base.shared_enums, patch.shared_enums,
        )
        summary.shared_enums = se_change
    else:
        merged_shared = list(base.shared_enums)

    # 5. generation_order 合并
    if patch.generation_order is not None:
        if "generation_order" in project_touched:
            merged_order = list(base.generation_order)
            summary.generation_order = PathChange(
                path="generation_order",
                action=MergeAction.SKIPPED,
                skip_reason=SkipReason.TOUCHED_PATH,
                detail="generation_order locked by user",
            )
        else:
            merged_order = list(patch.generation_order)
            summary.generation_order = PathChange(
                path="generation_order",
                action=MergeAction.UPDATED,
                detail=f"generation_order updated to {patch.generation_order}",
            )
    else:
        merged_order = list(base.generation_order)

    merged_project = BatchCrudProject(
        project_name=project_name,
        description=project_desc,
        entities=merged_entities,
        cross_relations=merged_cross,
        shared_enums=merged_shared,
        generation_order=merged_order,
    )

    return BatchMergeResult(project=merged_project, summary=summary)


__all__ = [
    "MergeAction",
    "SkipReason",
    "PathChange",
    "EntityMergeSummary",
    "MergeSummary",
    "BatchMergePatch",
    "BatchMergeResult",
    "merge_batch_project",
    "PROTECTABLE_PATHS",
]
