"""
多表依赖排序与 cross_relations 强校验

功能：
- 从 BatchCrudProject 的 entities + cross_relations 构建依赖 DAG
- 自动拓扑排序（generation_order 缺失时）
- 校验 generation_order 与依赖图的一致性
- 循环依赖检测与路径报告
- cross_relations 引用实体存在性 + 外键冲突检测
- many_to_many 明确策略提示
"""

from __future__ import annotations

from collections import deque
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field

from app.codegen.schemas import BatchCrudProject, RelationType


# ============================================================
# 错误码枚举
# ============================================================


class DependencyErrorCode(str, Enum):
    """依赖校验错误码"""

    MISSING_ENTITY = "missing_entity"
    DUPLICATE_MODULE = "duplicate_module"
    DUPLICATE_TABLE = "duplicate_table"
    CYCLE_DETECTED = "cycle_detected"
    ORDER_MISSING_ENTITY = "order_missing_entity"
    ORDER_DUPLICATE = "order_duplicate"
    ORDER_DEPENDENCY_CONFLICT = "order_dependency_conflict"
    INVALID_RELATION_TYPE = "invalid_relation_type"
    FOREIGN_KEY_CONFLICT = "foreign_key_conflict"
    MANY_TO_MANY_UNSUPPORTED = "many_to_many_unsupported"
    SELF_REFERENCE = "self_reference"


# ============================================================
# 校验结果结构
# ============================================================


class DependencyError(BaseModel):
    """依赖校验错误"""

    code: DependencyErrorCode = Field(..., description="错误码")
    message: str = Field(..., description="人类可读的错误信息")
    details: dict[str, Any] = Field(default_factory=dict, description="详情")


class DependencyEdge(BaseModel):
    """依赖边"""

    source: str = Field(..., description="依赖方 (module)")
    target: str = Field(..., description="被依赖方 (module)")
    relation_type: str = Field(..., description="关系类型")
    foreign_key: str | None = Field(None, description="外键字段")


class DependencyGraph(BaseModel):
    """依赖图"""

    nodes: list[str] = Field(default_factory=list, description="所有实体 module")
    edges: list[DependencyEdge] = Field(default_factory=list, description="依赖边")


class ValidationResult(BaseModel):
    """校验结果"""

    valid: bool = Field(True, description="是否通过校验")
    errors: list[DependencyError] = Field(default_factory=list)
    warnings: list[DependencyError] = Field(default_factory=list)
    graph: DependencyGraph = Field(default_factory=DependencyGraph)
    resolved_order: list[str] = Field(default_factory=list, description="解析后的拓扑排序")


# ============================================================
# 依赖图构建
# ============================================================


def _build_dependency_graph(project: BatchCrudProject) -> DependencyGraph:
    """从 entities + cross_relations 构建依赖 DAG

    依赖规则：
    - belongs_to: source 依赖 target（先建 target 表）
    - has_many: target 依赖 source（通过 FK 引用 source）
    - self_ref_tree: 无跨实体依赖
    - many_to_many: 双向依赖（join entity 依赖两端）
    """
    nodes = [e.module for e in project.entities]
    edges: list[DependencyEdge] = []

    for rel in project.cross_relations:
        if rel.relation_type == RelationType.BELONGS_TO:
            # source 含 FK → source 依赖 target
            edges.append(DependencyEdge(
                source=rel.source_entity,
                target=rel.target_entity,
                relation_type=rel.relation_type.value,
                foreign_key=rel.foreign_key,
            ))
        elif rel.relation_type == RelationType.HAS_MANY:
            # target 含 FK → target 依赖 source
            edges.append(DependencyEdge(
                source=rel.target_entity,
                target=rel.source_entity,
                relation_type=rel.relation_type.value,
                foreign_key=rel.foreign_key,
            ))
        elif rel.relation_type == RelationType.MANY_TO_MANY:
            # join entity 依赖两端（但 join entity 可能不在 entities 中）
            # 这里仅记录边，不生成方向依赖
            edges.append(DependencyEdge(
                source=rel.source_entity,
                target=rel.target_entity,
                relation_type=rel.relation_type.value,
                foreign_key=rel.foreign_key,
            ))
        # self_ref_tree: 自引用，不产生跨实体依赖边

    return DependencyGraph(nodes=nodes, edges=edges)


# ============================================================
# 拓扑排序
# ============================================================


