"""
Batch ProjectGraph — 实体依赖图/关系图输出

M58-T13: 为多表项目提供可视化/可诊断的数据结构：
- 实体节点（module/table/display_name）
- 关系边（source/target/type/foreign_key）
- 依赖顺序（generation_order）
- 问题列表（issues/warnings）

供 Wizard ER 图可视化、AI 智能体排错和解释生成顺序。
"""

from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field

from app.codegen.batch_deps import (
    DependencyError,
    DependencyErrorCode,
    ValidationResult,
    validate_and_sort,
)
from app.codegen.batch_result import check_shared_enums_boundary
from app.codegen.schemas import BatchCrudProject

GRAPH_VERSION = "1.0.0"


class IssueSeverity(str, Enum):
    """问题严重性"""

    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


# ============================================================
# Graph 节点
# ============================================================


class GraphNode(BaseModel):
    """实体节点"""

    id: str = Field(..., description="节点 ID (= entity.module)")
    module: str = Field(..., description="模块名")
    table_name: str = Field(..., description="表名")
    display_name: str = Field(..., description="中文显示名")
    display_name_en: str = Field("", description="英文显示名")
    field_count: int = Field(0, description="字段数量")
    order_index: int = Field(-1, description="生成顺序索引 (-1 = 未排序)")


# ============================================================
# Graph 边
# ============================================================


class GraphEdge(BaseModel):
    """关系边"""

    source: str = Field(..., description="来源实体 (module)")
    target: str = Field(..., description="目标实体 (module)")
    relation_type: str = Field(..., description="关系类型 (belongs_to/has_many/...)")
    foreign_key: str | None = Field(None, description="外键字段名")
    label: str = Field("", description="边标签（用于可视化）")


# ============================================================
# Graph Issue
# ============================================================


class GraphIssue(BaseModel):
    """图中的问题"""

    severity: IssueSeverity = Field(IssueSeverity.ERROR, description="严重性")
    code: str = Field(..., description="错误码")
    message: str = Field(..., description="人类可读信息")
    related_nodes: list[str] = Field(
        default_factory=list, description="关联的节点 ID",
    )
    related_edges: list[int] = Field(
        default_factory=list, description="关联的边索引",
    )


# ============================================================
# ProjectGraph
# ============================================================


class ProjectGraph(BaseModel):
    """项目依赖图（完整输出）"""

    version: str = Field(GRAPH_VERSION)
    project_name: str = Field("")
    nodes: list[GraphNode] = Field(default_factory=list)
    edges: list[GraphEdge] = Field(default_factory=list)
    generation_order: list[str] = Field(
        default_factory=list,
        description="最终解析后的生成顺序",
    )
    issues: list[GraphIssue] = Field(default_factory=list)
    warnings: list[GraphIssue] = Field(default_factory=list)
    valid: bool = Field(True, description="是否通过校验")
    entity_count: int = Field(0)
    edge_count: int = Field(0)

    def to_dict(self) -> dict[str, Any]:
        """序列化为 dict（供工具输出）"""
        return self.model_dump(mode="json")


# ============================================================
# Graph 构建
# ============================================================


def build_project_graph(project: BatchCrudProject) -> ProjectGraph:
    """从 BatchCrudProject 构建 ProjectGraph

    流程：
    1. 校验 + 拓扑排序（复用 validate_and_sort）
    2. 构建节点（从 entities）
    3. 构建边（从 cross_relations + entity.relations）
    4. 映射 issues/warnings
    5. shared_enums 边界检查

    Args:
        project: BatchCrudProject

    Returns:
        ProjectGraph
    """
    # 1. 校验 + 排序
    vr = validate_and_sort(project)

    # 2. 构建节点
    order_map = {
        module: idx
        for idx, module in enumerate(vr.resolved_order)
    }
    entity_map = {e.module: e for e in project.entities}

    nodes: list[GraphNode] = []
    for entity in project.entities:
        nodes.append(GraphNode(
            id=entity.module,
            module=entity.module,
            table_name=entity.table_name,
            display_name=entity.display_name,
            display_name_en=entity.display_name_en,
            field_count=len(entity.fields) if entity.fields else 0,
            order_index=order_map.get(entity.module, -1),
        ))

    # 3. 构建边
    edges: list[GraphEdge] = []

    # 3a. 从 cross_relations
    if project.cross_relations:
        for rel in project.cross_relations:
            source_module = rel.source_entity
            target_module = rel.target_entity
            edges.append(GraphEdge(
                source=source_module,
                target=target_module,
                relation_type=rel.relation_type,
                foreign_key=rel.foreign_key,
                label=f"{source_module} → {target_module}",
            ))

    # 3b. 从 dependency graph 边（可能包含 entity.relations 推导的依赖）
    for dep_edge in vr.graph.edges:
        # 检查是否已在 cross_relations 中
        already_exists = any(
            e.source == dep_edge.source
            and e.target == dep_edge.target
            and e.relation_type == dep_edge.relation_type
            for e in edges
        )
        if not already_exists:
            edges.append(GraphEdge(
                source=dep_edge.source,
                target=dep_edge.target,
                relation_type=dep_edge.relation_type,
                foreign_key=dep_edge.foreign_key,
                label=f"{dep_edge.source} → {dep_edge.target}",
            ))

    # 4. 映射 issues/warnings
    issues = _map_validation_issues(vr.errors, IssueSeverity.ERROR)
    warnings = _map_validation_issues(vr.warnings, IssueSeverity.WARNING)

    # 5. shared_enums 边界检查
    shared_warnings = check_shared_enums_boundary(
        project.shared_enums,
    )
    for w in shared_warnings:
        warnings.append(GraphIssue(
            severity=IssueSeverity.WARNING,
            code="shared_enums_v1",
            message=w,
        ))

    return ProjectGraph(
        project_name=project.project_name,
        nodes=nodes,
        edges=edges,
        generation_order=vr.resolved_order,
        issues=issues,
        warnings=warnings,
        valid=vr.valid,
        entity_count=len(nodes),
        edge_count=len(edges),
    )


def _map_validation_issues(
    errors: list[DependencyError],
    severity: IssueSeverity,
) -> list[GraphIssue]:
    """将 DependencyError 列表映射到 GraphIssue"""
    issues: list[GraphIssue] = []
    for err in errors:
        related_nodes: list[str] = []
        details = err.details or {}

        # 从 details 中提取关联节点
        for key in ("source", "target", "module", "entity"):
            if key in details:
                related_nodes.append(str(details[key]))
        if "modules" in details:
            related_nodes.extend(str(m) for m in details["modules"])
        if "cycle" in details:
            related_nodes.extend(str(m) for m in details["cycle"])

        issues.append(GraphIssue(
            severity=severity,
            code=err.code.value,
            message=err.message,
            related_nodes=related_nodes,
        ))
    return issues


__all__ = [
    "GRAPH_VERSION",
    "GraphEdge",
    "GraphIssue",
    "GraphNode",
    "ProjectGraph",
    "build_project_graph",
]