def _toposort(
    nodes: list[str],
    edges: list[DependencyEdge],
) -> tuple[list[str], list[list[str]] | None]:
    """拓扑排序，返回排序结果和可能的循环路径

    Args:
        nodes: 所有节点
        edges: 有向边 (source 依赖 target)

    Returns:
        (sorted_nodes, cycles)
        cycles 为 None 表示无循环
    """
    # 构建邻接表 (node → set of dependencies)
    adj: dict[str, set[str]] = {n: set() for n in nodes}
    for edge in edges:
        if edge.relation_type == RelationType.MANY_TO_MANY:
            continue  # many_to_many 不产生拓扑依赖
        if edge.source in adj and edge.target in adj:
            adj[edge.source].add(edge.target)

    # Kahn's algorithm
    in_degree: dict[str, int] = {n: 0 for n in nodes}
    reverse_adj: dict[str, set[str]] = {n: set() for n in nodes}
    for node, deps in adj.items():
        for dep in deps:
            in_degree[node] += 1
            reverse_adj[dep].add(node)

    q: deque[str] = deque()
    for node in nodes:
        if in_degree[node] == 0:
            q.append(node)

    # 稳定排序：同层按 module 名字母序
    q = deque(sorted(q))
    result: list[str] = []

    while q:
        node = q.popleft()
        result.append(node)
        dependents = sorted(reverse_adj.get(node, set()))
        for dep in dependents:
            in_degree[dep] -= 1
            if in_degree[dep] == 0:
                q.append(dep)
        q = deque(sorted(q))

    if len(result) != len(nodes):
        # 存在循环 → 找出所有循环
        remaining = set(nodes) - set(result)
        cycles = _find_cycles(remaining, adj)
        return result, cycles

    return result, None


def _find_cycles(
    nodes: set[str],
    adj: dict[str, set[str]],
) -> list[list[str]]:
    """在剩余节点中查找所有循环路径

    使用 DFS + current_path set 检测循环，每条搜索路径独立跟踪。
    """
    cycles: list[list[str]] = []
    visited: set[str] = set()

    for start in sorted(nodes):
        if start in visited:
            continue

        stack: list[tuple[str, list[str]]] = [(start, [start])]

        while stack:
            node, current_path = stack.pop()
            current_path_set = set(current_path)

            visited.add(node)

            for dep in sorted(adj.get(node, set()) & nodes):
                if dep in current_path_set:
                    cycle_start = current_path.index(dep)
                    cycle = current_path[cycle_start:] + [dep]
                    if cycle not in cycles:
                        cycles.append(cycle)
                elif dep not in visited:
                    stack.append((dep, current_path + [dep]))

    return cycles if cycles else [sorted(nodes)]


# ============================================================
# cross_relations 校验
# ============================================================


def _validate_cross_relations(project: BatchCrudProject) -> list[DependencyError]:
    """校验 cross_relations 的合法性"""
    errors: list[DependencyError] = []
    entity_modules = {e.module for e in project.entities}

    # 收集所有 foreign_key 以检测冲突
    fk_registry: dict[str, list[str]] = {}  # entity_module → [foreign_keys]

    for i, rel in enumerate(project.cross_relations):
        # 1. 实体存在性
        if rel.source_entity not in entity_modules:
            errors.append(DependencyError(
                code=DependencyErrorCode.MISSING_ENTITY,
                message=f"cross_relations[{i}].source_entity '{rel.source_entity}' not found in entities",
                details={
                    "index": i,
                    "field": "source_entity",
                    "value": rel.source_entity,
                    "available": sorted(entity_modules),
                },
            ))

        if rel.target_entity not in entity_modules:
            errors.append(DependencyError(
                code=DependencyErrorCode.MISSING_ENTITY,
                message=f"cross_relations[{i}].target_entity '{rel.target_entity}' not found in entities",
                details={
                    "index": i,
                    "field": "target_entity",
                    "value": rel.target_entity,
                    "available": sorted(entity_modules),
                },
            ))

        # 2. 自引用检查（cross_relations 中不应有自引用，那是 self_ref_tree）
        if rel.source_entity == rel.target_entity:
            errors.append(DependencyError(
                code=DependencyErrorCode.SELF_REFERENCE,
                message=f"cross_relations[{i}]: source and target are the same entity '{rel.source_entity}'. Use self_ref_tree in entity.relations instead.",
                details={
                    "index": i,
                    "entity": rel.source_entity,
                },
            ))

        # 3. many_to_many 策略提示
        if rel.relation_type == RelationType.MANY_TO_MANY:
            join_name = f"{rel.source_entity}_{rel.target_entity}"
            join_table = f"{rel.source_entity}_{rel.target_entity}s"
            errors.append(DependencyError(
                code=DependencyErrorCode.MANY_TO_MANY_UNSUPPORTED,
                message=(
                    f"cross_relations[{i}]: many_to_many between "
                    f"'{rel.source_entity}' and '{rel.target_entity}' is not directly supported in v1. "
                    f"Replace with an explicit join entity '{join_name}' "
                    f"and two belongs_to relations."
                ),
                details={
                    "index": i,
                    "source": rel.source_entity,
                    "target": rel.target_entity,
                    "suggestion": "create_join_entity",
                    "fix": {
                        "join_entity_module": join_name,
                        "join_entity_table": join_table,
                        "remove_relation_index": i,
                        "add_relations": [
                            {
                                "source_entity": join_name,
                                "target_entity": rel.source_entity,
                                "relation_type": "belongs_to",
                                "foreign_key": f"{rel.source_entity}_id",
                            },
                            {
                                "source_entity": join_name,
                                "target_entity": rel.target_entity,
                                "relation_type": "belongs_to",
                                "foreign_key": f"{rel.target_entity}_id",
                            },
                        ],
                    },
                },
            ))

        # 4. 外键冲突检测
        if rel.foreign_key:
            owner = (
                rel.source_entity
                if rel.relation_type == RelationType.BELONGS_TO
                else rel.target_entity
            )
            if owner not in fk_registry:
                fk_registry[owner] = []
            if rel.foreign_key in fk_registry[owner]:
                errors.append(DependencyError(
                    code=DependencyErrorCode.FOREIGN_KEY_CONFLICT,
                    message=(
                        f"cross_relations[{i}]: foreign_key '{rel.foreign_key}' "
                        f"conflicts in entity '{owner}' (already used)"
                    ),
                    details={
                        "index": i,
                        "entity": owner,
                        "foreign_key": rel.foreign_key,
                    },
                ))
            else:
                fk_registry[owner].append(rel.foreign_key)

    return errors


# ============================================================
# generation_order 校验
# ============================================================


def _validate_generation_order(
    project: BatchCrudProject,
    topo_order: list[str],
    adj: dict[str, set[str]],
) -> list[DependencyError]:
    """校验 generation_order 的合法性"""
    errors: list[DependencyError] = []
    if not project.generation_order:
        return errors

    entity_modules = {e.module for e in project.entities}
    order = project.generation_order

    # 1. 重复检查
    seen: set[str] = set()
    duplicates: list[str] = []
    for m in order:
        if m in seen:
            duplicates.append(m)
        seen.add(m)

    if duplicates:
        errors.append(DependencyError(
            code=DependencyErrorCode.ORDER_DUPLICATE,
            message=f"generation_order contains duplicates: {duplicates}",
            details={"duplicates": duplicates},
        ))

    # 2. 覆盖检查
    missing_in_order = entity_modules - set(order)
    if missing_in_order:
        errors.append(DependencyError(
            code=DependencyErrorCode.ORDER_MISSING_ENTITY,
            message=f"generation_order missing entities: {sorted(missing_in_order)}",
            details={"missing": sorted(missing_in_order)},
        ))

    unknown_in_order = set(order) - entity_modules
    if unknown_in_order:
        errors.append(DependencyError(
            code=DependencyErrorCode.MISSING_ENTITY,
            message=f"generation_order references unknown entities: {sorted(unknown_in_order)}",
            details={"unknown": sorted(unknown_in_order)},
        ))

    # 3. 依赖冲突检查：order 中 A 在 B 之前，但 A 依赖 B
    order_index = {m: i for i, m in enumerate(order)}
    for node, deps in adj.items():
        if node not in order_index:
            continue
        for dep in deps:
            if dep not in order_index:
                continue
            if order_index[node] < order_index[dep]:
                # node 排在 dep 前面，但 node 依赖 dep → 冲突
                errors.append(DependencyError(
                    code=DependencyErrorCode.ORDER_DEPENDENCY_CONFLICT,
                    message=(
                        f"generation_order conflict: '{node}' (index {order_index[node]}) "
                        f"depends on '{dep}' (index {order_index[dep]}), "
                        f"but '{node}' is ordered before '{dep}'"
                    ),
                    details={
                        "entity": node,
                        "dependency": dep,
                        "entity_index": order_index[node],
                        "dependency_index": order_index[dep],
                    },
                ))

    return errors


# ============================================================
# 基础校验
# ============================================================


def _validate_entities(project: BatchCrudProject) -> list[DependencyError]:
    """校验实体的基础合法性"""
    errors: list[DependencyError] = []

    # module 唯一性
    modules: dict[str, int] = {}
    for i, entity in enumerate(project.entities):
        if entity.module in modules:
            errors.append(DependencyError(
                code=DependencyErrorCode.DUPLICATE_MODULE,
                message=f"Duplicate entity module '{entity.module}' at index {i} (first at {modules[entity.module]})",
                details={
                    "module": entity.module,
                    "index": i,
                    "first_index": modules[entity.module],
                },
            ))
        else:
            modules[entity.module] = i

    # table_name 唯一性
    tables: dict[str, int] = {}
    for i, entity in enumerate(project.entities):
        if entity.table_name in tables:
            errors.append(DependencyError(
                code=DependencyErrorCode.DUPLICATE_TABLE,
                message=f"Duplicate table_name '{entity.table_name}' at index {i} (first at {tables[entity.table_name]})",
                details={
                    "table_name": entity.table_name,
                    "index": i,
                    "first_index": tables[entity.table_name],
                },
            ))
        else:
            tables[entity.table_name] = i

    return errors


# ============================================================
# 主入口
# ============================================================


def validate_and_sort(project: BatchCrudProject) -> ValidationResult:
    """校验 BatchCrudProject 并返回拓扑排序结果

    执行以下校验：
    1. 实体 module/table_name 唯一性
    2. cross_relations 引用合法性 + FK 冲突
    3. 循环依赖检测
    4. generation_order 合法性
    5. 自动拓扑排序（generation_order 缺失时）

    Returns:
        ValidationResult 包含校验结果和排序后的实体顺序
    """
    result = ValidationResult()

    # 1. 基础实体校验
    entity_errors = _validate_entities(project)
    result.errors.extend(entity_errors)

    # 如果有重复 module/table，后续校验可能不可靠
    if entity_errors:
        result.valid = False
        return result

    # 2. cross_relations 校验
    rel_errors = _validate_cross_relations(project)
    # many_to_many v1: 作为 error（含结构化修复指引）
    for err in rel_errors:
        result.errors.append(err)

    # 3. 构建依赖图
    graph = _build_dependency_graph(project)
    result.graph = graph

    # 4. 拓扑排序 + 循环检测
    topo_order, cycles = _toposort(graph.nodes, graph.edges)

    if cycles:
        for cycle in cycles:
            result.errors.append(DependencyError(
                code=DependencyErrorCode.CYCLE_DETECTED,
                message=f"Circular dependency detected: {' → '.join(cycle + [cycle[0]])}",
                details={"cycle": cycle},
            ))
        result.valid = False
        result.resolved_order = topo_order  # 部分排序
        return result

    result.resolved_order = topo_order

    # 5. generation_order 校验
    adj: dict[str, set[str]] = {n: set() for n in graph.nodes}
    for edge in graph.edges:
        if edge.relation_type == RelationType.MANY_TO_MANY:
            continue
        if edge.source in adj and edge.target in adj:
            adj[edge.source].add(edge.target)

    order_errors = _validate_generation_order(project, topo_order, adj)
    result.errors.extend(order_errors)

    # 6. 汇总
    if result.errors:
        result.valid = False

    return result


def resolve_generation_order(project: BatchCrudProject) -> list[str]:
    """解析生成顺序

    如果 generation_order 为空，自动推导。
    如果已提供且无冲突，直接返回。

    Args:
        project: BatchCrudProject

    Returns:
        排好序的 module 列表
    """
    validation = validate_and_sort(project)

    if project.generation_order and not any(
        e.code in (
            DependencyErrorCode.ORDER_DEPENDENCY_CONFLICT,
            DependencyErrorCode.ORDER_MISSING_ENTITY,
            DependencyErrorCode.ORDER_DUPLICATE,
        )
        for e in validation.errors
    ):
        return list(project.generation_order)

    return validation.resolved_order


__all__ = [
    "DependencyErrorCode",
    "DependencyError",
    "DependencyEdge",
    "DependencyGraph",
    "ValidationResult",
    "validate_and_sort",
    "resolve_generation_order",
]
